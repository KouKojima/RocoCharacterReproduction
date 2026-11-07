using CUE4Parse.FileProvider;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Pak.Objects;

// Local helper (not part of the handoff bundle): same mount and decompression
// corrections as the kit's PortableOptions, but the sample character id is a
// parameter so other NPCs can be rebuilt with byte-identical output formats.
internal sealed class NrcOptions
{
    public required string PakDir, Output, KeyPath, Npc;
    public string Mesh = "";
    public string Root = "";
    public string[] Clips = [];
    public string[] Textures = [];
    public string[] Commands = [];
    public string Filter = "";
    public string Exclude = "";
    public static NrcOptions Parse(string[] args)
    {
        var values = new Dictionary<string, string>();
        var commands = new List<string>();
        for (var i = 0; i < args.Length; i++)
        {
            if (args[i].StartsWith("--"))
            {
                if (i + 1 >= args.Length || args[i + 1].StartsWith("--")) throw new Exception("Missing option value: " + args[i]);
                values.Add(args[i], args[++i]);
            }
            else commands.Add(args[i]);
        }
        var pak = Path.GetFullPath(values.GetValueOrDefault("--paks") ?? throw new Exception("Provide --paks"));
        var output = Path.GetFullPath(values.GetValueOrDefault("--out") ?? throw new Exception("Provide --out"));
        if (output.Equals(pak, StringComparison.OrdinalIgnoreCase) || output.StartsWith(pak.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new Exception("Output must be outside Paks");
        Directory.CreateDirectory(output);
        var npc = values.GetValueOrDefault("--npc") ?? throw new Exception("Provide --npc <NPC_XXXXX>");
        var clips = (values.GetValueOrDefault("--clips") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries);
        var textures = (values.GetValueOrDefault("--textures") ?? "").Split(',', StringSplitOptions.RemoveEmptyEntries);
        return new NrcOptions
        {
            PakDir = pak,
            Output = output,
            KeyPath = values.GetValueOrDefault("--key") ?? throw new Exception("Provide --key"),
            Npc = npc,
            Mesh = values.GetValueOrDefault("--mesh") ?? ("SKM_" + npc + "_Skin"),
            Root = values.GetValueOrDefault("--root") ?? ("/Human/NPC/" + npc + "/"),
            Clips = clips,
            Textures = textures,
            Commands = commands.ToArray(),
            Filter = values.GetValueOrDefault("--filter") ?? "",
            Exclude = values.GetValueOrDefault("--exclude") ?? "",
        };
    }

    public DefaultFileProvider Mount(bool shaders = false, bool script = false)
    {
        var provider = new DefaultFileProvider(PakDir, SearchOption.TopDirectoryOnly, new VersionContainer(EGame.GAME_RocoKingdomWorld), StringComparer.OrdinalIgnoreCase);
        provider.ReadShaderMaps = shaders;
        provider.ReadScriptData = script;
        provider.Initialize();
        var key = File.ReadAllBytes(KeyPath);
        if (key.Length != 32) throw new Exception("Expected 32-byte base key");
        provider.SubmitKey(new FGuid(), new FAesKey(key));
        var pakDir = PakDir;
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
            if (count > 1000000 || count < 0 || entry.Offset + 57L + 16L * count > fs.Length) throw new Exception("Unexpected compression block layout; do not guess");
            if ((count & 1023) != entry.CompressionBlocks.Length) throw new Exception("Block-count relation differs from the confirmed format");
            var blocks = new FPakCompressedBlock[count];
            for (var i = 0; i < count; i++) { var s = br.ReadInt64(); var e = br.ReadInt64(); blocks[i] = new FPakCompressedBlock { CompressedStart = entry.Offset + s, CompressedEnd = entry.Offset + e }; }
            br.ReadByte();
            var blockSize = br.ReadUInt32();
            var strategy = entry.CustomData - (count >> 10);
            if (strategy < 0 || blockSize == 0) throw new Exception("Invalid corrected strategy or block size");
            typeof(FPakEntry).GetField("CompressionBlocks")!.SetValue(entry, blocks);
            typeof(FPakEntry).GetField("StructSize")!.SetValue(entry, 57 + 16 * count);
            typeof(FPakEntry).GetField("CompressionBlockSize")!.SetValue(entry, blockSize);
            entry.CustomData = strategy;
            fixes++;
        }
        Console.WriteLine($"MOUNT files={provider.Files.Count}; block fixes={fixes}");
        return provider;
    }
}
