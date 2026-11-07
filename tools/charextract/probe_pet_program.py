"""Execute the original pet BasePass pixel program and report its output.

This is a probe: it runs the cooked DXBC through the workspace DXBC interpreter
with a chosen set of runtime constant-buffer values so the recovered material
kernel can be checked against the original program instead of a guess.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dxbc_interp import Interpreter  # noqa: E402

SHADERS = pathlib.Path(sys.argv[1])
PREFIX = sys.argv[2]
SHADER_FILE = sys.argv[3]

rng = np.random.default_rng(20260907)


def instruction_block(path: pathlib.Path):
    """The executable block starts after the last dcl_ declaration."""
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


m = np.array(json.loads((SHADERS / (PREFIX + '-evaluated.json')).read_text(encoding='utf8'))['buffer'])
block = instruction_block(SHADERS / (SHADER_FILE + '.asm'))
print('block lines: %d..%d  (%d instructions)' % (block[0][:0] and 0 or 0, len(block), len(block)))

# ---------------------------------------------------------------- runtime state
light_dir = np.array([0.35, -0.55, 0.75])
light_dir /= np.linalg.norm(light_dir)
light_color = np.array([1.0, 0.97, 0.92])
ambient = np.array([0.18, 0.20, 0.26])

cb = {i: np.zeros((300, 4)) for i in range(7)}
cb[6][:len(m)] = m
cb[0][23] = [0.0, 0.0, 0.0, 0.0]      # camera position
cb[0][79] = [0.0, 0.0, 0.0, 0.0]      # frame counter -> r0.y = 0
cb[0][138] = [0.0, 0.0, 0.0, 0.0]     # viewport origin
cb[0][145] = [0.0, 1.0, 0.0, 0.0]     # output scale
cb[0][156] = [0.0, 1.0, 0.0, 0.0]     # output blend
cb[0][147] = [0.0, 0.0, 0.0, 1.0]     # normal remap
cb[0][199] = list(ambient) + [0.0]    # ambient colour
cb[0][294] = [0.0, 1.0, 0.0, 1.0]     # shadow depth bias / scale
cb[1][79] = [0.0, 0.0, 1.0, 1.0]      # fog

cb[2][0] = list(light_dir) + [0.0]
cb[2][1] = list(light_dir) + [0.0]
cb[2][2] = list(light_dir) + [0.0]
cb[2][3] = [0.0, 0.0, 0.0, 0.0]
cb[2][4] = [1.0, 1.0, 1.0, 1.0]
cb[2][8] = list(light_dir) + [0.0]
cb[2][51] = [0.0, 0.0, 0.0, 0.0]

cb[3][23] = [0.0, 0.0, 0.0, 0.0]
cb[3][30] = [0.0, 0.0, 0.0, 0.0]

cb[4][1] = [1.0, 1.0, 1.0, 0.0]      # ramp tint / blend / floor
cb[4][2] = [1.0, 0.0, 0.0, 0.0]      # ramp width, light offset
cb[4][12] = [0.0, 0.0, 0.0, 0.0]
cb[4][13] = list(light_dir) + [float(np.dot(light_dir, [0.375, 0.5, 0.125]))]
cb[4][14] = list(light_dir) + [1.0]
cb[4][15] = [0.0, 0.0, 0.0, 0.0]

cb[5][2] = [0.0, 0.0, 0.5, 0.0]      # ramp contrast

# Optional cb6 row overrides, either inline JSON or a path to a JSON file.
if len(sys.argv) > 4 and sys.argv[4]:
    raw = sys.argv[4]
    candidate = pathlib.Path(raw)
    if candidate.exists():
        raw = candidate.read_text(encoding='utf-8-sig')
    for row, value in json.loads(raw).items():
        cb[6][int(row)] = list(value) + [0.0] * (4 - len(value))

# ------------------------------------------------------------------- resources
base = rng.uniform(0.05, 0.95, size=4)
mask = rng.uniform(0.05, 0.95, size=4)
ramp = rng.uniform(0.0, 1.0, size=4)


def shadow_lut(index):
    return np.array([0.9, 0.9, 0.9, 0.9])


textures = {0: shadow_lut, 1: base, 2: mask, 3: ramp}

normal = np.array([0.2, 0.3, 0.93])
normal /= np.linalg.norm(normal)
v = {i: np.zeros(4) for i in range(8)}
v[1] = list(normal) + [1.0]
v[2] = [0.0, 0.37, 0.42, 0.2]        # vertex colour: y index, z region, w flag
v[3][:2] = [0.31, 0.62]
v[6] = [0.12, 1.35, -0.4, 1.0]       # world position + clip w
v[7] = [640.0, 360.0, 0.5, 0.002]

interp = Interpreter(cb, v, textures)
interp.r[0] = [1.0, 1.0, 1.0, 0.0]
interp.r[1] = [0.0, 0.0, 0.0, 0.0]
interp.r[2] = [0.0, 0.0, 0.0, 0.0]
interp.run(block)

print('discarded   :', interp.discarded)
print('o0.xyz      :', interp.r[0, :3] if False else interp.r[0, :3])
print('r0 (final)  :', interp.r[0])
print('r1 (final)  :', interp.r[1])
print('r3 (final)  :', interp.r[3])
print('r5 (ramp)   :', interp.r[5])
print('r4 (light)  :', interp.r[4])
print('r2 (final)  :', interp.r[2])
print('r6 (final)  :', interp.r[6])
print('r7 (final)  :', interp.r[7])
