"""Prepare the preview animation folder for a character that has no PoseAsset.

Local helper (not part of the handoff bundle). Some humanoids drive their face
with the bone-driven facial curve system instead of an additive PoseAsset:
their facial bones are addressed directly by curve name
(Bone_Chin_x_position, Bone_L_MeiMao01_z_rotation, ...) and the expression
curves (EyeBlink, BrowUp, LipTogether, ...) drive morph targets that live in
the skeletal mesh.

Those characters still own a curve-only TestData AnimSequence, so the original
curves are exported verbatim, but they cannot be mapped onto poses the way a
PoseAsset character can. The pose set is therefore empty and the mapping is
recorded as absent instead of borrowing another character's poses.
"""
from pathlib import Path
import argparse, json, shutil, hashlib, struct, math

LABELS = {
    'World_Idle': '待机', 'World_Idle_Relax_1': '休闲待机', 'World_Walk': '走路', 'World_Run': '跑步',
    'World_Hello_1': '打招呼', 'World_Greet_1': '问候', 'World_Happy_1': '开心动作', 'World_Happy_2': '开心动作 2',
    'World_Anger_1': '生气动作', 'World_Anger_2': '生气动作 2', 'World_Sad_1': '难过动作', 'World_Sad_2': '难过动作 2',
    'World_Shock_0': '惊讶动作', 'World_Shock_1': '惊讶动作', 'World_Fear_0': '害怕动作', 'World_Fear_1': '害怕动作 2',
    'World_Dialogue_1': '对话动作', 'World_Dialogue_2': '对话动作 2', 'World_Dialogue_3': '对话动作 3',
    'World_Dialogue_4': '对话动作 4', 'World_Crossarms': '抱臂', 'World_Crossarms_Start': '抱臂 开始',
    'World_Crossarms_Loop': '抱臂 循环', 'World_Crossarms_End': '抱臂 结束',
    'World_Crossarms_Gesture': '抱臂 手势', 'World_Crossarms_Gesture_Start': '抱臂 手势开始',
    'World_Crossarms_Gesture_Loop': '抱臂 手势循环', 'World_Crossarms_Gesture_End': '抱臂 手势结束',
    'World_HandOnchest': '抚胸', 'World_HandOnchest_Start': '抚胸 开始', 'World_HandOnchest_Loop': '抚胸 循环',
    'World_HandOnchest_End': '抚胸 结束', 'World_HandOnchin': '托腮', 'World_HandOnchin_Start': '托腮 开始',
    'World_HandOnchin_Loop': '托腮 循环', 'World_HandOnchin_End': '托腮 结束',
    'World_HandReach': '伸手', 'World_HandReach_Start': '伸手 开始', 'World_HandReach_Loop': '伸手 循环',
    'World_HandReach_End': '伸手 结束', 'World_HandSonhips': '叉腰', 'World_HandSonhips_Start': '叉腰 开始',
    'World_HandSonhips_Loop': '叉腰 循环', 'World_HandSonhips_End': '叉腰 结束',
    'World_Provoke': '挑衅', 'World_RolePlay_Command': '角色扮演 指令', 'World_RolePlay_Sad': '角色扮演 难过',
    'World_Think': '思考', 'World_Stun_Cough': '眩晕咳嗽', 'World_Stun_Shake': '眩晕摇晃',
    'World_Stun_Dialogue_1': '眩晕对话 1', 'World_Stun_Dialogue_2': '眩晕对话 2',
    'World_Jump_Fall': '跳跃下落', 'World_Fly_Start': '起飞', 'World_Fly_Hover': '悬停',
    'World_Fly_Gliding': '滑翔', 'World_Fly_Landing': '降落',
    'Fight_Start': '战斗准备', 'Fight_Start_2': '战斗准备 2', 'Fight_Start_3_1': '战斗准备 3-1',
    'Fight_Start_3_2': '战斗准备 3-2', 'Fight_Start_Show': '战斗登场', 'Fight_CallOut': '战斗呼喝',
    'Fight_Call_Back': '战斗回应', 'Fight_Command': '战斗指令', 'Fight_Lose': '战斗失败',
    'Fight_YingDui': '战斗应战', 'Fight_Attack_1': '战斗攻击 1', 'Fight_Attack_2': '战斗攻击 2',
    'Fight_Hit_1': '受击 1', 'Fight_Hit_2': '受击 2', 'Fight_Hit_3': '受击 3',
    'Fight_Die': '战败', 'Hurt': '受伤',
    'P_Eye_Close': '闭眼片段', 'P_Eye_Idle': '眼部：平静', 'P_Eye_Happy': '眼部：开心',
    'P_Eye_Anger': '眼部：生气', 'P_Eye_Sad': '眼部：难过', 'P_Eye_Shock': '眼部：惊讶',
    'KouXing_Idle': '口型：平静', 'KouXing_Happy': '口型：开心', 'KouXing_Anger': '口型：生气',
    'KouXing_Sad': '口型：难过', 'KouXing_Shock': '口型：惊讶',
    'Pos_LookBase': '注视：基础', 'Pos_LookDown': '注视：向下', 'Pos_LookUp': '注视：向上',
    'Pos_LookLeft': '注视：向左', 'Pos_LookRight': '注视：向右',
    'P_Idle': '表情：平静', 'P_Happy': '表情：开心', 'P_Anger': '表情：生气',
    'P_Sad': '表情：难过', 'P_Shock': '表情：惊讶',
    'P_KX_Idle': '嘴部姿势：平静', 'P_KX_Happy': '嘴部姿势：开心', 'P_KX_Anger': '嘴部姿势：生气',
    'P_KX_Sad': '嘴部姿势：难过', 'P_KX_Shock': '嘴部姿势：惊讶',
}

