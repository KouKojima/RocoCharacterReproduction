using CUE4Parse.UE4.Assets.Exports.Animation;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Objects.Core.Math;
using CUE4Parse.UE4.Objects.Engine.Animation;
using CUE4Parse_Conversion.PoseAsset;
using CUE4Parse_Conversion.Animations;
using CUE4Parse_Conversion.Dto;
using CUE4Parse_Conversion.Options;
using CUE4Parse_Conversion.Textures;
using Newtonsoft.Json;

// Local helper (not part of the handoff bundle): one mount of the local game,
// then any combination of export steps for a chosen NPC. Output formats match
// the kit's probes byte for byte so the kit's validators still apply.
var options = NrcOptions.Parse(args);
var npc = options.Npc;
var npcDir = options.Root;
var provider = options.Mount(shaders: true, script: true);

void DoCatalog()
{
    var assets = provider.Files
        .Where(kv => kv.Key.Contains(npcDir, StringComparison.OrdinalIgnoreCase) && kv.Key.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase))
        .Select(kv => new { path = kv.Key, size = kv.Value.Size, source = (kv.Value as CUE4Parse.UE4.VirtualFileSystem.VfsEntry)?.Vfs.Name })
        .ToArray();
    File.WriteAllText(Path.Combine(options.Output, "catalog.json"), JsonConvert.SerializeObject(assets, Formatting.Indented));
    Console.WriteLine($"CATALOG {assets.Length} assets for {npc}");
}

void DoModel()
{
    var path = provider.Files.Keys.FirstOrDefault(p => p.EndsWith($"/{options.Mesh}.uasset", StringComparison.OrdinalIgnoreCase))
                ?? throw new Exception($"Mesh SKM_{npc}_Skin not mounted");
    var mesh = provider.LoadPackage(path).GetExports().OfType<USkeletalMesh>().First();
    var dto = new SkeletalMeshDto(mesh, new ExportOptions(meshQuality: EMeshQuality.Highest, exportMaterials: false));
    var lod = dto.LODs[0];
    var outdir = Path.Combine(options.Output, "preview", "assets");
    Directory.CreateDirectory(outdir);
    var cols = lod.VertexColors?.FirstOrDefault().Colors;
    using (var w = new BinaryWriter(File.Create(Path.Combine(outdir, "character.bin"))))
    {
        w.Write(0x4343524E); w.Write(lod.Vertices.Length); w.Write(lod.Indices.Length); w.Write(lod.ExtraUvs.Length + 1);
        foreach (var v in lod.Vertices) { w.Write(v.Position.X * .01f); w.Write(v.Position.Z * .01f); w.Write(-v.Position.Y * .01f); }
        foreach (var v in lod.Vertices) { w.Write(v.Normal.X); w.Write(v.Normal.Z); w.Write(-v.Normal.Y); }
        foreach (var v in lod.Vertices) { w.Write(v.Tangent.X); w.Write(v.Tangent.Z); w.Write(-v.Tangent.Y); w.Write(v.Normal.W); }
        foreach (var v in lod.Vertices) { w.Write(v.Uv.U); w.Write(v.Uv.V); }
        foreach (var uv in lod.ExtraUvs) foreach (var v in uv) { w.Write(v.U); w.Write(v.V); }
        for (int i = 0; i < lod.Vertices.Length; i++) { var c = cols is { Length: > 0 } ? cols[i] : new FColor(255, 255, 255, 255); w.Write(c.R); w.Write(c.G); w.Write(c.B); w.Write(c.A); }
        foreach (var index in lod.Indices) w.Write(index);
    }
    var sec = lod.Sections.Select((s, i) => new
    {
        section = i,
        materialIndex = s.MaterialIndex,
        start = s.FirstIndex,
        count = s.NumFaces * 3,
        meshMaterial = new
        {
            slot = mesh.SkeletalMaterials[s.MaterialIndex].MaterialSlotName?.ToString(),
            path = mesh.SkeletalMaterials[s.MaterialIndex].MaterialInterface?.ResolvedObject?.GetPathName(),
        },
    }).ToArray();
    var colorStats = sec.Select(s =>
    {
        var ids = lod.Indices.Skip(s.start).Take(s.count).Distinct().Select(v => (int)v).ToArray();
        return new
        {
            section = s.section,
            vertexCount = ids.Length,
            uniqueColors = cols is { Length: > 0 } ? ids.Select(i => cols[i]).Distinct().Count() : 0,
            min = cols is { Length: > 0 } ? new[] { ids.Min(i => cols[i].R), ids.Min(i => cols[i].G), ids.Min(i => cols[i].B), ids.Min(i => cols[i].A) } : null,
            max = cols is { Length: > 0 } ? new[] { ids.Max(i => cols[i].R), ids.Max(i => cols[i].G), ids.Max(i => cols[i].B), ids.Max(i => cols[i].A) } : null,
        };
    }).ToArray();
    File.WriteAllText(Path.Combine(outdir, "character.json"), JsonConvert.SerializeObject(new
    {
        path,
        coordinateTransform = "UE (x,y,z) centimeters -> preview (x,z,-y) meters",
        vertexCount = lod.Vertices.Length,
        indexCount = lod.Indices.Length,
        uvCount = lod.ExtraUvs.Length + 1,
        hasVertexColors = cols is { Length: > 0 },
        sections = sec,
        colorStats,
        bounds = mesh.ImportedBounds,
    }, Formatting.Indented));
    File.WriteAllText(Path.Combine(options.Output, "model-native-bones.json"), JsonConvert.SerializeObject(mesh.ReferenceSkeleton, Formatting.Indented));
    Console.WriteLine($"MODEL {npc} vertices={lod.Vertices.Length} triangles={lod.Indices.Length / 3} uvs={lod.ExtraUvs.Length + 1} colors={cols?.Length}; " + JsonConvert.SerializeObject(colorStats));
}

