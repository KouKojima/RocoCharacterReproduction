"""Runtime constant state for the pet (PetBase) material family.

The cooked pet materials read three constant buffers that the kit's material
extractor does not reproduce:

  * cb2/cb3/cb4/cb5 hold per-primitive and scene data (light vector, shadow
    LUT, ramp width, ramp contrast, vertex-colour region colours ...),
  * several cb6 rows are derived from the material's *dynamic* switch
    parameters, whose cooked value is 0 (the game flips them at runtime).

Those values are preview inputs here, exactly like the studio light direction
and shadow that the kit already treats as preview inputs for the humanoid
characters. `build_runtime` assembles them into the constant buffers the DXBC
interpreter expects, so the recovered kernel and the original program can be
compared with identical inputs.
"""
from __future__ import annotations

import numpy as np

IMMEDIATE_CONSTANT_BLOCK = np.array(
    [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
        [0.0, 0.750000, 0.125000, 0.937500],
        [0.500000, 0.250000, 0.687500, 0.437500],
        [0.187500, 0.875000, 0.062500, 0.812500],
        [0.625000, 0.375000, 0.562500, 0.312500],
    ],
    dtype=np.float64,
)


def build_runtime(material_rows,
                  light_vector=(0.35, -0.55, 0.75),
                  ambient_color=(0.18, 0.20, 0.26),
                  shadow_value=1.0,
                  ramp_width=1.0,
                  ramp_contrast=0.5,
                  ramp_tint=(1.0, 1.0, 1.0),
                  ramp_blend=0.0,
                  ramp_floor=1.0,
                  spec_scale=0.0,
                  spec_tint=(1.0, 1.0, 1.0),
                  base_mix=0.0,
                  output_scale=1.0,
                  shadow_bias=0.0,
                  region_colors=None,
                  diffuse_mix=1.0,
                  final_tint=(1.0, 1.0, 1.0),
                  light_offset=0.0,
                  frame=0.0,
                  eye_brightness=1.0,
                  eye_color=(5.0, 0.0, 0.357563),
                  outline_base=(0.014444, 0.005605, 0.035601),
                  outline_alt=(1.0, 1.0, 1.0),
                  outline_width=1.0,
                  outline_fresnel=(0.0, 1.0),
                  outline_curve=(1.0, 1.0, 1.0),
                  outline_mask=0.0):
    """Assemble cb0..cb6 for the pet material programs.

    `material_rows` is the evaluated cb6 block of the material permutation.
    """
    cb = {i: np.zeros((300, 4)) for i in range(7)}
    cb[6][:len(material_rows)] = material_rows

    light = np.array(light_vector, dtype=np.float64)
    ambient = np.array(ambient_color, dtype=np.float64)

    # cb0 - global / view block
    cb[0][23] = [0.0, 0.0, 0.0, 0.0]          # camera origin (fresnel only)
    cb[0][75] = [0.0, 0.0, 0.0, 0.0]
    cb[0][79] = [0.0, frame, 0.0, 0.0]         # frame counter
    cb[0][138] = [0.0, 0.0, 0.0, 0.0]         # viewport origin
    cb[0][139] = [0.0, 0.0, 0.0, 0.0]
    cb[0][145] = [0.0, output_scale, 0.0, 0.0]
    cb[0][147] = [0.0, 0.0, 0.0, 1.0]         # albedo remap: scale + offset
    cb[0][153] = [0.0, 0.0, 0.0, 0.0]
    cb[0][156] = [0.0, base_mix, 0.0, 0.0]
    cb[0][199] = list(ambient) + [0.0]
    cb[0][294] = [0.0, 1.0, 0.0, 1.0]         # shadow depth bias / scale
    # cb1 - view block
    cb[1][75] = [0.0, 0.0, 0.0, 0.0]
    cb[1][79] = [0.0, 0.0, 1.0, 1.0]          # fog
    cb[1][139] = [0.0, 0.0, 0.0, 0.0]
    # cb2 - scene / bone block
    for row in (0, 1, 2, 8, 15):
        cb[2][row] = list(light) + [0.0]
    cb[2][3] = [0.0, 0.0, 0.0, 0.0]
    cb[2][4] = [1.0, 1.0, 1.0, 1.0]
    cb[2][51] = [0.0, 0.0, 0.0, 0.0]
    # cb3 - material block of the outline shader / misc in the body shader
    cb[3][0] = [1.0, 0.0, 0.0, 0.0]
    cb[3][1] = [0.0, 1.0, 0.0, 0.0]
    cb[3][23] = [0.0, 0.0, 0.0, 0.0]
    cb[3][30] = [0.0, 0.0, 0.0, 0.0]
    # cb4 - per primitive block
    cb[4][1] = [0.0, 0.0, ramp_blend, ramp_floor]
    cb[4][2] = [ramp_width, 0.0, light_offset, 0.0]
    cb[4][12] = [0.0, spec_scale, 0.0, shadow_bias]
    cb[4][13] = list(light) + [float(np.dot(light, [0.375, 0.5, 0.125]))]
    cb[4][14] = list(light) + [1.0]
    cb[4][15] = list(spec_tint) + [0.0]
    # cb5
    cb[5][2] = [0.0, 0.0, ramp_contrast, 0.0]
    return cb


def apply_material_overrides(cb, overrides):
    """Apply `{'32': [r,g,b]}` style overrides to the cb6 block."""
    for row, value in overrides.items():
        values = list(value) + [0.0] * (4 - len(value))
        cb[6][int(row)] = values
    return cb
