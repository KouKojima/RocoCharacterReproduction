"""Recovered numpy kernel for the pet (PetBase) material family.

Each function mirrors the corresponding original DXBC program instruction for
instruction, so the result can be compared against the original program with
`validate_pet_port.py`. Constant-buffer reads use the same indices as the
DXBC: `cb6` holds the evaluated material rows, `cb0`/`cb2`/`cb3`/`cb4`/`cb5`
hold the runtime state assembled by `pet_runtime.build_runtime`.
"""
from __future__ import annotations

import numpy as np

F32 = np.float32
LUMA = np.array([0.375, 0.500, 0.125])
DIFFUSE_LUMA = np.array([0.300, 0.590, 0.110])


def sat(x):
    x = np.asarray(x, dtype=np.float64)
    with np.errstate(invalid='ignore'):
        out = np.clip(x, 0.0, 1.0)
    return np.where(np.isnan(out), 0.0, out)


def div_sat(x, y):
    # IEEE division: a zero denominator gives +/-inf (0/0 gives NaN) and the
    # saturate then clamps it, exactly like the original program.
    with np.errstate(divide='ignore', invalid='ignore'):
        q = x / y
    return sat(q)


def bit_and(a, b):
    bits = (np.asarray(a, dtype=F32).view(np.uint32) & np.asarray(b, dtype=F32).view(np.uint32))
    return bits.view(np.float32).astype(np.float64)


def round_ni(x):
    return np.floor(np.asarray(x, dtype=np.float64) + 0.5)


def round_ne_flag(x):
    x = np.asarray(x, dtype=np.float64)
    return np.where(np.round(x) != x, 1.0, 0.0)


def inverse_tone(c):
    """The engine's inverse tone curve, identical in the humanoid and pet kernels."""
    c = np.asarray(c, dtype=np.float64)
    return (0.047 - 0.56 * c - np.sqrt(np.maximum(-0.2072 * c * c + 0.70896 * c + 0.002209, 0.0))) / (1.86 * c - 2.72)