void DoTextures()
{
    TextureDecoder.UseAssetRipperTextureDecoder = true;
    var textureOut = Path.Combine(options.Output, "preview-native-textures");
    Directory.CreateDirectory(textureOut);
    var report = new List<object>();
    foreach (var request in options.Textures)
    {
        var name = request.Split('/').Last().Split('.')[0];
        var path = provider.Files.Keys.FirstOrDefault(p => p.EndsWith("/" + name + ".uasset", StringComparison.OrdinalIgnoreCase))
                   ?? throw new Exception("Missing texture " + request);
        var tex = provider.LoadPackage(path).GetExports().OfType<UTexture2D>().First(t => t.Name == name);
        var mips = new List<object>();
        for (int level = 0; level < tex.PlatformData.Mips.Length; level++)
        {
            var image = tex.DecodeMip(level, new ExportOptions());
            if (image == null) throw new Exception($"No mip {name}/{level}");
            var png = image.Encode(new ExportOptions(), out var ext);
            var file = name + "-mip" + level + "." + ext;
            File.WriteAllBytes(Path.Combine(textureOut, file), png);
            mips.Add(new { level, width = image.Width, height = image.Height, logicalWidth = Math.Max(1, tex.PlatformData.SizeX >> level), logicalHeight = Math.Max(1, tex.PlatformData.SizeY >> level), file });
        }
        report.Add(new { name, path, srgb = tex.SRGB, width = tex.PlatformData.SizeX, height = tex.PlatformData.SizeY, format = tex.Format.ToString(), mips });
        Console.WriteLine($"TEXTURE {name} mips={mips.Count} sRGB={tex.SRGB}");
    }
    File.WriteAllText(Path.Combine(textureOut, "manifest.json"), JsonConvert.SerializeObject(report, Formatting.Indented));
}

