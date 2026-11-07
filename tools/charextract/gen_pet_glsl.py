"""Generate the preview GLSL for the pet (PetBase) material programs.

Each cooked BasePass pixel program is transpiled from its DXBC into GLSL and
written next to the preview sources together with a manifest of the runtime
constant values the shader needs. The values come from
`pet_runtime.build_runtime`, the same helper the DXBC interpreter validation
uses, so the shader and the original program see identical inputs.

Two forms are written per program:

  pet-<key>.glsl      the standalone shader used by the validation harnesses
  pet-<key>-lib.glsl  the same program as a library: the inputs become
                      globals, the colour output becomes `petOut` and the body
                      becomes `petMain()`, so the preview can feed its own
                      varyings and wrap the recovered program.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dxbc_glsl import Context, Transpiler, parse_block  # noqa: E402
from pet_runtime import build_runtime  # noqa: E402
from pet_programs import PROGRAMS, HEADER  # noqa: E402

SHADERS = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

LIBRARY_INPUTS = ('pNormal', 'pColor', 'pUv', 'pWorld', 'pScreen', 'pOutlineWidth')


def library_form(source: str) -> str:
    """Turn the standalone shader into a library the preview can call."""
    out = source
    out = out.replace('void main(){', 'void petMain(){')
    for name in LIBRARY_INPUTS:
        out = out.replace('in vec4 %s;\n' % name, 'vec4 %s;\n' % name)
    out = out.replace('layout(location = 0) out vec4 outColor;\n', '')
    out = out.replace('layout(location = 1) out float outAux;\n', '')
    out = out.replace('outColor', 'petOut').replace('outAux', 'petAux')
    out = out.replace('void petMain(){', 'vec4 petOut;\nfloat petAux;\nvoid petMain(){')
    return out


manifest = {}
for key, spec in PROGRAMS.items():
    lines = (SHADERS / (spec['file'] + '.asm')).read_text(encoding='utf8').splitlines()
    ops = parse_block(lines)
    context = Context(spec['material'], spec['vmap'], spec['tmap'])
    transpiler = Transpiler(context)
    body = transpiler.emit(ops)
    material = json.loads((SHADERS / (spec['prefix'] + '-evaluated.json')).read_text(encoding='utf8'))['buffer']
    cb = build_runtime(material)
    uniforms = {}
    for name in sorted(transpiler.used_uniforms):
        if name.startswith('uCb'):
            register, row = name[3:].split('_')
            uniforms[name] = list(cb[int(register)][int(row)])
        elif name == 'uShadowLut':
            uniforms[name] = [1.0, 1.0, 1.0, 1.0]
    header = HEADER % {'title': key, 'prefix': spec['prefix'], 'file': spec['file']}
    for name, kind in sorted(transpiler.used_uniforms.items()):
        if name.startswith('uCb'):
            header += 'uniform vec4 %s;\n' % name
    source = header + '\nvoid main(){\n' + body + '\n}\n'
    (OUT / ('pet-%s.glsl' % key)).write_text(source, encoding='utf8')
    (OUT / ('pet-%s-lib.glsl' % key)).write_text(library_form(source), encoding='utf8')
    manifest[key] = {'prefix': spec['prefix'], 'file': spec['file'],
                     'uniforms': uniforms, 'material': material}
    print('generated pet-%s.glsl  (%d instructions, %d runtime uniforms)'
          % (key, len(ops), len(uniforms)))

(OUT / 'pet-runtime.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf8')
print('wrote', OUT / 'pet-runtime.json')
