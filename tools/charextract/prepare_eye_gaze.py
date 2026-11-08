"""Export the original per-clip eye-gaze curves into the preview assets.

Every native AnimSequence that carries facial curves also carries four float
curves named ec_u_offset_l / ec_u_offset_r / ec_v_offset_l / ec_v_offset_r.
They are the UV offsets consumed by the original material function
MF_FacialAnimationUV.  prepare_morph.py only ships curves whose names match a
real morph target, so the gaze curves are counted and dropped there; this
script ships them verbatim.

Output (<assets>/<char>/gaze/curves.json):
  {source, channels, units, note, stats,
   clips: {clipName: {curves: {name: {interp, keys: [[t,v,arrive,leave],...]}}}}}

No sign flip, clamp, normalization or rescaling is applied.  The sign/scale
convention inside MF_FacialAnimationUV has not been verified against a
rendered frame (docs/05), so the preview adds the raw values as UV offsets
and states that assumption in the UI and the handoff notes.
"""
import argparse
import json
import math
from pathlib import Path

CHANNELS = ('ec_u_offset_l', 'ec_u_offset_r', 'ec_v_offset_l', 'ec_v_offset_r')
INTERP = {'RCIM_Constant': 'constant', 'RCIM_Linear': 'linear', 'RCIM_Cubic': 'cubic'}


def curve_keys(keys, clip, name):
    out = []
    previous = None
    for k in keys:
        t, v, a, l = (k['Time'], k['Value'], k['ArriveTangent'], k['LeaveTangent'])
        if not all(math.isfinite(x) for x in (t, v, a, l)):
            raise ValueError('%s/%s: non-finite key' % (clip, name))
        if previous is not None and t < previous:
            raise ValueError('%s/%s: keys not sorted' % (clip, name))
        previous = t
        out.append([round(t, 6), round(v, 6), round(a, 6), round(l, 6)])
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='work dir holding chars/ and multi/')
    parser.add_argument('--chars', type=Path, default=None, help='override chars/ dir')
    parser.add_argument('--out', type=Path, default=None, help='override assets dir')
    options = parser.parse_args()

    chars = options.chars or (options.data / 'chars')
    assets = options.out or (options.data / 'multi' / 'preview' / 'assets')

    for char in sorted(p.name for p in chars.iterdir() if p.is_dir()):
        native_dir = chars / char / 'animation-research' / 'native-animation'
        if not native_dir.is_dir():
            print('SKIP %-12s no native-animation' % char)
            continue
        clips = {}
        values = []
        key_count = 0
        interp_keys = {}
        channel_count = {name: 0 for name in CHANNELS}
        for native in sorted(native_dir.glob('*-native.json')):
            clip = native.stem[:-len('-native')]
            payload = json.loads(native.read_text(encoding='utf-8'))
            names = [n.get('DisplayName') for n in payload.get('CompressedCurveNames', [])]
            floats = payload.get('CompressedCurveData', {}).get('FloatCurves', [])
            if len(names) != len(floats):
                raise ValueError('%s/%s: %d names vs %d curves' % (char, clip, len(names), len(floats)))
            curves = {}
            for name, wrapper in zip(names, floats):
                if name not in CHANNELS:
                    continue
                keys = wrapper.get('FloatCurve', {}).get('Keys', [])
                if not keys:
                    continue
                modes = {k.get('InterpMode', 'RCIM_Linear') for k in keys}
                if len(modes) != 1:
                    raise ValueError('%s/%s/%s: mixed interpolation %s'
                                     % (char, clip, name, sorted(modes)))
                mode = next(iter(modes))
                if mode not in INTERP:
                    raise ValueError('%s/%s/%s: unsupported interpolation %s'
                                     % (char, clip, name, mode))
                interp = INTERP[mode]
                curves[name] = {'interp': interp, 'keys': curve_keys(keys, clip, name)}
                channel_count[name] += 1
                key_count += len(keys)
                interp_keys[interp] = interp_keys.get(interp, 0) + len(keys)
                values.extend(k[1] for k in curves[name]['keys'])
            if curves:
                clips[clip] = {'curves': curves}
        if not clips:
            print('SKIP %-12s no gaze curves' % char)
            continue

        out = assets / char / 'gaze'
        out.mkdir(parents=True, exist_ok=True)
        doc = {
            'source': 'chars/%s/animation-research/native-animation/*-native.json' % char,
            'channels': list(CHANNELS),
            'units': 'raw original float-curve values; applied verbatim as eye-material UV offsets',
            'note': ('Curve names follow the original MF_FacialAnimationUV eye offsets. Left and right '
                     'channels are shipped separately and applied to their own eye. No sign flip, clamp, '
                     'normalization or rescaling is applied; the original material function has not been '
                     'frame-matched, see docs/05.'),
            'stats': {
                'clips': len(clips),
                'channels': channel_count,
                'keys': key_count,
                'interpolationKeys': interp_keys,
                'minValue': min(values),
                'maxValue': max(values),
            },
            'clips': clips,
        }
        (out / 'curves.json').write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
        print('PREPARED %-12s clips=%-3d keys=%-5d min=%.6f max=%.6f channels=%s'
              % (char, len(clips), key_count, min(values), max(values), channel_count))


if __name__ == '__main__':
    main()