void DoPoses()
{
    var output = Path.Combine(options.Output, "animation-research", "morph-poses");
    Directory.CreateDirectory(output);
    var paths = provider.Files.Keys.Where(p => p.EndsWith(".uasset") && p.Contains(options.Root)).OrderBy(p => p).ToArray();
    File.WriteAllText(Path.Combine(output, "catalog.txt"), string.Join('\n', paths));
    var meshPath = paths.First(p => p.EndsWith($"/{options.Mesh}.uasset"));
    var exports = provider.LoadPackage(meshPath).GetExports().ToArray();
    var mesh = exports.OfType<USkeletalMesh>().First();
    Console.WriteLine($"Mesh exports {exports.Length}; morph refs {mesh.MorphTargets.Length}; embedded morphs {exports.OfType<UMorphTarget>().Count()}");
    File.WriteAllText(Path.Combine(output, "mesh-exports.json"), JsonConvert.SerializeObject(exports.Select(x => new { x.Name, type = x.GetType().Name, path = x.GetPathName() }), Formatting.Indented));
    File.WriteAllText(Path.Combine(output, "mesh-morph-refs.json"), JsonConvert.SerializeObject(mesh.MorphTargets, Formatting.Indented));
    var morphs = exports.OfType<UMorphTarget>().ToList();
    foreach (var reference in mesh.MorphTargets) { if (reference.TryLoad<UMorphTarget>(out var morph) && !morphs.Contains(morph)) morphs.Add(morph); }
    var report = new List<object>();
    using (var w = new BinaryWriter(File.Create(Path.Combine(output, "morph-deltas.bin"))))
    {
        w.Write(0x4D43524E); w.Write(morphs.Count);
        foreach (var morph in morphs)
        {
            var lod = morph.MorphLODModels.FirstOrDefault(); var vertices = lod?.Vertices ?? []; var offset = w.BaseStream.Position;
            w.Write(vertices.Length);
            foreach (var v in vertices) { w.Write(v.SourceIdx); w.Write(v.PositionDelta.X * .01f); w.Write(v.PositionDelta.Z * .01f); w.Write(-v.PositionDelta.Y * .01f); w.Write(v.TangentZDelta.X); w.Write(v.TangentZDelta.Z); w.Write(-v.TangentZDelta.Y); }
            report.Add(new { name = morph.Name, path = morph.GetPathName(), lod0Count = vertices.Length, offset, numBaseMeshVerts = lod?.NumBaseMeshVerts, sections = lod?.SectionIndices, lodCounts = morph.MorphLODModels.Select(l => l.Vertices.Length).ToArray(), maxPositionDelta = vertices.Length > 0 ? vertices.Max(v => v.PositionDelta.Size()) : 0 });
            File.WriteAllText(Path.Combine(output, morph.Name + "-metadata.json"), JsonConvert.SerializeObject(morph, Formatting.Indented));
        }
    }
    File.WriteAllText(Path.Combine(output, "morphs.json"), JsonConvert.SerializeObject(report, Formatting.Indented));
    Console.WriteLine("Morphs " + JsonConvert.SerializeObject(report));
    var poseResults = new List<object>();
    var poseCandidates = paths.Where(p => p.Contains("Pose") || p.Contains("/KouXing_") || p.Contains("/P_")
                                          || Path.GetFileNameWithoutExtension(p).StartsWith("PA_", StringComparison.OrdinalIgnoreCase)).ToArray();
    Console.WriteLine("POSE CANDIDATES " + poseCandidates.Length);
    foreach (var path in poseCandidates)
    {
        try
        {
            var objects = provider.LoadPackage(path).GetExports().ToArray();
            if (objects.Length > 0) Console.WriteLine("PKG " + path + " -> " + string.Join(",", objects.Select(x => x.GetType().Name)));
            foreach (var pose in objects.OfType<UPoseAsset>())
            {
                File.WriteAllText(Path.Combine(output, pose.Name + ".json"), JsonConvert.SerializeObject(pose, Formatting.Indented));
                var container = pose.PoseContainer; var convertedOk = pose.TryConvert(out var converted);
                if (convertedOk) File.WriteAllText(Path.Combine(output, pose.Name + "-converted.json"), JsonConvert.SerializeObject(converted, Formatting.Indented));
                poseResults.Add(new { path, name = pose.Name, pose.bAdditivePose, pose.BasePoseIndex, poseNames = container.GetPoseNames().ToArray(), trackCount = container.Tracks.Length, curveCount = container.Curves.Length, poseCount = container.Poses?.Length, convertedOk });
                Console.WriteLine("POSE " + pose.Name + " " + container.Poses?.Length);
            }
        }
        catch (Exception e) { poseResults.Add(new { path, error = e.ToString() }); Console.WriteLine("ERR " + path + " " + e.Message); }
    }
    File.WriteAllText(Path.Combine(output, "pose-inventory.json"), JsonConvert.SerializeObject(poseResults, Formatting.Indented));
    Console.WriteLine("POSES " + poseResults.Count);
}

