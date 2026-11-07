"""Debug helper: compare the DXBC interpreter and the numpy kernel step by step.

Prints the material rows that matter and the register state around the
instruction where the two implementations disagree.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dxbc_interp import Interpreter  # noqa: E402
from pet_kernel import body_surface, sat  # noqa: E402
from pet_runtime import IMMEDIATE_CONSTANT_BLOCK, build_runtime  # noqa: E402

SHADERS = pathlib.Path(sys.argv[1])
PREFIX = sys.argv[2]
SHADER_FILE = sys.argv[3]
TARGET = int(sys.argv[4]) if len(sys.argv) > 4 else 13


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


material = np.array(json.loads((SHADERS / (PREFIX + '-evaluated.json')).read_text(encoding='utf8'))['buffer'])
block = instruction_block(SHADERS / (SHADER_FILE + '.asm'))

for row in (5, 9, 12, 13, 15, 29, 30, 32, 33, 34, 35, 36, 37, 38, 40):
    print('cb6[%2d] = %s' % (row, np.round(material[row], 6).tolist()))

rng = np.random.default_rng(20260907)
for sample in range(TARGET + 1):
    normal = rng.normal(size=3)
    normal /= np.linalg.norm(normal)
    vertex_color = np.array([0.0, rng.uniform(0.0, 0.6), rng.uniform(0.0, 1.0), rng.uniform(0.0, 1.0)])
    uv = rng.uniform(0.0, 1.0, size=2)
    world_pos = rng.normal(size=3) * 1.2
    screen_pos = np.array([rng.uniform(0, 1920), rng.uniform(0, 1080), 0.5, 0.002])
    clip_w = float(rng.uniform(0.001, 0.05))
    base_tex = rng.uniform(0.02, 0.95, size=4)
    mask_tex = rng.uniform(0.02, 0.98, size=4)
    ramp_tex = rng.uniform(0.0, 1.0, size=4)
    light_vector = rng.normal(size=3)
    light_vector /= np.linalg.norm(light_vector)
    light_vector = light_vector * rng.uniform(0.3, 1.6)
    ambient = rng.uniform(0.02, 0.4, size=3)
    ramp_width = float(rng.uniform(0.4, 1.2))
    ramp_contrast = float(rng.uniform(0.2, 0.8))
    spec_scale = float(rng.uniform(0.0, 0.4))
    base_mix = float(rng.uniform(0.0, 1.0))
    diffuse_mix = float(rng.uniform(0.5, 1.0))

    cb = build_runtime(material, light_vector=light_vector, ambient_color=ambient,
                       shadow_value=float(rng.uniform(0.2, 1.0)), ramp_width=ramp_width,
                       ramp_contrast=ramp_contrast, spec_scale=spec_scale,
                       base_mix=base_mix, diffuse_mix=diffuse_mix)
    material = material.copy()
    material[32] = [material[30][0], material[30][1], material[30][2], 0.0]
    cb[6][32] = material[32]

    v = {i: np.zeros(4) for i in range(8)}
    v[1] = list(normal) + [1.0]
    v[2] = vertex_color
    v[3][:2] = uv
    v[6] = list(world_pos) + [clip_w]
    v[7] = screen_pos
    textures = {0: lambda i: np.array([1.0, 1.0, 1.0, 1.0]), 1: base_tex, 2: mask_tex, 3: ramp_tex}

print()
print('sample', TARGET)
print('mask_tex', mask_tex.tolist())

# run the interpreter up to the shadow/light block and dump the registers
interp = Interpreter(cb, v, textures, immediate=IMMEDIATE_CONSTANT_BLOCK)
interp.r[0] = [1.0, 1.0, 1.0, 0.0]
for count in (95, 99, 103, 105, 106):
    interp.run(block[:count])
    print('after %3d instr: r2=%s r3=%s' % (count,
          np.round(interp.r[2], 6).tolist(), np.round(interp.r[3], 6).tolist()))

interp.run(block)
expected = interp.o[0][:3]
got, discarded = body_surface(material, cb, normal, vertex_color, uv, world_pos,
                               screen_pos, clip_w, base_tex, mask_tex, ramp_tex,
                               IMMEDIATE_CONSTANT_BLOCK)
print('interpreter out', expected.tolist(), 'discarded', interp.discarded)
print('kernel      out', np.asarray(got).tolist(), 'discarded', discarded)
