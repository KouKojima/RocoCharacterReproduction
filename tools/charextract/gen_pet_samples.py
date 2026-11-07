"""Generate random samples and the expected results for the pet shader check.

The expected values come from the original DXBC programs executed by the
workspace interpreter, so the generated GLSL can be compared against the
original programs in a browser (see pet-validate.html).
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dxbc_glsl import Context, Transpiler, parse_block  # noqa: E402
from dxbc_interp import Interpreter  # noqa: E402
from pet_runtime import IMMEDIATE_CONSTANT_BLOCK, build_runtime  # noqa: E402
from pet_programs import PROGRAMS, build_textures, build_vertex_registers, json_safe  # noqa: E402

SHADERS = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
SAMPLES = int(sys.argv[3]) if len(sys.argv) > 3 else 120

rng = np.random.default_rng(20260907)


def instruction_block(path: pathlib.Path):
    lines = path.read_text(encoding='utf8').splitlines()
    start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('dcl_temps'):
            start = i + 1
            break
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].strip().startswith('ret'):
            end = i
            break
    return lines[start:end]


def random_unit():
    v = rng.normal(size=3)
    return v / np.linalg.norm(v)


out = {'programs': {}}
for key, spec in PROGRAMS.items():
    lines = (SHADERS / (spec['file'] + '.asm')).read_text(encoding='utf8').splitlines()
    block = instruction_block(SHADERS / (spec['file'] + '.asm'))
    context = Context(spec['material'], spec['vmap'], spec['tmap'])
    transpiler = Transpiler(context)
    transpiler.emit(parse_block(lines))

    material = np.array(json.loads((SHADERS / (spec['prefix'] + '-evaluated.json')).read_text(encoding='utf8'))['buffer'])
    material_register = int(spec['material'][2:])
    samples = []
    for _ in range(SAMPLES):
        normal = random_unit()
        vertex_color = np.array([0.0, rng.uniform(0.0, 0.6), rng.uniform(0.0, 1.0), rng.uniform(0.0, 1.0)])
        uv = rng.uniform(0.0, 1.0, size=2)
        world = rng.normal(size=3) * 1.2
        screen = np.array([rng.uniform(0, 1920), rng.uniform(0, 1080), 0.5, rng.uniform(0.001, 0.05)])
        outline_width = np.array([rng.uniform(0.0, 2.0), rng.uniform(0.0, 2.0), 0.0, 0.0])

        light_vector = random_unit() * rng.uniform(0.3, 1.6)
        ambient = rng.uniform(0.02, 0.4, size=3)
        cb = build_runtime(material,
                           light_vector=light_vector,
                           ambient_color=ambient,
                           ramp_width=float(rng.uniform(0.4, 1.2)),
                           ramp_contrast=float(rng.uniform(0.2, 0.8)),
                           spec_scale=float(rng.uniform(0.0, 0.4)),
                           base_mix=float(rng.uniform(0.0, 1.0)),
                           shadow_bias=float(rng.uniform(0.0, 0.2)),
                           ramp_blend=float(rng.uniform(0.0, 1.0)),
                           ramp_floor=float(rng.uniform(0.0, 1.0)),
                           light_offset=float(rng.uniform(-0.2, 0.2)))
        rows = material.copy()
        # cb6[32] is `MainColor * <runtime scalar>`; the scalar is 0 in the
        # cooked asset, the preview supplies 1.
        if material_register == 6 and len(rows) > 32 and rows[32].tolist() == [0.0, 0.0, 0.0, 0.0]:
            rows[32] = [rows[30][0], rows[30][1], rows[30][2], 0.0]
        # The body programs read their material from cb6, the outline program
        # from cb3 - that register then holds the material rows and not the
        # runtime block.
        cb[material_register][:len(rows)] = rows

        base_tex = rng.uniform(0.02, 0.95, size=4)
        mask_tex = rng.uniform(0.02, 0.98, size=4)
        ramp_tex = rng.uniform(0.0, 1.0, size=4)
        eye_tex = rng.uniform(0.02, 0.95, size=4)
        outline_tex = rng.uniform(0.0, 1.0, size=4)

        inputs = {
            'vNormal': [float(x) for x in normal],
            'vColor': [float(x) for x in vertex_color],
            'vUv': [float(x) for x in uv],
            'vWorldPosition': [float(x) for x in world],
            'vScreen': [float(x) for x in screen],
            'vOutlineWidth': [float(x) for x in outline_width],
        }
        sample_textures = {
            'uBase': [float(x) for x in base_tex],
            'uMask': [float(x) for x in mask_tex],
            'uRamp': [float(x) for x in ramp_tex],
            'uEyeAtlas': [float(x) for x in eye_tex],
            'uOutlineMask': [float(x) for x in outline_tex],
        }
        # the register layout follows the program's own v map / t map
        v = build_vertex_registers(spec['vmap'], inputs)
        textures = build_textures(spec['tmap'], sample_textures)

        interp = Interpreter(cb, v, textures, immediate=IMMEDIATE_CONSTANT_BLOCK)
        interp.r[0] = [1.0, 1.0, 1.0, 0.0]
        interp.run(block)

        uniforms = {}
        for name in sorted(transpiler.used_uniforms):
            if name.startswith('uCb'):
                register, row = name[3:].split('_')
                uniforms[name] = [float(x) for x in cb[int(register)][int(row)]]
            elif name == 'uShadowLut':
                uniforms[name] = [1.0, 1.0, 1.0, 1.0]
        uniforms['uMat'] = [[float(x) for x in row] for row in rows]

        samples.append({
            'uniforms': uniforms,
            'inputs': inputs,
            'textures': sample_textures,
            'expected': [float(x) for x in interp.o[0][:3]],
            'discarded': bool(interp.discarded),
        })
    out['programs'][key] = {'glsl': 'pet-%s.glsl' % key, 'samples': samples}
    print('%-8s %d samples' % (key, len(samples)))

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'pet-samples.json').write_text(json.dumps(json_safe(out), ensure_ascii=False), encoding='utf8')
print('wrote', OUT / 'pet-samples.json')