void DoDialogue()
{
    var output = Path.Combine(options.Output, "animation-research", "facial-runtime");
    Directory.CreateDirectory(output);
    Directory.CreateDirectory(Path.Combine(output, "assets"));
    var numeric = new string(npc.Where(char.IsDigit).ToArray());
    var named = provider.Files.Keys
        .Where(p => p.EndsWith(".uasset") && Path.GetFileNameWithoutExtension(p).StartsWith("TestData_", StringComparison.OrdinalIgnoreCase))
        .Where(p => Path.GetFileNameWithoutExtension(p).EndsWith("_" + numeric, StringComparison.OrdinalIgnoreCase))
        .OrderBy(p => p).ToArray();
    var candidates = named.Length > 0 ? named : provider.Files.Keys
        .Where(p => p.EndsWith(".uasset") && Path.GetFileNameWithoutExtension(p).StartsWith("TestData_", StringComparison.OrdinalIgnoreCase))
        .Where(p => Path.GetFileNameWithoutExtension(p).Contains(numeric, StringComparison.OrdinalIgnoreCase))
        .OrderBy(p => p).ToArray();
    if (candidates.Length == 0) throw new Exception("No curve-only TestData clip found for " + npc);
    var path = candidates[0];
    Console.WriteLine("TESTDATA " + path);
    var anim = provider.LoadPackage(path).GetExports().OfType<UAnimSequence>().First();
    var payload = provider.SavePackage(path).First(p => p.Key.EndsWith(".uexp")).Value;
    var marker = System.Text.Encoding.ASCII.GetBytes("/Engine/Animation/DefaultAnimCurveCompressionSettings.DefaultAnimCurveCompressionSettings:CurveCompressionCodec\0");
    var at = payload.AsSpan().IndexOf(marker);
    if (at < 4) throw new Exception("Codec string missing");
    if (BitConverter.ToInt32(payload, at - 4) != marker.Length) throw new Exception("FString size mismatch");
    var count = BitConverter.ToInt32(payload, at + marker.Length); var begin = at + marker.Length + 4;
    var bytes = payload[begin..(begin + count)]; var names = anim.CompressedCurveNames ?? throw new Exception("No curve names");
    for (int i = 0; i < names.Length; i++)
    {
        var p = i * 12; var off = BitConverter.ToInt32(bytes, p + 8);
        if (bytes[p] > 5 || bytes[p + 1] > 1 || off < names.Length * 12 || off > bytes.Length || (off == bytes.Length && bytes[p] > 1)) throw new Exception("Bad curve header " + i);
    }
    var curves = new UAnimCurveCompressionCodec_CompressedRichCurve().ConvertCurves(names, bytes);
    var report = new { path, curveCodec = "DefaultAnimCurveCompressionSettings:CurveCompressionCodec / CompressedRichCurve", curveByteOffset = begin, curveByteLength = count, frames = anim.NumFrames, duration = anim.SequenceLength, curveNames = names.Select(n => n.DisplayName.Text).ToArray(), curves };
    File.WriteAllText(Path.Combine(output, "dialogue-curves.json"), JsonConvert.SerializeObject(report, Formatting.Indented));
    File.WriteAllBytes(Path.Combine(output, "dialogue-curves.bin"), bytes);
    var samples = new List<object>();
    foreach (var c in curves) { var keys = c.FloatCurve.Keys; samples.Add(new { name = c.CurveName.Text, keys = keys?.Length ?? 0, min = keys?.Min(k => k.Value), max = keys?.Max(k => k.Value) }); }
    Console.WriteLine("DECODED " + curves.Length + " " + JsonConvert.SerializeObject(samples.Take(10)));
}

