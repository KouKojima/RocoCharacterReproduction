"""Compact the decoded original face curves for any character.

Local helper (not part of the handoff bundle). The kit's
`character/animation-research/facial-runtime/compact_facial_data.py` is
sample-locked: it asserts the sample character's exact curve/pose counts
(108/109) and hard-codes one sample-only curve name in its report. This copy
keeps the same decoding, validation and output contract but derives those
values from the data actually present, so it works for any extracted
character without touching the checksummed kit files.
"""
from pathlib import Path
import json, struct, hashlib, math, collections
import argparse


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def write(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='character extraction folder')
    options = parser.parse_args()

    root = options.data.resolve() / 'animation-research' / 'facial-runtime'
    anim = root.parent

    raw = read(root / "dialogue-curves.json")
    payload = (root / "dialogue-curves.bin").read_bytes()
    poses = read(anim / "morph-poses/facial-poses.json")
    pose_by_name = {p["name"]: p["index"] for p in poses["poses"]}
    formats = ["empty", "constant", "linear", "cubic", "mixed", "weighted"]
    out = []
    all_keys = []
    for idx, entry in enumerate(raw["curves"]):
        curve = entry["FloatCurve"]
        keys = curve["Keys"]
        name = entry["CurveName"]
        fmt, tfmt, pre, post, n, offset = struct.unpack_from("<BBBBii", payload, idx * 12)
        assert name in pose_by_name
        assert keys and all(math.isfinite(k[field]) for k in keys for field in ["Time", "Value", "ArriveTangent", "LeaveTangent"])
        assert all(a["Time"] <= b["Time"] for a, b in zip(keys, keys[1:]))
        assert all(0 <= k["Time"] <= raw["duration"] + 1e-5 for k in keys)
        assert all(k["TangentWeightMode"] == "RCTWM_WeightedNone" for k in keys)
        assert curve["PreInfinityExtrap"] == curve["PostInfinityExtrap"] == "RCCE_Constant"
        out.append({
            "name": name,
            "poseIndex": pose_by_name[name],
            "compression": formats[fmt],
            "timeCompression": "uint16" if tfmt == 0 else "float32",
            "interpolation": "constant" if fmt <= 1 else "cubic" if fmt == 3 else "linear" if fmt == 2 else "per-key",
            "keys": [[k["Time"], k["Value"], k["ArriveTangent"], k["LeaveTangent"]] for k in keys],
            "minimumKeyValue": min(k["Value"] for k in keys),
            "maximumKeyValue": max(k["Value"] for k in keys),
        })
        all_keys.extend(keys)

    # Sample-locked counts are replaced by the data-derived expectation:
    # every pose except the reference pose has a matching curve.
    assert len(out) == len(pose_by_name) - 1, (len(out), len(pose_by_name))
    extra_poses = set(pose_by_name) - {c["name"] for c in out}
    assert extra_poses == {"Reference"}, extra_poses
    by_name = {c["name"]: c for c in out}
    mirrors = []
    for c in out:
        if c["name"].endswith("_Neg"):
            positive = by_name[c["name"][:-4]]["keys"]
            negative = c["keys"]
            is_mirror = len(positive) == len(negative) and all(
                a[0] == b[0] and all(abs(a[i] + b[i]) < 1e-6 for i in [1, 2, 3])
                for a, b in zip(positive, negative)
            )
            mirrors.append({"positive": c["name"][:-4], "negative": c["name"], "signedMirrors": is_mirror})
    result = {
        "source": raw["path"],
        "sourceDuration": raw["duration"], "sourceFrames": raw["frames"],
        "kind": "curve-only AnimSequence; no compressed bone tracks",
        "poseAsset": poses["source"],
        "poseMapping": "All %d curve names match the same-named pose exactly; Reference is excluded." % len(out),
        "curvePayloadSha256": hashlib.sha256(payload).hexdigest(),
        "keyColumns": ["timeSeconds", "signedValue", "arriveTangent", "leaveTangent"],
        "extrapolation": "constant before first key and after last key",
        "tangentWeights": "none",
        "cubicEvaluation": "For interval a,b: u=(t-a.time)/(b.time-a.time); h00*a.value+h10*dt*a.leaveTangent+h01*b.value+h11*dt*b.arriveTangent; h00=2u^3-3u^2+1,h10=u^3-2u^2+u,h01=-2u^3+3u^2,h11=u^3-u^2.",
        "warning": "Values are original signed curves, not normalized positive weights. Native facial runtime sign gating / multi-pose composition has not been established. Preserve these values rather than claiming a guessed blend is exact original playback. The source name is TestData and does not prove that a released dialogue uses it.",
        "curves": out,
        "signedPairs": mirrors,
    }
    write(root / "dialogue-curves-compact.json", result)

    if (root / 'official-expression-presets.json').exists():
        presets = read(root / "official-expression-presets.json")
        controllers = {}
        for row in presets["controllerConfig"]:
            controllers[row["Key"]] = [{"pose": a["pose"], "coefficient": a["weight"], "jawOpen": a["jawOpen"], "blinkScale": a["blinkScale"]} for a in row["Value"]["attributes"]]
        mapped = {"source": presets["source"], "mapping": controllers,
                  "note": "Mapping coefficients are original controllerConfig attributes. Products below preserve sign; no unverified clamp, normalization or quaternion composition is applied.",
                  "emotionSignedPoseProducts": {}, "visemeSignedPoseProducts": {}}
        for source, destination in [("emotionControllerWeights", "emotionSignedPoseProducts"), ("visemeControllerWeights", "visemeSignedPoseProducts")]:
            for preset, weights in presets[source].items():
                mapped[destination][preset] = {a["pose"]: value * a["coefficient"]
                                              for controller, value in weights.items()
                                              for a in controllers[controller] if value * a["coefficient"] != 0}
        write(root / "official-presets-pose-mapping.json", mapped)

    validation = {
        "curveCount": len(out), "poseCount": len(pose_by_name), "unmappedCurves": [],
        "extraPoseNames": ["Reference"], "keyCount": len(all_keys),
        "nonzeroCurves": sum(c["minimumKeyValue"] != 0 or c["maximumKeyValue"] != 0 for c in out),
        "compressionFormats": dict(collections.Counter(c["compression"] for c in out)),
        "timeFormats": dict(collections.Counter(c["timeCompression"] for c in out)),
        "signedPairs": len(mirrors), "exactMirroredPairs": sum(c["signedMirrors"] for c in mirrors),
        "nonMirroredPairs": [c for c in mirrors if not c["signedMirrors"]],
        "timeRange": [min(k["Time"] for k in all_keys), max(k["Time"] for k in all_keys)],
        "finiteSortedKeysAndConstantExtrapolation": True,
        "keyRangeExamples": {name: {"minimum": by_name[name]["minimumKeyValue"], "maximum": by_name[name]["maximumKeyValue"], "keys": len(by_name[name]["keys"])}
                             for name in ["EyeBlink", "LipTogether_Neg", "BrowUp"] if name in by_name},
        "originalBlinkKeys": by_name["EyeBlink"]["keys"],
    }
    write(root / "dialogue-curves-validation.json", validation)
    print(json.dumps(validation, ensure_ascii=True))


if __name__ == '__main__':
    main()
