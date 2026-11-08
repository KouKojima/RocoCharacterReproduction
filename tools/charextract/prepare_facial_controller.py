"""Export the original facial controllerConfig into the preview assets.

Every positive authored curve name (the ones without a ``_Neg`` suffix) is a key
in FacialSubModelConfig_NPC_<npc>.controllerConfig.  Each entry carries
``attributes`` of {pose, weight, jawOpen, blinkScale}; the negative direction is
expressed by the companion ``<name>_Neg`` pose with weight -1.  The authored
negative curves are exact mirrors of the positive ones, so only the positive
curve is sampled (docs/06 sections 1 and 5.1.3).

Output (<assets>/<char>/facial/controller.json):
  {source, note, stats, entries: {curveName: [{pose, weight, jawOpen, blinkScale}]}}

Nothing is silently dropped: poses that do not exist in the character's
poses.json are reported in stats.missingPoses so characters without a
PoseAsset (NPC_06201) degrade honestly instead of faking a blend.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True,
                        help='manifest/ dir with characters.manifest.json')
    parser.add_argument('--out', type=Path, required=True, help='preview assets dir')
    parser.add_argument('--assets-animation', type=Path, default=None,
                        help='optional override for the animation folder (defaults to <out>/<char>/animation)')
    options = parser.parse_args()

    characters = json.loads((options.manifest / 'characters.manifest.json').read_text(encoding='utf-8'))
    cfg_dir = options.manifest / 'facial-controller-config'

    for entry in characters['characters']:
        cid, npc = entry['id'], entry['npc']
        source = cfg_dir / ('FacialSubModelConfig_%s.json' % npc)
        if not source.is_file():
            print('SKIP %-12s no controllerConfig file' % cid)
            continue
        doc = json.loads(source.read_text(encoding='utf-8'))
        controller = doc.get('controllerConfig', {})
        if not controller:
            print('SKIP %-12s empty controllerConfig' % cid)
            continue

        entries = {}
        for curve, value in controller.items():
            entries[curve] = [{
                'pose': a['pose'],
                'weight': a['weight'],
                'jawOpen': a['jawOpen'],
                'blinkScale': a['blinkScale'],
            } for a in value.get('attributes', [])]

        anim = options.assets_animation or (options.out / cid / 'animation')
        poses_file = anim / 'poses.json'
        available = set()
        if poses_file.is_file():
            available = {p['name'] for p in json.loads(poses_file.read_text(encoding='utf-8')).get('poses', [])}
        wanted = {a['pose'] for attrs in entries.values() for a in attrs}
        missing = sorted(wanted - available)

        out = options.out / cid / 'facial'
        out.mkdir(parents=True, exist_ok=True)
        payload = {
            'source': 'manifest/facial-controller-config/' + source.name,
            'note': ('Original controllerConfig attributes. The preview samples positive authored '
                     'curves and applies v(t)*weight to the named pose when the product is positive; '
                     'negative products select the companion _Neg pose. jawOpen/blinkScale channels '
                     'are reported but not applied (no equivalent runtime channel in the preview).'),
            'stats': {
                'entries': len(entries),
                'attributes': sum(len(v) for v in entries.values()),
                'distinctPoses': len(wanted),
                'availablePoses': len(wanted & available),
                'missingPoses': len(missing),
                'missingPoseNames': missing,
                'jawOpenAttributes': sum(1 for v in entries.values() for a in v if a['jawOpen']),
                'blinkScaleAttributes': sum(1 for v in entries.values() for a in v if a['blinkScale']),
            },
            'entries': entries,
        }
        (out / 'controller.json').write_text(
            json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
        print('PREPARED %-12s entries=%-3d attrs=%-3d poses=%-3d available=%-3d missing=%-3d jaw=%d blink=%d'
              % (cid, payload['stats']['entries'], payload['stats']['attributes'],
                 payload['stats']['distinctPoses'], payload['stats']['availablePoses'],
                 payload['stats']['missingPoses'], payload['stats']['jawOpenAttributes'],
                 payload['stats']['blinkScaleAttributes']))


if __name__ == '__main__':
    main()