void DoAnim()
{
    var output = Path.Combine(options.Output, "animation-research", "native-animation");
    Directory.CreateDirectory(output);
    var assets = provider.Files.Where(kv => kv.Key.Contains(npcDir, StringComparison.OrdinalIgnoreCase) && kv.Key.EndsWith(".uasset", StringComparison.OrdinalIgnoreCase))
        .Select(kv => new { path = kv.Key, size = kv.Value.Size, source = (kv.Value as CUE4Parse.UE4.VirtualFileSystem.VfsEntry)?.Vfs.Name }).ToArray();
    File.WriteAllText(Path.Combine(output, "catalog.json"), JsonConvert.SerializeObject(assets, Formatting.Indented));
    Console.WriteLine($"NPC ASSETS {assets.Length}");

    var meshPath = provider.Files.Keys.First(p => p.EndsWith($"/{options.Mesh}.uasset", StringComparison.OrdinalIgnoreCase));
    var mesh = provider.LoadPackage(meshPath).GetExports().OfType<USkeletalMesh>().First();
    var dto = new SkeletalMeshDto(mesh, new ExportOptions(meshQuality: EMeshQuality.Highest, exportMaterials: false));
    var lod = dto.LODs[0];
    File.WriteAllText(Path.Combine(output, "rig.json"), JsonConvert.SerializeObject(new
    {
        coordinateSystem = "Raw UE coordinates, centimeters; FQuat XYZW; local transforms",
        meshPath,
        bones = dto.Bones.Select((b, i) => new { index = i, name = b.Name, parent = b.ParentIndex, position = new[] { b.Transform.Translation.X, b.Transform.Translation.Y, b.Transform.Translation.Z }, quaternion = new[] { b.Transform.Rotation.X, b.Transform.Rotation.Y, b.Transform.Rotation.Z, b.Transform.Rotation.W }, scale = new[] { b.Transform.Scale3D.X, b.Transform.Scale3D.Y, b.Transform.Scale3D.Z } }),
        skeletonPath = dto.SkeletonPathName,
    }, Formatting.Indented));
    using (var w = new BinaryWriter(File.Create(Path.Combine(output, "skin.bin"))))
    {
        w.Write(0x534B524E); w.Write(lod.Vertices.Length); w.Write(dto.Bones.Length); w.Write(4);
        foreach (var v in lod.Vertices) { var inf = v.Influences.OrderByDescending(x => x.Weight).Take(4).ToArray(); for (int i = 0; i < 4; i++) w.Write(i < inf.Length ? inf[i].Bone : (ushort)0); for (int i = 0; i < 4; i++) w.Write(i < inf.Length ? inf[i].Weight : 0f); }
    }

    var selected = options.Clips.Length > 0
        ? options.Clips
        : new[] { "World_Idle", "World_Idle_Relax_1", "World_Walk", "World_Run", "World_Hello_1", "World_Happy_1", "World_Anger_1", "World_Sad_1", "World_Shock_1", "World_Dialogue_1", "Face_Expression", "P_Eye_Close", "P_Eye_Idle", "P_Eye_Happy", "P_Eye_Anger", "P_Eye_Sad", "P_Eye_Shock", "KouXing_Idle", "KouXing_Happy", "KouXing_Anger", "KouXing_Sad", "KouXing_Shock", "Pos_LookBase", "Pos_LookDown", "Pos_LookLeft", "Pos_LookRight", "Pos_LookUp", "P_Idle", "P_Happy", "P_Anger", "P_Sad", "P_Shock", "P_KX_Idle", "P_KX_Happy", "P_KX_Anger", "P_KX_Sad", "P_KX_Shock" };

    string? Resolve(string name)
    {
        var own = provider.Files.Keys.FirstOrDefault(p => p.Contains(npcDir, StringComparison.OrdinalIgnoreCase) && p.EndsWith("/" + name + ".uasset", StringComparison.OrdinalIgnoreCase));
        if (own != null) return own;
        var facial = provider.Files.Keys.FirstOrDefault(p => p.Contains("/FacialAnimationData/", StringComparison.OrdinalIgnoreCase) && p.EndsWith("/" + name + ".uasset", StringComparison.OrdinalIgnoreCase));
        if (facial != null) return facial;
        var loose = provider.Files.Keys.Where(p => p.EndsWith("/" + name + ".uasset", StringComparison.OrdinalIgnoreCase)).ToArray();
        return loose.Length == 1 ? loose[0] : null;
    }

    var report = new List<object>();
    foreach (var name in selected)
    {
        var path = Resolve(name);
        if (path == null) { report.Add(new { name, error = "missing" }); Console.WriteLine($"MISSING {name}"); continue; }
        try
        {
            var exports = provider.LoadPackage(path).GetExports().ToArray();
            var anim = exports.OfType<UAnimSequence>().First();
            File.WriteAllText(Path.Combine(output, name + "-native.json"), JsonConvert.SerializeObject(anim, Formatting.Indented));
            var set = anim.ConvertAnims();
            var seq = set.Sequences[0];
            seq.RetargetTracks(mesh.ReferenceSkeleton);
            var sourceBoneNames = set.Skeleton.ReferenceSkeleton.FinalRefBoneInfo.Select(x => x.Name.Text).ToArray();
            var mapping = dto.Bones.Select(b => Array.IndexOf(sourceBoneNames, b.Name)).ToArray();
            float maxSamplerQuaternionNormError = 0;
            var file = name + ".bin";
            using (var w = new BinaryWriter(File.Create(Path.Combine(output, file))))
            {
                w.Write(0x414E524E); w.Write(seq.NumFrames); w.Write(dto.Bones.Length); w.Write(anim.SequenceLength);
                for (int frame = 0; frame < seq.NumFrames; frame++) for (int bone = 0; bone < dto.Bones.Length; bone++)
                {
                    var bp = dto.Bones[bone].Transform; var q = bp.Rotation; var p = bp.Translation; var s = bp.Scale3D;
                    var source = mapping[bone];
                    if (source >= 0 && source < seq.Tracks.Count) seq.Tracks[source].GetBoneTransform(frame, seq.NumFrames, ref q, ref p, ref s);
                    var norm = MathF.Sqrt(q.X * q.X + q.Y * q.Y + q.Z * q.Z + q.W * q.W);
                    maxSamplerQuaternionNormError = MathF.Max(maxSamplerQuaternionNormError, MathF.Abs(norm - 1f));
                    if (norm > 1e-12f) { var inv = 1f / norm; q = new FQuat(q.X * inv, q.Y * inv, q.Z * inv, q.W * inv); }
                    w.Write(p.X); w.Write(p.Y); w.Write(p.Z); w.Write(q.X); w.Write(q.Y); w.Write(q.Z); w.Write(q.W); w.Write(s.X); w.Write(s.Y); w.Write(s.Z);
                }
            }
            report.Add(new
            {
                name, path, success = true, file, frameCount = seq.NumFrames, duration = anim.SequenceLength, rateScale = anim.RateScale,
                sampleFPS = (seq.NumFrames - 1) / anim.SequenceLength, libraryFramesPerSecond = seq.FramesPerSecond,
                boneCount = dto.Bones.Length, sourceBoneCount = sourceBoneNames.Length,
                codec = anim.CompressedDataStructure?.GetType().Name, sourceAdditive = seq.IsAdditive, exportedPoseType = "full-local-pose",
                quaternionNormalization = "Accurate unit normalization after CUE4Parse sampling", maxSamplerQuaternionNormError,
                sourceRefPoseType = anim.RefPoseType.ToString(), sourceRefFrameIndex = anim.RefFrameIndex, sourceRefSequence = anim.RefPoseSeq?.GetPathName(),
                missingMappedBones = mapping.Count(x => x < 0), sourceBoneNames,
                trackCoverage = mapping.Select((index, bone) => new { meshBone = bone, sourceBone = index, positionKeys = index >= 0 ? seq.Tracks[index].KeyPos.Length : 0, rotationKeys = index >= 0 ? seq.Tracks[index].KeyQuat.Length : 0, scaleKeys = index >= 0 ? seq.Tracks[index].KeyScale.Length : 0 }),
            });
            Console.WriteLine($"ANIMATION {name}: frames={seq.NumFrames}, duration={anim.SequenceLength}, bones={dto.Bones.Length}, codec={anim.CompressedDataStructure?.GetType().Name}, additive={seq.IsAdditive}");
        }
        catch (Exception ex) { report.Add(new { name, path, success = false, error = ex.ToString() }); Console.WriteLine($"ERROR {name}: {ex.Message}"); }
    }
    var success = report.Where(o => Newtonsoft.Json.Linq.JObject.FromObject(o)["success"]?.ToObject<bool>() == true).ToArray();
    var failures = report.Where(o => Newtonsoft.Json.Linq.JObject.FromObject(o)["success"]?.ToObject<bool>() != true).ToArray();
    File.WriteAllText(Path.Combine(output, "animations.json"), JsonConvert.SerializeObject(success, Formatting.Indented));
    File.WriteAllText(Path.Combine(output, "export-failures.json"), JsonConvert.SerializeObject(failures, Formatting.Indented));
    Console.WriteLine($"RIG vertices={lod.Vertices.Length} bones={dto.Bones.Length}");
}

var commands = options.Commands.Length > 0 ? options.Commands : new[] { "model" };
foreach (var command in commands)
{
    switch (command)
    {
        case "catalog": DoCatalog(); break;
        case "model": DoModel(); break;
        case "textures": DoTextures(); break;
        case "poses": DoPoses(); break;
        case "dialogue": DoDialogue(); break;
        case "anim": DoAnim(); break;
        default: throw new Exception("Unknown command: " + command);
    }
}
