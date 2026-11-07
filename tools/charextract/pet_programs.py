"""The four pet (PetBase) BasePass programs and the shared GLSL header.

Kept in its own module so the generator, the sample builder and the probe
builder all agree on the register mapping without importing each other.
"""
from __future__ import annotations

import numpy as np

PROGRAMS = {
    'body': {
        'prefix': 'MI_Lig_YiLiSi3_001_By-4D1367FB',
        'file': 'shader-b179fd5f54d35cfe731f727d92d891067dd8ee40',
        'material': 'cb6',
        'vmap': {'v1': 'pNormal', 'v2': 'pColor', 'v3': 'pUv', 'v6': 'pWorld', 'v7': 'pScreen'},
        'tmap': {0: 'uShadowLut', 1: 'uBase', 2: 'uMask', 3: 'uRamp'},
        'name': 'petBodySurface',
    },
    'body1': {
        'prefix': 'MI_Lig_YiLiSi3_001_By1-06D885F4',
        'file': 'shader-178d69e20ecb502d686597128d875b656faa3237',
        'material': 'cb6',
        'vmap': {'v1': 'pNormal', 'v2': 'pUv', 'v5': 'pWorld', 'v6': 'pScreen'},
        'tmap': {0: 'uShadowLut', 1: 'uBase', 2: 'uMask', 3: 'uRamp'},
        'name': 'petBody1Surface',
    },
    'eyes': {
        'prefix': 'MI_Lig_YiLiSi3_001_Es-249B0820',
        'file': 'shader-c45322fd9687ce878361fc55adf70961d3788ee7',
        'material': 'cb6',
        'vmap': {'v1': 'pNormal', 'v2': 'pColor', 'v3': 'pUv', 'v6': 'pWorld', 'v7': 'pScreen'},
        'tmap': {0: 'uShadowLut', 1: 'uEyeAtlas'},
        'name': 'petEyeSurface',
    },
    'outline': {
        'prefix': 'MI_Lig_YiLiSi3_001_By_Ol-2AECB4DE',
        'file': 'shader-f83ebd021113dc4b50c3e9cb16916e88c342d7cb',
        'material': 'cb3',
        'vmap': {'v1': 'pNormal', 'v2': 'pColor', 'v3': 'pUv', 'v5': 'pOutlineWidth',
                 'v6': 'pWorld', 'v7': 'pScreen'},
        'tmap': {0: 'uOutlineMask'},
        'name': 'petOutlineSurface',
    },
}

# The engine semantics a preview input feeds, per GLSL input name.
INPUT_SEMANTICS = {
    'pNormal': 'vNormal',
    'pColor': 'vColor',
    'pUv': 'vUv',
    'pWorld': 'vWorldPosition',
    'pScreen': 'vScreen',
    'pOutlineWidth': 'vOutlineWidth',
}


def build_vertex_registers(vmap, inputs):
    """The `v` registers of a DXBC program, following the program's own map.

    Every pet program binds the engine semantics to different v registers
    (the body reads the world position from v6, body1 from v5), so the sample
    data has to be routed through the map instead of a fixed layout.
    """
    v = {i: np.zeros(4) for i in range(8)}
    for reg, semantic in vmap.items():
        index = int(reg[1:])
        name = INPUT_SEMANTICS.get(semantic)
        if name is None or name not in inputs:
            continue
        value = [float(x) for x in inputs[name]]
        if semantic == 'pNormal':
            value = value + [1.0]
        elif semantic == 'pUv':
            value = value + [0.0, 0.0]
        elif semantic == 'pWorld':
            value = value + [0.0]
        v[index][:len(value[:4])] = value[:4]
    return v


def build_textures(tmap, sample_textures):
    """The texture register values of a DXBC program, following its own map.

    The eye program reads t1 as the eye atlas while the body program reads t1
    as the base colour, so the values have to follow the program's map.
    """
    textures = {}
    for slot, name in tmap.items():
        if name == 'uShadowLut':
            # The cooked asset carries no shadow LUT: the interpreter reads a
            # constant 1, the GLSL port reads the uShadowLut uniform.
            textures[slot] = lambda i: np.array([1.0, 1.0, 1.0, 1.0])
        else:
            textures[slot] = np.asarray(sample_textures[name], dtype=np.float64)
    return textures


def json_safe(value):
    """Replace non-finite floats with strings.

    JSON has no NaN or Infinity literal: `json.dumps` writes them anyway and
    the browser's JSON.parse rejects the whole file. The preview data keeps
    them as the strings 'nan', 'inf' and '-inf'.
    """
    import math
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float):
        if math.isnan(value):
            return 'nan'
        if math.isinf(value):
            return 'inf' if value > 0 else '-inf'
    return value

HEADER = """// Generated from the cooked DXBC of %(title)s.
// Resource %(prefix)s, program %(file)s.
// Not original source: a mechanical transpilation of the original program,
// checked against the original program by tools/charextract/validate_pet_port.py.
precision highp float;
precision highp int;
#define texture2D texture
uniform vec4 uMat[64];
uniform sampler2D uBase;
uniform sampler2D uMask;
uniform sampler2D uRamp;
uniform sampler2D uEyeAtlas;
uniform sampler2D uOutlineMask;
uniform vec4 uShadowLut;
in vec4 pNormal;
in vec4 pColor;
in vec4 pUv;
in vec4 pWorld;
in vec4 pScreen;
in vec4 pOutlineWidth;
layout(location = 0) out vec4 outColor;
layout(location = 1) out float outAux;
// the interpreter starts with r0 = (1,1,1,0) and every other register at zero;
// the same initialisation keeps the GLSL registers comparable instruction by
// instruction (a shader global would otherwise be undefined).
vec4 r0=vec4(1.0,1.0,1.0,0.0),r1=vec4(0.0),r2=vec4(0.0),r3=vec4(0.0),r4=vec4(0.0),r5=vec4(0.0),r6=vec4(0.0),r7=vec4(0.0),r8=vec4(0.0),r9=vec4(0.0),r10=vec4(0.0),r11=vec4(0.0),r12=vec4(0.0),r13=vec4(0.0),r14=vec4(0.0),r15=vec4(0.0);
const vec4 icbRows[8]=vec4[8](vec4(1.0,0.0,0.0,0.0),vec4(0.0,1.0,0.0,0.0),vec4(0.0,0.0,1.0,0.0),
  vec4(0.0,0.0,0.0,1.0),vec4(0.0,0.75,0.125,0.9375),vec4(0.5,0.25,0.6875,0.4375),
  vec4(0.1875,0.875,0.0625,0.8125),vec4(0.625,0.375,0.5625,0.3125));
"""
