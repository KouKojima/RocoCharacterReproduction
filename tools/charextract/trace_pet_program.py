"""Trace register state of the pet BasePass program around the discard decision."""
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dxbc_interp import Interpreter  # noqa: E402

SHADERS = pathlib.Path(sys.argv[1])
PREFIX = sys.argv[2]
SHADER_FILE = sys.argv[3]

WATCH = ('discard', 'mad r0.x', 'lt r0.x', 'max r0.x', 'min r0.x', 'and r0', 'ge r0.y', 'dp4',
         'movc r0.y', 'round_ne', 'add r3.x', 'div_sat r3.x')

lines = (SHADERS / (SHADER_FILE + '.asm')).read_text(encoding='utf8').splitlines()
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

m = np.array(json.loads((SHADERS / (PREFIX + '-evaluated.json')).read_text(encoding='utf8'))['buffer'])
print('cb6[33..40]:')
for i in range(33, 41):
    print('   cb6[%d] = %s' % (i, m[i]))

light_dir = np.array([0.35, -0.55, 0.75])
light_dir /= np.linalg.norm(light_dir)
cb = {i: np.zeros((300, 4)) for i in range(7)}
cb[6][:len(m)] = m
cb[0][23] = [0.0, 0.0, 0.0, 0.0]
cb[0][79] = [0.0, 0.0, 0.0, 0.0]
cb[0][138] = [0.0, 0.0, 0.0, 0.0]
cb[0][145] = [0.0, 1.0, 0.0, 0.0]
cb[0][156] = [0.0, 1.0, 0.0, 0.0]
cb[0][147] = [0.0, 0.0, 0.0, 1.0]
cb[0][199] = [0.18, 0.20, 0.26, 0.0]
cb[0][294] = [0.0, 1.0, 0.0, 1.0]
cb[1][79] = [0.0, 0.0, 1.0, 1.0]
for row in (0, 1, 2, 8):
    cb[2][row] = list(light_dir) + [0.0]
cb[2][3] = [0.0, 0.0, 0.0, 0.0]
cb[2][4] = [1.0, 1.0, 1.0, 1.0]
cb[2][51] = [0.0, 0.0, 0.0, 0.0]
cb[3][23] = [0.0, 0.0, 0.0, 0.0]
cb[3][30] = [0.0, 0.0, 0.0, 0.0]
cb[4][1] = [1.0, 1.0, 1.0, 0.0]
cb[4][2] = [1.0, 0.0, 0.0, 0.0]
cb[4][12] = [0.0, 0.0, 0.0, 0.0]
cb[4][13] = list(light_dir) + [float(np.dot(light_dir, [0.375, 0.5, 0.125]))]
cb[4][14] = list(light_dir) + [1.0]
cb[4][15] = [0.0, 0.0, 0.0, 0.0]
cb[5][2] = [0.0, 0.0, 0.5, 0.0]

rng = np.random.default_rng(20260907)
base = rng.uniform(0.05, 0.95, size=4)
mask = rng.uniform(0.05, 0.95, size=4)
ramp = rng.uniform(0.0, 1.0, size=4)
textures = {0: lambda i: np.array([0.9, 0.9, 0.9, 0.9]), 1: base, 2: mask, 3: ramp}

normal = np.array([0.2, 0.3, 0.93])
normal /= np.linalg.norm(normal)
v = {i: np.zeros(4) for i in range(8)}
v[1] = list(normal) + [1.0]
v[2] = [0.0, 0.37, 0.42, 0.2]
v[3][:2] = [0.31, 0.62]
v[6] = [0.12, 1.35, -0.4, 1.0]
v[7] = [640.0, 360.0, 0.5, 0.002]

interp = Interpreter(cb, v, textures)
interp.r[0] = [1.0, 1.0, 1.0, 0.0]

for line in block:
    before = interp.r.copy()
    interp.run([line])
    text = line.strip()
    if any(w in text for w in WATCH):
        print('  %-52s r0=%s -> %s   r1=%s r2=%s' % (
            text[:52], np.round(before[0], 4), np.round(interp.r[0], 4),
            np.round(interp.r[1], 4), np.round(interp.r[2], 4)))

print()
print('discarded:', interp.discarded)
print('o0:', interp.o[0])
