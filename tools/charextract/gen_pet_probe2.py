"""Instruction level bisect for the pet pixel programs.

For every instruction count the tool emits a probe shader that runs the first
`count` instructions of the transpiled program and writes r0..r3 into the four
pixels of a 4x1 target.  The expected register values come from the DXBC
interpreter stopped at the same instruction, so the browser can report the
first instruction at which the GLSL port and the original program disagree.

Only instruction counts that do not cut a branch in half are used: the
interpreter scans for the matching `endif`, so a truncated branch would make
its expected values meaningless.
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
from pet_programs import PROGRAMS, HEADER, build_textures, build_vertex_registers, json_safe  # noqa: E402

SHADERS = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
SAMPLES = pathlib.Path(sys.argv[3])
KEY = sys.argv[4]
SAMPLE_COUNT = int(sys.argv[5]) if len(sys.argv) > 5 else 8

spec = PROGRAMS[KEY]
asm_path = SHADERS / (spec['file'] + '.asm')
lines = asm_path.read_text(encoding='utf8').splitlines()
ops = parse_block(lines)

context = Context(spec['material'], spec['vmap'], spec['tmap'])
transpiler = Transpiler(context)
transpiler.emit(ops)

# the interpreter consumes the instruction text, the transpiler the parsed form
op_lines = [op + ' ' + ', '.join(args) for op, args in ops]

header = HEADER % {'title': 'probe-' + KEY, 'prefix': spec['prefix'], 'file': spec['file']}
for name in sorted(transpiler.used_uniforms):
    if name.startswith('uCb'):
        header += 'uniform vec4 %s;\n' % name

# branch depth after every instruction: a probe may only stop where no branch
# is open, otherwise the interpreter cannot know where the branch ends.
depth = 0
depths = []
for op, _ in ops:
    if op.startswith('if_nz') or op.startswith('if_c'):
        depths.append(depth)
        depth += 1
        continue
    if op == 'endif':
        depth -= 1
        depths.append(depth)
        continue
    depths.append(depth)

data = json.loads(SAMPLES.read_text(encoding='utf8'))
samples = data['programs'][KEY]['samples'][:SAMPLE_COUNT]


def state_from_sample(sample):
    cb = {i: np.zeros((300, 4)) for i in range(7)}
    for name, value in sample['uniforms'].items():
        if name.startswith('uCb'):
            register, row = name[3:].split('_')
            cb[int(register)][int(row)] = np.asarray(value, dtype=np.float64)
    u_mat = sample['uniforms']['uMat']
    cb[int(spec['material'][2:])][:len(u_mat)] = np.asarray(u_mat, dtype=np.float64)
    inputs = sample['inputs']
    v = build_vertex_registers(spec['vmap'], inputs)
    textures = build_textures(spec['tmap'], sample['textures'])
    return cb, v, textures


PROBE_TAIL = """
  int ix = int(gl_FragCoord.x);
  vec4 pv = r0;
  if (ix == 1) pv = r1;
  else if (ix == 2) pv = r2;
  else if (ix == 3) pv = r3;
  outColor = pv;
"""

OUT.mkdir(parents=True, exist_ok=True)
report = {
    'key': KEY,
    'total': len(ops),
    'ops': [' '.join([op] + list(args)) for op, args in ops],
    'probes': {},
}
for count in range(1, len(ops) + 1):
    if depths[count - 1] != 0:
        continue
    body = transpiler.emit_range(ops, 0, count)
    body = body.replace('discard;', ';')
    source = header + '\nvoid main(){\n' + body + PROBE_TAIL + '}\n'
    name = 'pet-probe2-%s-%03d.glsl' % (KEY, count)
    (OUT / name).write_text(source, encoding='utf8')

    expected = []
    for sample in samples:
        cb, v, textures = state_from_sample(sample)
        interp = Interpreter(cb, v, textures, immediate=IMMEDIATE_CONSTANT_BLOCK)
        interp.r[0] = [1.0, 1.0, 1.0, 0.0]
        interp.run(op_lines[:count])
        expected.append([[float(x) for x in interp.r[i]] for i in range(4)])
    report['probes'][str(count)] = {'glsl': name, 'expected': expected}

(OUT / ('pet-probe2-%s.json' % KEY)).write_text(json.dumps(json_safe(report), ensure_ascii=False), encoding='utf8')
print('wrote %s probes for %s' % (len(report['probes']), KEY))
print('wrote', OUT / ('pet-probe2-%s.json' % KEY))
