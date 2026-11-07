"""Decode a material's uniform preshader bytecode so each cb6 row can be named."""
import base64
import json
import pathlib
import struct
import sys

SHADERS = pathlib.Path(sys.argv[1])
PREFIX = sys.argv[2]
WANT = [int(x) for x in sys.argv[3:]] if len(sys.argv) > 3 else None

uniforms = json.loads((SHADERS / (PREFIX + '-uniforms.json')).read_text(encoding='utf8'))
data = base64.b64decode(uniforms['UniformPreshaderData']['Data'])

vparams = uniforms['UniformVectorParameters']
sparams = uniforms['UniformScalarParameters']


def vname(i):
    return vparams[i]['ParameterInfo']['Name'] if i < len(vparams) else 'v#%d' % i


def sname(i):
    return sparams[i]['ParameterInfo']['Name'] if i < len(sparams) else 's#%d' % i


def splitargs(s):
    out = []
    depth = 0
    start = 0
    for i, c in enumerate(s):
        if c == '(':
            depth += 1
        if c == ')':
            depth -= 1
        if c == ',' and depth == 0:
            out.append(s[start:i].strip())
            start = i + 1
    return out + [s[start:].strip()]


def describe(code):
    pos = 0
    stack = []
    while pos < len(code):
        op = code[pos]
        pos += 1
        if op == 1:
            stack.append('zero')
        elif op == 2:
            stack.append('lit(%s)' % list(struct.unpack_from('<4f', code, pos)))
            pos += 16
        elif op in (3, 4):
            i = struct.unpack_from('<H', code, pos)[0]
            pos += 2
            stack.append(('scalar ' if op == 3 else 'vector ') + (sname(i) if op == 3 else vname(i)))
        elif op in (5, 6, 7, 8, 9, 10, 11):
            y = stack.pop()
            x = stack.pop()
            stack.append('(%s %s %s)' % (x, {5: '+', 6: '-', 7: '*', 8: '/', 9: 'fmod', 10: 'min', 11: 'max'}[op], y))
        elif op == 20:
            typ = code[pos]
            pos += 1
            y = stack.pop()
            x = stack.pop()
            n = 4 if typ >= 8 else 3 if typ >= 4 else 2 if typ >= 2 else 1
            stack.append('dot%d(%s,%s)' % (n, x, y))
        elif op in (22, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34):
            x = stack.pop()
            stack.append('%s(%s)' % ({22: 'sqrt', 24: 'saturate', 25: 'abs', 26: 'floor', 27: 'ceil',
                                     28: 'round', 29: 'trunc', 30: 'sign', 31: 'frac',
                                     33: 'log2', 34: 'log10'}[op], x))
        elif op == 35:
            n = code[pos]
            ids = code[pos + 1:pos + 5]
            pos += 5
            x = stack.pop()
            stack.append('swizzle(%s)' % x)
        elif op == 36:
            n = code[pos]
            pos += 1
            y = stack.pop()
            x = stack.pop()
            stack.append('concat(%s,%s)' % (x, y))
        else:
            stack.append('?op%d' % op)
    return stack[-1] if stack else '?'


print('--- vector preshaders (cb6 row -> expression) ---')
for i, h in enumerate(uniforms['UniformVectorPreshaders']):
    if WANT is not None and i not in WANT:
        continue
    code = data[h['OpcodeOffset']:h['OpcodeOffset'] + h['OpcodeSize']]
    print('  cb6[%2d]  %s' % (i, describe(code)))

print()
print('--- scalar preshaders (packed cb6 row -> expression) ---')
for i, h in enumerate(uniforms['UniformScalarPreshaders']):
    if WANT is not None and i not in WANT:
        continue
    code = data[h['OpcodeOffset']:h['OpcodeOffset'] + h['OpcodeSize']]
    print('  s[%2d] -> cb6[%2d].%s  %s' % (i, len(uniforms['UniformVectorPreshaders']) + i // 4,
                                            'xyzw'[i % 4], describe(code)))
