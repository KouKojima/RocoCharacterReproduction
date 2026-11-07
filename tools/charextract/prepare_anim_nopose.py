"""Prepare the preview animation folder for a character without a face-curve system.

Local helper (not part of the handoff bundle). The humanoid characters carry a
facial PoseAsset plus a curve-only dialogue clip, so `prepare_anim.py` requires
those files. Pets have neither: their facial expression is driven by the body
skeleton and material vertex colors, not by a separate facial rig. This variant
therefore emits only the skeletal clips and leaves the face controls empty
instead of inventing pose data.
"""
from pathlib import Path
import argparse, json, shutil, hashlib

LABELS = {
    'World_Idle': '待机', 'World_Walk': '走路', 'World_Run': '跑步',
    'World_Happy_1': '开心动作', 'World_Dialogue_1': '对话动作', 'World_Dialogue_2': '对话动作 2',
    'Common_Idle': '通用待机', 'Common_Relax': '通用休闲', 'Common_Alert': '通用警戒',
    'Common_Anger': '通用生气', 'Common_Fear': '通用恐惧', 'Common_Happy': '通用开心',
    'Common_Sad': '通用难过', 'Common_Shock': '通用惊讶', 'Common_Show': '通用展示',
    'Common_Stun': '通用眩晕', 'Common_Sleep_Stand': '通用站立睡眠',
    'Common_Move_L': '通用左移', 'Common_Move_R': '通用右移',
    'Fight_Start': '战斗准备', 'Fight_Attack_1': '战斗攻击 1', 'Fight_Attack_2': '战斗攻击 2',
    'Fight_Hit_1': '受击 1', 'Fight_Hit_2': '受击 2', 'Fight_Hit_3': '受击 3',
    'Fight_Die': '战败', 'Fight_CallOut': '战斗呼喝',
    'World_Fly_Start': '起飞', 'World_Fly_Hover': '悬停', 'World_Fly_Gliding': '滑翔',
    'World_Fly_Landing': '降落', 'World_Jump_Fall': '跳跃下落',
    'World_Stun_Cough': '眩晕咳嗽', 'World_Stun_Shake': '眩晕摇晃',
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

    clips = []
    for animation in json.loads((src / 'animations.json').read_text(encoding='utf8')):
        if not animation.get('success'):
            continue
        assert animation.get('exportedPoseType') == 'full-local-pose', animation['name']
        shutil.copy2(src / animation['file'], out / animation['file'])
        clips.append({k: animation.get(k) for k in ('name', 'path', 'file', 'frameCount', 'duration', 'sampleFPS',
                                                    'rateScale', 'boneCount', 'exportedPoseType', 'sourceAdditive',
                                                    'sourceRefPoseType', 'sourceRefFrameIndex', 'sourceRefSequence')}
                     | {'label': LABELS.get(animation['name'], animation['name']),
                        'group': 'body',
                        'sha256': hashlib.sha256((src / animation['file']).read_bytes()).hexdigest()})

    rig = json.loads((src / 'rig.json').read_text(encoding='utf8'))
    character = json.loads((root / 'preview' / 'assets' / 'character.json').read_text(encoding='utf8'))
    mesh_name = Path(character.get('path', '')).stem
    meta = {
        'mesh': mesh_name,
        'boneCount': len(rig['bones']),
        'vertexCount': character.get('vertexCount'),
        'coordinates': 'raw UE centimeters, quaternion XYZW; converted at playback',
        'clips': clips,
        'poseCount': 0,
        'facialBoneIndices': [],
        'source': 'Native client ACL-decoded sequences; this character has no facial PoseAsset or curve-only dialogue clip',
    }
    (out / 'manifest.json').write_text(json.dumps(meta, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    (out / 'poses.json').write_text(json.dumps({'poses': []}, ensure_ascii=False, separators=(',', ':')), encoding='utf8')

    # The preview always loads authored-curves.json, so the folder has to contain
    # one. This character owns no curve-only AnimSequence, so the file records
    # an empty curve set instead of borrowed humanoid data.
    authored = {
        'source': None,
        'sourceDuration': 0,
        'sourceFrames': 0,
        'kind': 'no curve-only AnimSequence for this character',
        'poseAsset': None,
        'poseMapping': 'no facial curves exist; facial state is driven by the body skeleton and material vertex colors',
        'curvePayloadSha256': hashlib.sha256(b'').hexdigest(),
        'keyColumns': ['timeSeconds', 'signedValue', 'arriveTangent', 'leaveTangent'],
        'extrapolation': 'constant before first key and after last key',
        'tangentWeights': 'none',
        'cubicEvaluation': 'n/a',
        'warning': 'Empty by source, not by omission: this character has no facial curve asset.',
        'curves': [],
        'signedPairs': [],
    }
    (out / 'authored-curves.json').write_text(json.dumps(authored, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    print('Prepared', len(clips), 'original clips, 0 facial poses, 0 authored curves for', mesh_name)


if __name__ == '__main__':
    main()
