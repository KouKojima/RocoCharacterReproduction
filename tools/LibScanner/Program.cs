using CUE4Parse.FileProvider;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Pak.Objects;
using System.Security.Cryptography;
using System.Text.Json;

// Local helper (not part of the handoff bundle): enumerates every ShaderArchive
// entry per pak and can extract one specific pak's copy, so lower-priority
// archive versions stay reachable without touching the verified kit probe.
string? Arg(string name) { var i = Array.IndexOf(args, name); return i >= 0 && i + 1 < args.Length ? args[i + 1] : null; }

var pakDir = Path.GetFullPath(Arg("--paks") ?? throw new Exception("Provide --paks"));
var output = Path.GetFullPath(Arg("--out") ?? throw new Exception("Provide --out"));
var filter = Arg("--filter") ?? "ShaderArchive";
var keyPath = Arg("--key") ?? throw new Exception("Provide --key");
Directory.CreateDirectory(output);

var provider = new DefaultFileProvider(pakDir, SearchOption.TopDirectoryOnly, new VersionContainer(EGame.GAME_RocoKingdomWorld), StringComparer.OrdinalIgnoreCase);
provider.ReadShaderMaps = false;
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey(File.ReadAllBytes(keyPath)));

// Confirmed old NRC overflow: high block-count bits leaked into CustomData.
var fixes = 0;
foreach (var pair in provider.Files)
{
    if (pair.Value is not FPakEntry entry || !entry.IsCompressed) continue;
    var pak = Path.Combine(pakDir, entry.Vfs.Name);
    using var fs = File.OpenRead(pak);
    if (entry.Offset < 0 || entry.Offset + 52 > fs.Length) throw new Exception("Invalid entry header bounds");
    using var br = new BinaryReader(fs);
    fs.Position = entry.Offset + 48;
    var count = br.ReadInt32();
    if (count <= entry.CompressionBlocks.Length) continue;
    if (count > 1000000 || count < 0 || entry.Offset + 57L + 16L * count > fs.Length) throw new Exception("Unexpected compression block layout");
    if ((count & 1023) != entry.CompressionBlocks.Length) throw new Exception("Block-count relation differs");
    var blocks = new FPakCompressedBlock[count];
    for (var i = 0; i < count; i++) { var s = br.ReadInt64(); var e = br.ReadInt64(); blocks[i] = new FPakCompressedBlock { CompressedStart = entry.Offset + s, CompressedEnd = entry.Offset + e }; }
    var flags = br.ReadByte();
    var blockSize = br.ReadUInt32();
    var strategy = entry.CustomData - (count >> 10);
    if (strategy < 0 || blockSize == 0) throw new Exception("Invalid corrected strategy");
    typeof(FPakEntry).GetField("CompressionBlocks")!.SetValue(entry, blocks);
    typeof(FPakEntry).GetField("StructSize")!.SetValue(entry, 57 + 16 * count);
    typeof(FPakEntry).GetField("CompressionBlockSize")!.SetValue(entry, blockSize);
    entry.CustomData = strategy;
    fixes++;
}

var rows = provider.Files
    .Where(x => x.Key.Contains(filter, StringComparison.OrdinalIgnoreCase))
    .Select(x => new
    {
        path = x.Key,
        bytes = x.Value.Size,
        pak = (x.Value as CUE4Parse.UE4.VirtualFileSystem.VfsEntry)?.Vfs.Name
    })
    .ToArray();

File.WriteAllText(Path.Combine(output, "library-index.json"), JsonSerializer.Serialize(new { indexedFiles = provider.Files.Count, largeBlockFixes = fixes, rows }, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine(JsonSerializer.Serialize(new { indexedFiles = provider.Files.Count, largeBlockFixes = fixes, shaderArchives = rows.Length }));

if (Arg("--extract-pak") is string extractPak)
{
    var target = provider.Files
        .Where(x => x.Key.Contains(filter, StringComparison.OrdinalIgnoreCase))
        .Where(x => extractPak == "ALL" || (x.Value as CUE4Parse.UE4.VirtualFileSystem.VfsEntry)?.Vfs.Name == extractPak)
        .Select(x => x.Value)
        .ToArray();
    if (target.Length == 0) throw new Exception("No " + filter + " in pak " + extractPak);
    foreach (var f in target)
    {
        var raw = f.Read();
        var pakName = (f as CUE4Parse.UE4.VirtualFileSystem.VfsEntry)?.Vfs.Name ?? "unknown";
        var name = pakName + "." + Path.GetFileName(f.Path);
        var file = Path.Combine(output, name);
        File.WriteAllBytes(file, raw);
        File.WriteAllText(file + ".provenance.json", JsonSerializer.Serialize(new { objectPath = f.Path, pak = pakName, bytes = raw.Length, sha256 = Convert.ToHexString(SHA256.HashData(raw)) }, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"EXTRACTED {name} {raw.Length}");
    }
}