# --------------------------------------------------------------------- body
def body_surface(m, cb, normal, vertex_color, uv, world_pos, screen_pos, clip_w,
                 base_tex, mask_tex, ramp_tex, immediate):
    """MI_Lig_YiLiSi3_001_By / _By1 BasePass pixel program."""
    m = np.asarray(m, dtype=np.float64)
    normal = np.asarray(normal, dtype=np.float64)
    vc = np.asarray(vertex_color, dtype=np.float64)
    world_pos = np.asarray(world_pos, dtype=np.float64)
    screen_pos = np.asarray(screen_pos, dtype=np.float64)

    # --- 59..77 region selection and the stochastic cut-out weight ---------
    lt4 = np.array([vc[2] < t for t in (0.9, 0.7, 0.5, 0.3)], dtype=np.float64)
    region = m[33][1]
    region = m[33][2] if lt4[0] else region
    region = m[33][3] if lt4[1] else region
    region = m[34][0] if lt4[2] else region
    region = m[34][1] if lt4[3] else region
    region = m[34][2] if vc[2] < 0.1 else region
    region = max(region, 1.0)
    r0x = round_ne_flag(region)
    idx = round_ni(vc[1] * 10.0)
    r0x = r0x - idx
    r0x = 1.0 if 1e-5 < abs(r0x) else 0.0
    r0y = 0.0 if r0x else 1.0
    r0z = 1.0 if vc[3] >= 0.8 else 0.0
    r0w = 1.0 if 0.9 >= vc[3] else 0.0
    r0x = bit_and(r0x, 1.0)
    r0z = bit_and(r0z, 1.0)
    r0w = bit_and(r0w, 1.0)
    r0z = 1.0 - r0z * r0w
    r0x = r0z * r0x + r0y

    # --- 78..91 view fresnel ---------------------------------------------
    r0y = round_ni(cb[0][79][3] + 0.1)
    inv_p2 = 1.0 / max(float(np.dot(world_pos, world_pos)), 1e-30)
    r1_xyz = -world_pos * inv_p2
    r2_xyz = world_pos * inv_p2 - cb[0][23][:3]
    r0_yzw = r0y * r2_xyz + r1_xyz
    fresnel = sat(float(np.dot(normal, r0_yzw)))
    fresnel = 1.0 - fresnel
    fresnel = max(fresnel, 1e-4)
    fresnel = np.exp(np.log(fresnel) * m[34][3])
    fresnel = fresnel * m[35][0]

    # --- 92..104 rim / emissive accumulation ------------------------------
    rim = fresnel * m[5][:3]
    rim = rim * m[35][1]
    r1x = m[35][2] - 1.0
    r1x = m[35][1] * r1x + 1.0
    r1y = fresnel * r1x - 0.99
    r1y = sat(r1y * 100.000099)
    r1z = r1y * (-2.0) + 3.0
    r1y = r1y * r1y * r1z
    r1_spec = r1y * m[6][:3] * m[35][3]
    r0_yzw = r0_yzw * r1x - r1_spec
    r0_yzw = m[36][0] * r0_yzw + r1_spec

    # --- 105..112 base colour sample --------------------------------------
    tex1 = np.asarray(base_tex, dtype=np.float64)
    alpha = sat((tex1[3] - 0.04) * 1.111100)
    r0_yzw = m[9][:3] * alpha + r0_yzw
    r2_xyz = alpha * m[2][:3]
    r2_xyz = r2_xyz * m[33][0] + r0_yzw
    r0x = max(0.0, r0x)
    r0x = min(r0x, 1.0)

    # --- 113..121 stochastic clip -----------------------------------------
    # `ftoi` truncates towards zero, it does not floor.
    screen = np.trunc(screen_pos[:2] - cb[0][138][:2]).astype(np.int64)
    ix = int(screen[0]) & 3
    iy = int(screen[1]) & 3
    dither = float(np.dot(immediate[iy + 4], immediate[ix]))
    gate = 1.0 if m[40][3] >= dither else 0.0
    r0x = r0x * gate - 0.333300
    discard = r0x < 0.0

    # --- 122..138 albedo and specular tint --------------------------------
    c = tex1[:3]
    sq = c * c
    disc = np.sqrt(np.maximum(-0.207200 * sq + 0.708960 * c + 0.002209, 0.0))
    num = 0.047000 - 0.560000 * c
    den = (0.930000 * c - 1.360000) * 2.0
    albedo = (num - disc) / den
    albedo = m[36][3] * (-albedo) + albedo
    luma = float(np.dot(albedo, DIFFUSE_LUMA))
    r1x = sat(cb[4][12][1])
    r1_yzw = albedo * (1.0 - r1x)
    albedo = sat(albedo)
    spec_tint = luma * r1x + r1_yzw

    # --- 139..146 geometric normal and light direction ---------------------
    geo = normal / max(float(np.linalg.norm(normal)), 1e-30)
    flag = bit_and(cb[2][51][0], cb[3][23][3])
    r4_xyz = cb[2][8][:3] if flag else cb[4][14][:3]
    flag2 = 1.0 if 0.5 >= cb[4][14][3] else 0.0
    r4_xyz = r4_xyz if flag2 else cb[4][14][:3]
    ndotl = float(np.dot(geo, r4_xyz))

    # --- 147..164 mask light channel and the ambient floor -----------------
    mask = np.asarray(mask_tex, dtype=np.float64)
    m_b = sat(mask[2])
    m_a = sat(mask[3])
    light_amount = ndotl * 0.5 + m_b
    light_amount = (light_amount + 0.5) * 0.5
    light_amount = 1.0 if 0.95 < m_b else light_amount
    albedo = albedo * (1.0 - m_a)
    albedo = albedo * cb[0][147][3] + cb[0][147][:3]
    light_amount = 0.0 if m_b < 0.05 else light_amount
    step = div_sat(light_amount - m[15][0], m[15][1] * 0.1)
    floor_value = 1.0 - sat(m[15][0] - light_amount)
    light_amount = step * (1.0 - floor_value) + floor_value

    # --- 165..179 shadow and the direct light amount -----------------------
    shadow = sat((clip_w * 1e-5 - cb[0][294][2]) / cb[0][294][3])
    shadow = shadow * shadow * (shadow * (-2.0) + 3.0)
    shadow = shadow * (cb[0][294][1] - 1.0) + 1.0
    r4_xyz = shadow * cb[2][0][:3]
    r4_xyz = r4_xyz if flag else cb[4][13][:3]
    r4_w = float(np.dot(r4_xyz, LUMA))
    r4_xyz = r4_xyz if flag2 else cb[4][13][:3]
    r4_w = r4_w if flag2 else cb[4][13][3]
    direct = sat(r4_w + r4_w)
    ramp_amount = direct * light_amount
    direct = direct * step

    # --- 180..188 shadow LUT -----------------------------------------------
    # The cooked asset carries no shadow LUT, so the buffer read returns 1.
    # The flag only selects between that value and 1 - it is not a factor of
    # the direct light amount.
    lut_value = 1.0
    lut_flag = 1.0 if 1e-5 < abs(cb[3][30][0] - 0.5) else 0.0
    if not lut_flag:
        lut_value = 1.0
    lut_value = sat(lut_value + cb[4][12][3])
    ramp_amount = ramp_amount * lut_value

    # --- 189..198 ramp lookup ----------------------------------------------
    ramp_width = sat(cb[4][2][0])
    ramp_u = ramp_amount * ramp_width
    ramp = np.asarray(ramp_tex, dtype=np.float64)[:3]
    contrast = 1.0 - abs((cb[5][2][2] - 0.5) * 2.0)
    ramp = ramp * 0.85 + contrast * ramp * 0.15
    inv_ramp = 1.0 - ramp

    # --- 200..217 toon colour ----------------------------------------------
    direct = direct * lut_value * ramp_width
    toon = direct * inv_ramp + ramp
    tint = -cb[0][199][:3] + cb[4][15][:3]
    tint = cb[4][15][3] * tint + cb[0][199][:3]
    toon = toon - tint
    ramp_blend = sat(cb[4][1][2])
    toon = ramp_blend * toon + tint
    toon = spec_tint * toon
    floor_mix = 1.0 - cb[4][1][3]
    floor_mix = light_amount * floor_mix + cb[4][1][3]
    toon = floor_mix * toon
    light_tint = direct * spec_tint
    light_offset = min(cb[4][2][2] * m[38][3], 0.0)
    r4_xyz = r4_xyz + light_offset
    toon = light_tint * r4_xyz + toon
    colour = light_offset * tex1[:3] + toon

    # --- 218..233 specular tint and the final composition ------------------
    r3 = m[12][:3] - r2_xyz
    r2_xyz = m[36][3] * r3 + r2_xyz
    r3 = m[13][:3] - r2_xyz
    r2_xyz = m[37][0] * r3 + r2_xyz
    r2_xyz = np.maximum(r2_xyz, 0.0)
    r3 = r2_xyz * direct - r2_xyz
    r3 = r3 * m[29][1]
    r2_xyz = m[29][0] * r3 + r2_xyz
    colour = colour + r2_xyz
    colour = shadow * colour
    colour = np.maximum(colour, 0.0)
    colour = np.minimum(colour, 100.0)
    final = albedo - colour
    final = cb[0][156][1] * final + colour
    final = final * cb[0][145][1]
    final = final * m[32][:3]
    if cb[1][79][3] < 1.0:
        final = np.sqrt(np.maximum(final * cb[1][79][3], 0.0))
    return final, discard
