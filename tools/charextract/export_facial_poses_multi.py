"""Export the facial PoseAsset of any extracted character.

Local helper (not part of the handoff bundle). The kit's
`character/animation-research/morph-poses/export_facial_poses.py` is
sample-locked: it reads a fixed `Face_Expression_PoseAsset.json` and writes a
fixed `SKM_NPC_00401_Skin` mesh name. This copy takes the character folder and
the PoseAsset file name as parameters and derives the mesh name from the
package path, so any NPC can be rebuilt without touching the checksummed kit
files. The output contract (facial-poses.json + facial-poses-validation.json)
is identical.
"""
from pathlib import Path
import argparse, json, hashlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='character extraction folder')
    parser.add_argument('--pose-asset', required=True, help='PoseAsset json file name inside morph-poses')
    options = parser.parse_args()

    root = options.data.resolve()
    poses_root = root / 'animation-research' / 'morph-poses'
    source_path = poses_root / options.pose_asset
    if not source_path.exists():
        raise SystemExit('missing pose asset export: ' + str(source_path))
    source = json.loads(source_path.read_text(encoding='utf8'))
    props = source['Properties']
    container = props['PoseContainer']
    rig = json.loads((root / 'model-native-bones.json').read_text(encoding='utf8'))
    bone_indices = {b['Name']: i for i, b in enumerate(rig['FinalRefBoneInfo'])}

    names = [x['DisplayName'] for x in container['PoseNames']]
    curve_names = [x['Name']['DisplayName'] for x in container['Curves']]

    def xyz(x):
        return [x[k] for k in 'XYZ']

    def quat(x):
        return [x[k] for k in 'XYZW']

    def transform(t):
        p = xyz(t['Translation'])
        q = quat(t['Rotation'])
        s = xyz(t['Scale3D'])
        return {'translationDelta': [p[0] * .01, p[2] * .01, -p[1] * .01],
                'rotationDelta': [q[0], q[2], -q[1], q[3]],
                'scaleDelta': [s[0], s[2], s[1]],
                'nativeTranslation': p, 'nativeRotation': q, 'nativeScaleDelta': s}

    poses, errors = [], []
    for i, (name, pose) in enumerate(zip(names, container['Poses'])):
        bones = []
        for binding in pose['TrackToBufferIndex']:
            track = int(binding['Key'])
            buffer = binding['Value']
            bone = container['Tracks'][track]
            if bone not in bone_indices:
                errors.append({'pose': name, 'missingBone': bone})
                continue
            bones.append({'boneName': bone, 'boneIndex': bone_indices[bone], 'trackIndex': track,
                          **transform(pose['LocalSpacePose'][buffer])})
        poses.append({'index': i, 'name': name, 'bones': bones, 'curves': dict(zip(curve_names, pose['CurveData']))})

    # The mesh name comes from the PoseAsset package path
    # (…/Human/NPC/NPC_XXXXX/SKM_NPC_XXXXX_Skin.SKM_NPC_XXXXX_Skin:…), not
    # from a hard-coded sample id.
    package = source.get('Package', '')
    mesh = package.split('/')[-1].split('.')[0] if package else ''
    if not mesh.startswith('SKM_'):
        mesh = 'SKM_' + mesh[4:] if mesh else ''

    result = {
        'source': source['Package'],
        'sourceFile': options.pose_asset,
        'sourceSha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
        'mesh': mesh,
        'morphTargetCount': 0,
        'additive': props['bAdditivePose'],
        'basePoseIndex': props['BasePoseIndex'],
        'basePoseName': names[props['BasePoseIndex']],
        'coordinateSystem': 'preview (x,z,-y) meters; local bone additive translation/rotation/scale deltas',
        'quaternionOrder': 'x,y,z,w',
        'scaleConvention': 'delta from base scale: apply multiplicatively as 1+delta for full pose; zero means unchanged',
        'rotationComposition': 'full-weight local additive qFinal = normalize(qDelta * qBase), translationFinal = translationBase + delta, scaleFinal = scaleBase * (1+deltaScale); source engine accumulation and nearest sequence-frame alignment support order, but pose asset and compressed sequence are not bit-identical',
        'trackNames': container['Tracks'],
        'curveNames': curve_names,
        'poses': poses,
        'errors': errors,
    }
    (poses_root / 'facial-poses.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf8')

    report = {
        'passed': not errors,
        'poseCount': len(poses),
        'trackCount': len(container['Tracks']),
        'curveCount': len(curve_names),
        'maxChangedBones': max(len(p['bones']) for p in poses),
        'maxQuatNormError': max(abs(sum(q * q for q in b['rotationDelta']) - 1) for p in poses for b in p['bones']),
        'poseNamesUnique': len(set(names)) == len(names),
        'allMappingsValid': all(0 <= int(m['Key']) < len(container['Tracks']) and 0 <= m['Value'] < len(p['LocalSpacePose'])
                                 for p in container['Poses'] for m in p['TrackToBufferIndex']),
        'additiveReferenceIsIdentity': not poses[0]['bones'] and not any(poses[0]['curves'].values()),
        'nonzeroCurves': [(p['name'], {k: v for k, v in p['curves'].items() if v != 0}) for p in poses if any(p['curves'].values())],
        'selectedPoseBones': {p['name']: [b['boneName'] for b in p['bones']]
                               for p in poses if p['name'] in ['EyeBlink', 'LipTogether', 'LipTogether_Neg', 'BrowUp', 'BrowDown']},
        'errors': errors,
    }
    (poses_root / 'facial-poses-validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('nonzeroCurves',)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
