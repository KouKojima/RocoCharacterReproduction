"""Build instruction-level probe shaders for the pet programs.

The probe shader runs the first N instructions of the transpiled program and
then writes a chosen register to the colour output. The expected values come
from the DXBC interpreter stopped at the same instruction, so the browser can
tell exactly which instruction first diverges from the original program.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dxbc_glsl import Context, Transpiler, parse_block  # noqa: E402
from dxbc_interp import Interpreter  # noqa: E402
from pet_runtime import IMMEDIATE_CONSTANT_BLOCK  # noqa: E402
from pet_programs import PROGRAMS, HEADER  # noqa: E402

SHADERS = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
SAMPLES = pathlib.Path(sys.argv[3])
KEY = sys.argv[4]
PROBES = [int(x) for x in sys.argv[5].split(',')]
REGISTER = sys.argv[6] if len(sys.argv) > 6 else 'r0'

spec = PROGRAMS[KEY]
lines = (SHADERS / (spec['file'] + '.asm')).read_text(encoding='utf8').splitlines()
ops = parse_block(lines)

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
block = lines[start:end]
assert len(block) == len(ops), (len(block), len(ops))

context = Context(spec['material'], spec['vmap'], spec['tmap'])
transpiler = Transpiler(context)
full = transpiler.emit(ops)

header = HEADER % {'title': 'probe-' + KEY, 'prefix': spec['prefix'], 'file': spec['file']}
for name in sorted(transpiler.used_uniforms):
    if name.startswith('uCb'):
        header += 'uniform vec4 %s;\n' % name


def state_from_sample(sample):
    cb = {i: np.zeros((300, 4)) for i in range(7)}
    for name, value in sample['uniforms'].items():
        if name.startswith('uCb'):
            register, row = name[3:].split('_')
            cb[int(register)][int(row)] = np.asarray(value, dtype=np.float64)
    u_mat = sample['uniforms']['uMat']
    cb[6][:len(u_mat)] = np.asarray(u_mat, dtype=np.float64)
    inputs = sample['inputs']
    v = {i: np.zeros(4) for i in range(8)}
    v[1] = list(inputs['vNormal']) + [1.0]
    v[2] = list(inputs['vColor'])
    v[3][:2] = list(inputs['vUv'])
    v[5] = list(inputs['vOutlineWidth'])
    v[6] = list(inputs['vWorldPosition']) + [inputs['vScreen'][3]]
    v[7] = list(inputs['vScreen'])
    textures = {
        0: lambda i: np.array([1.0, 1.0, 1.0, 1.0]),
        1: np.asarray(sample['textures']['uBase'], dtype=np.float64),
        2: np.asarray(sample['textures']['uMask'], dtype=np.float64),
        3: np.asarray(sample['textures']['uRamp'], dtype=np.float64),
        4: np.asarray(sample['textures']['uEyeAtlas'], dtype=np.float64),
        5: np.asarray(sample['textures']['uOutlineMask'], dtype=np.float64),
    }
    return cb, v, textures


data = json.loads(SAMPLES.read_text(encoding='utf8'))
samples = data['programs'][KEY]['samples']

OUT.mkdir(parents=True, exist_ok=True)
report = {}
for count in PROBES:
    body = transpiler.emit_range(ops, 0, count)
    if body.count('{') != body.count('}'):
        raise SystemExit('probe cut %d lands inside a branch' % count)
    # the probe must not be killed by a discard before the register is read
    body = '\n'.join(line for line in body.split('\n') if 'discard;' not in line)
    probe = 'outColor = vec4(%s.x, %s.y, %s.z, 1.0);\n' % (REGISTER, REGISTER, REGISTER)
    source = header + '\nvoid main(){\n' + body + '\n' + probe + '}\n'
    name = 'pet-probe-%s-%03d.glsl' % (KEY, count)
    (OUT / name).write_text(source, encoding='utf8')

    expected = []
    for sample in samples:
        cb, v, textures = state_from_sample(sample)
        interp = Interpreter(cb, v, textures, immediate=IMMEDIATE_CONSTANT_BLOCK)
        interp.r[0] = [1.0, 1.0, 1.0, 0.0]
        interp.run(block[:count])
        index = int(REGISTER[1:])
        expected.append([float(x) for x in interp.r[index][:3]])
    report[str(count)] = {'glsl': name, 'expected': expected}
    print('probe %s after %d instructions -> %s' % (REGISTER, count, name))

(OUT / ('pet-probe-%s.json' % KEY)).write_text(json.dumps(report, ensure_ascii=False), encoding='utf8')
print('wrote', OUT / ('pet-probe-%s.json' % KEY))