BODY_PREFIXES = ('World_', 'Fight_', 'MP01_', 'Ride_', 'Common_', 'Suits')
BODY_EXACT = ('Hurt',)


def decode_curves(root):
    """Decode the original curve-only TestData clip into the preview curve form."""
    runtime = root / 'animation-research' / 'facial-runtime'
    raw = json.loads((runtime / 'dialogue-curves.json').read_text(encoding='utf8'))
    payload = (runtime / 'dialogue-curves.bin').read_bytes()
    formats = ['empty', 'constant', 'linear', 'cubic', 'mixed', 'weighted']
    out = []
    for index, entry in enumerate(raw['curves']):
        curve = entry['FloatCurve']
        keys = curve['Keys']
        fmt, tfmt, pre, post, count, offset = struct.unpack_from('<BBBBii', payload, index * 12)
        assert keys and all(math.isfinite(k[field]) for k in keys for field in ('Time', 'Value', 'ArriveTangent', 'LeaveTangent'))
        assert all(a['Time'] <= b['Time'] for a, b in zip(keys, keys[1:]))
        out.append({
            'name': entry['CurveName'],
            'compression': formats[fmt],
            'timeCompression': 'uint16' if tfmt == 0 else 'float32',
            'interpolation': 'constant' if fmt <= 1 else 'cubic' if fmt == 3 else 'linear' if fmt == 2 else 'per-key',
            'keys': [[k['Time'], k['Value'], k['ArriveTangent'], k['LeaveTangent']] for k in keys],
            'minimumKeyValue': min(k['Value'] for k in keys),
            'maximumKeyValue': max(k['Value'] for k in keys),
        })
    mirrors = []
    by_name = {c['name']: c for c in out}
    for curve in out:
        if curve['name'].endswith('_Neg'):
            positive = by_name.get(curve['name'][:-4])
            if positive is None:
                continue
            negative = curve['keys']
            is_mirror = len(positive['keys']) == len(negative) and all(
                a[0] == b[0] and all(abs(a[i] + b[i]) < 1e-6 for i in (1, 2, 3))
                for a, b in zip(positive['keys'], negative))
            mirrors.append({'positive': curve['name'][:-4], 'negative': curve['name'], 'signedMirrors': is_mirror})
    return {
        'source': raw['path'],
        'sourceDuration': raw['duration'],
        'sourceFrames': raw['frames'],
        'kind': 'curve-only AnimSequence; no compressed bone tracks',
        'poseAsset': None,
        'poseMapping': 'absent: this character has no PoseAsset, so the curves address the facial bones by name and the expression curves drive morph targets; no pose index can be assigned',
        'curvePayloadSha256': hashlib.sha256(payload).hexdigest(),
        'keyColumns': ['timeSeconds', 'signedValue', 'arriveTangent', 'leaveTangent'],
        'extrapolation': 'constant before first key and after last key',
        'tangentWeights': 'none',
        'cubicEvaluation': 'For interval a,b: u=(t-a.time)/(b.time-a.time); h00*a.value+h10*dt*a.leaveTangent+h01*b.value+h11*dt*b.arriveTangent; h00=2u^3-3u^2+1,h10=u^3-2u^2+u,h01=-2u^3+3u^2,h11=u^3-u^2.',
        'warning': 'Original signed curve values. This character has no PoseAsset, so the preview records the curves but does not apply them: the native blend semantics of the bone-addressed facial curves and of the morph-target expression curves were not established and are not guessed.',
        'curves': out,
        'signedPairs': mirrors,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='character extraction root')
    options = parser.parse_args()
    root = options.data.resolve()
    src = root / 'animation-research' / 'native-animation'
    out = root / 'preview' / 'assets' / 'animation'
    out.mkdir(parents=True, exist_ok=True)

    for name in ('rig.json', 'skin.bin'):
        shutil.copy2(src / name, out / name)

    authored = decode_curves(root)
    (out / 'authored-curves.json').write_text(json.dumps(authored, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    (out / 'poses.json').write_text(json.dumps({'poses': []}, ensure_ascii=False, separators=(',', ':')), encoding='utf8')

    clips = []
    for animation in json.loads((src / 'animations.json').read_text(encoding='utf8')):
        if not animation.get('success'):
            continue
        assert animation.get('exportedPoseType') == 'full-local-pose', animation['name']
        shutil.copy2(src / animation['file'], out / animation['file'])
        label = LABELS.get(animation['name'])
        if label is None and animation['name'].startswith('TestData_'):
            label = '原版对话口型样例'
        name = animation['name']
        group = 'body' if name.startswith(BODY_PREFIXES) or name in BODY_EXACT else 'face'
        clips.append({k: animation.get(k) for k in ('name', 'path', 'file', 'frameCount', 'duration', 'sampleFPS',
                                                    'rateScale', 'boneCount', 'exportedPoseType', 'sourceAdditive',
                                                    'sourceRefPoseType', 'sourceRefFrameIndex', 'sourceRefSequence')}
                     | {'label': label or animation['name'],
                        'group': group,
                        'sha256': hashlib.sha256((src / animation['file']).read_bytes()).hexdigest()})

    rig = json.loads((src / 'rig.json').read_text(encoding='utf8'))
    character = json.loads((root / 'preview' / 'assets' / 'character.json').read_text(encoding='utf8'))
    mesh_name = Path(character.get('path', '')).stem or rig.get('meshPath', '').rsplit('/', 1)[-1].split('.')[0]
    meta = {
        'mesh': mesh_name,
        'boneCount': len(rig['bones']),
        'vertexCount': character.get('vertexCount'),
        'coordinates': 'raw UE centimeters, quaternion XYZW; converted at playback',
        'clips': clips,
        'poseCount': 0,
        'facialBoneIndices': [],
        'source': 'Native client ACL-decoded sequences; this character has no facial PoseAsset (its PA_ asset is a PhysicsAsset), so no pose set is exported',
        'facialCurves': {
            'count': len(authored['curves']),
            'duration': authored['sourceDuration'],
            'frames': authored['sourceFrames'],
            'source': authored['source'],
            'note': 'original curve-only clip, recorded verbatim; not applied by the preview',
        },
    }
    (out / 'manifest.json').write_text(json.dumps(meta, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    print('Prepared', len(clips), 'original clips, 0 poses,', len(authored['curves']), 'original facial curves for', mesh_name)


if __name__ == '__main__':
    main()
