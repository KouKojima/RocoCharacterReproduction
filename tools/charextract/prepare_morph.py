"""Export morph targets and their animation curves into the preview assets.

The game drives the face with blend shapes, not bones:

  * the mesh carries UMorphTarget deltas (already decoded to morph-deltas.bin),
  * each AnimSequence carries float curves whose names are exactly those of
    the morph targets, so the curve value *is* the blend weight.

Both halves were exported earlier but never reached the browser: this script
joins them into the per-character preview folder.

Output (<assets>/<char>/morph/):
  targets.json   ordered target list; the index is the blend shape index
  deltas.bin     verbatim copy of morph-deltas.bin (index + position + normal)
  curves.json    {clips: {clipName: {curveName: {interp, keys:[[t,v,a,l]]}}}}

Only curves that name a real morph target are kept. Utility curves the game
uses elsewhere (ec_u/v offsets for the eye material, Move_Velocity, EC_Eye,
and the character-specific Xi_/Jing_/Bei_ channels) are counted and reported
but not shipped, so the payload never contains a curve we cannot apply.
"""
import argparse
import json
import math
import shutil
import struct
from pathlib import Path

NRCM = 0x4D43524E


def parse_targets(deltas: Path, meta: list) -> None:
    raw = deltas.read_bytes()
    magic, count = struct.unpack_from('<II', raw, 0)
    if magic != NRCM:
        raise ValueError('unexpected morph-delta magic %08x' % magic)
    if count != len(meta):
        raise ValueError('morph count mismatch: bin %d, json %d' % (count, len(meta)))
    pos = 8
    for item in meta:
        if item['offset'] != pos:
            raise ValueError('target %s offset %d != walked %d' % (item['name'], item['offset'], pos))
        n = struct.unpack_from('<i', raw, pos)[0]
        if n != item['lod0Count']:
            raise ValueError('target %s vertex count %d != %d' % (item['name'], n, item['lod0Count']))
        pos += 4 + n * 28
    if pos != len(raw):
        raise ValueError('trailing bytes: walked %d of %d' % (pos, len(raw)))


def curve_keys(keys: list) -> list:
    out = []
    for k in keys:
        out.append([round(k['Time'], 6), round(k['Value'], 6),
                    round(k['ArriveTangent'], 6), round(k['LeaveTangent'], 6)])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='work dir holding chars/ and multi/')
    parser.add_argument('--chars', type=Path, default=None, help='override chars/ dir')
    parser.add_argument('--out', type=Path, default=None, help='override assets dir')
    options = parser.parse_args()

    chars = options.chars or (options.data / 'chars')
    assets = options.out or (options.data / 'multi' / 'preview' / 'assets')

    totals = []
    for char in sorted(p.name for p in chars.iterdir() if p.is_dir()):
        research = chars / char / 'animation-research'
        morph_dir = research / 'morph-poses'
        if not (morph_dir / 'morphs.json').exists():
            print('SKIP %-12s no morph-poses' % char)
            continue
        target_meta = json.loads((morph_dir / 'morphs.json').read_text(encoding='utf-8'))
        parse_targets(morph_dir / 'morph-deltas.bin', target_meta)
        names = [t['name'] for t in target_meta]

        clips = {}
        kept = skipped = keys_total = 0
        skipped_names = set()
        anim = research / 'native-animation'
        for native in sorted(anim.glob('*-native.json')):
            clip = native.stem[:-len('-native')] if native.stem.endswith('-native') else native.stem
            payload = json.loads(native.read_text(encoding='utf-8'))
            curve_names = [n['DisplayName'] for n in payload.get('CompressedCurveNames', [])]
            float_curves = payload.get('CompressedCurveData', {}).get('FloatCurves', [])
            if len(curve_names) != len(float_curves):
                raise ValueError('%s/%s: %d names vs %d curves'
                                 % (char, clip, len(curve_names), len(float_curves)))
            curves = {}
            for name, wrapper in zip(curve_names, float_curves):
                if name not in names:
                    skipped += 1
                    skipped_names.add(name)
                    continue
                keys = wrapper.get('FloatCurve', {}).get('Keys', [])
                if not keys:
                    continue
                mode = keys[0].get('InterpMode', 'RCIM_Linear')
                interp = {'RCIM_Cubic': 'cubic', 'RCIM_Linear': 'linear',
                          'RCIM_Constant': 'constant'}.get(mode, 'linear')
                curves[name] = {'interp': interp, 'keys': curve_keys(keys)}
                kept += 1
                keys_total += len(keys)
            if curves:
                clips[clip] = {'curves': curves}

        out = assets / char / 'morph'
        out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(morph_dir / 'morph-deltas.bin', out / 'deltas.bin')
        (out / 'targets.json').write_text(json.dumps({
            'magic': 'NRCM',
            'source': 'UMorphTarget LOD0 deltas, decoded by tools/NrcChar DoPoses',
            'layout': 'int32 count, then per target {int32 vertexCount, [int32 sourceIndex, '
                      'float32 positionDelta xyz, float32 tangentZDelta xyz]}',
            'deltaUnits': 'meter (native centimeter deltas scaled by 0.01)',
            'order': 'matches default-blend-shape order of the mesh',
            'targets': [{'name': t['name'], 'count': t['lod0Count'], 'offset': t['offset']}
                        for t in target_meta],
        }, ensure_ascii=False, indent=1), encoding='utf8')
        (out / 'curves.json').write_text(json.dumps({'clips': clips}, separators=(',', ':')), encoding='utf8')

        mouth = sum(1 for n in names if n.lower().startswith(('mh_c', 'mh_o', 'mho_')))
        totals.append((char, len(names), mouth, len(clips), kept, keys_total, skipped, sorted(skipped_names)))
        print('PREPARED %-12s targets=%-3d mouth=%-3d clips=%-3d curves=%-4d keys=%-5d skipped=%-3d %s'
              % (char, len(names), mouth, len(clips), kept, keys_total, skipped,
                 ','.join(sorted(skipped_names))))

    print('PREPARED %d characters' % len(totals))


if __name__ == '__main__':
    main()
