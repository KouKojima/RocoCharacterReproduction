"""Dump the evaluated constant-buffer layout of a cooked material permutation."""
import json
import pathlib
import sys

SHADERS = pathlib.Path(sys.argv[1])
PREFIX = sys.argv[2]

uniforms = json.loads((SHADERS / (PREFIX + '-uniforms.json')).read_text(encoding='utf8'))
evaluated = json.loads((SHADERS / (PREFIX + '-evaluated.json')).read_text(encoding='utf8'))

nv = len(uniforms['UniformVectorPreshaders'])
ns = len(uniforms['UniformScalarPreshaders'])
print('vector preshaders   :', nv)
print('scalar preshaders   :', ns)
print('evaluated rows      :', len(evaluated['buffer']))
print()

print('--- vector parameters (name -> raw value) ---')
for name, value in evaluated['vector_parameters'].items():
    print('  %-24s %s' % (name, value))
print()
print('--- scalar parameters (name -> value) ---')
for name, value in evaluated['scalar_parameters'].items():
    print('  %-24s %s' % (name, value))
print()
print('--- evaluated buffer rows (index -> row) ---')
for i, row in enumerate(evaluated['buffer']):
    print('  cb6[%2d] = %s' % (i, row))
