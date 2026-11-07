"""Show the vector/scalar preshader order of a cooked material so the cb6 row mapping is auditable."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from material_preshaders import evaluate_uniforms  # noqa: E402

SHADERS = pathlib.Path(sys.argv[1])
PREFIX = sys.argv[2]

uniforms = json.loads((SHADERS / (PREFIX + '-uniforms.json')).read_text(encoding='utf8'))
evaluated = evaluate_uniforms(uniforms, [{}, {}, {}])

vparams = uniforms['UniformVectorParameters']
sparams = uniforms['UniformScalarParameters']
nv = len(uniforms['UniformVectorPreshaders'])
ns = len(uniforms['UniformScalarPreshaders'])

print('--- vector preshader index -> cb6 row (evaluated) ---')
for i in range(nv):
    name = vparams[i]['ParameterInfo']['Name'] if i < len(vparams) else '<expr>'
    row = evaluated['buffer'][i]
    print('  cb6[%2d]  %-24s %s' % (i, name, row))

print()
print('--- scalar preshader index -> packed cb6 row ---')
base = nv
for i in range(ns):
    row = base + i // 4
    comp = 'xyzw'[i % 4]
    name = sparams[i]['ParameterInfo']['Name'] if i < len(sparams) else '<expr>'
    print('  cb6[%2d].%s  %-24s %s' % (row, comp, name, evaluated['buffer'][row][i % 4]))
