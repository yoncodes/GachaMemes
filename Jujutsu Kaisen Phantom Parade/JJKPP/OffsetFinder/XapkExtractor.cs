using System.IO.Compression;

namespace OffsetFinder;

/// <summary>
/// Handles XAPK files with split APKs (architecture-specific splits)
/// </summary>
public class XapkExtractor : IDisposable
{
    private readonly ZipArchive _archive;
    private bool _disposed;

    public XapkExtractor(string xapkPath)
    {
        if (!File.Exists(xapkPath))
            throw new FileNotFoundException($"XAPK not found: {xapkPath}");

        _archive = ZipFile.OpenRead(xapkPath);
    }

    /// <summary>
    /// Find all APK files within the XAPK
    /// </summary>
    public List<string> FindApks()
    {
        return _archive.Entries
            .Where(e => e.FullName.EndsWith(".apk", StringComparison.OrdinalIgnoreCase))
            .Select(e => e.FullName)
            .ToList();
    }

    /// <summary>
    /// Extract metadata from any APK in the XAPK (usually in base APK)
    /// </summary>
    public byte[]? ExtractMetadata()
    {
        string[] metadataPaths =
        {
            "assets/bin/Data/Managed/Metadata/global-metadata.dat",
            "assets/bin/Data/Managed/global-metadata.dat"
        };

        // Try each APK
        var apks = FindApks();
        foreach (var apkPath in apks)
        {
            var apkEntry = _archive.GetEntry(apkPath);
            if (apkEntry == null) continue;

            try
            {
                using var apkStream = apkEntry.Open();
                using var apkArchive = new ZipArchive(apkStream, ZipArchiveMode.Read);

                foreach (var metadataPath in metadataPaths)
                {
                    var metadataEntry = apkArchive.GetEntry(metadataPath);
                    if (metadataEntry != null)
                    {
                        using var ms = new MemoryStream();
                        using var stream = metadataEntry.Open();
                        stream.CopyTo(ms);
                        return ms.ToArray();
                    }
                }
            }
            catch { }
        }

        return null;
    }

    /// <summary>
    /// Find and extract libil2cpp.so from the appropriate architecture split APK
    /// </summary>
    public byte[]? ExtractIl2CppLibrary(string targetArch = "arm64")
    {
        var apks = FindApks();

        // Architecture patterns to look for
        var archPatterns = new Dictionary<string, string[]>
        {
            { "arm64", new[] { "arm64_v8a", "arm64-v8a" } },
            { "arm32", new[] { "armeabi_v7a", "armeabi-v7a" } },
            { "x86_64", new[] { "x86_64" } },
            { "x86", new[] { "x86" } }
        };

        var patterns = archPatterns.GetValueOrDefault(targetArch, archPatterns["arm64"]);

        // Look for split APKs matching the architecture
        var targetApks = apks.Where(apk =>
        {
            var lowerApk = apk.ToLowerInvariant();
            return patterns.Any(p => lowerApk.Contains(p));
        }).ToList();

        // Also check base APK
        var baseApk = apks.FirstOrDefault(a =>
            !a.Contains("split", StringComparison.OrdinalIgnoreCase) &&
            !a.Contains("config", StringComparison.OrdinalIgnoreCase));

        if (baseApk != null)
            targetApks.Insert(0, baseApk);

        // Possible libil2cpp.so paths
        string[] il2cppPaths =
        {
            $"lib/arm64-v8a/libil2cpp.so",
            $"lib/armeabi-v7a/libil2cpp.so",
            $"lib/x86_64/libil2cpp.so",
            $"lib/x86/libil2cpp.so"
        };

        // Try each target APK
        foreach (var apkPath in targetApks)
        {
            var apkEntry = _archive.GetEntry(apkPath);
            if (apkEntry == null) continue;

            try
            {
                using var apkStream = apkEntry.Open();
                using var apkArchive = new ZipArchive(apkStream, ZipArchiveMode.Read);

                foreach (var il2cppPath in il2cppPaths)
                {
                    var libEntry = apkArchive.GetEntry(il2cppPath);
                    if (libEntry != null)
                    {
                        using var ms = new MemoryStream();
                        using var stream = libEntry.Open();
                        stream.CopyTo(ms);
                        return ms.ToArray();
                    }
                }
            }
            catch { }
        }

        return null;
    }

    /// <summary>
    /// Get info about all APKs in the XAPK
    /// </summary>
    public List<XapkApkInfo> GetApkInfo()
    {
        var infos = new List<XapkApkInfo>();
        var apks = FindApks();

        foreach (var apkPath in apks)
        {
            var info = new XapkApkInfo
            {
                Name = Path.GetFileName(apkPath),
                Path = apkPath,
                IsBase = !apkPath.Contains("split", StringComparison.OrdinalIgnoreCase) &&
                         !apkPath.Contains("config", StringComparison.OrdinalIgnoreCase),
                Architecture = DetectArchFromPath(apkPath)
            };

            // Check if it contains libil2cpp.so
            try
            {
                var apkEntry = _archive.GetEntry(apkPath);
                if (apkEntry != null)
                {
                    using var apkStream = apkEntry.Open();
                    using var apkArchive = new ZipArchive(apkStream, ZipArchiveMode.Read);

                    info.HasIl2Cpp = apkArchive.Entries.Any(e =>
                        e.FullName.Contains("libil2cpp.so"));
                    info.HasMetadata = apkArchive.Entries.Any(e =>
                        e.FullName.Contains("global-metadata.dat"));
                }
            }
            catch { }

            infos.Add(info);
        }

        return infos;
    }

    private string? DetectArchFromPath(string path)
    {
        var lower = path.ToLowerInvariant();
        if (lower.Contains("arm64") || lower.Contains("arm64_v8a")) return "arm64";
        if (lower.Contains("armeabi") || lower.Contains("armeabi_v7a")) return "arm32";
        if (lower.Contains("x86_64")) return "x86_64";
        if (lower.Contains("x86")) return "x86";
        return null;
    }

    public void Dispose()
    {
        if (!_disposed)
        {
            _archive?.Dispose();
            _disposed = true;
        }
        GC.SuppressFinalize(this);
    }
}

public class XapkApkInfo
{
    public string Name { get; set; } = string.Empty;
    public string Path { get; set; } = string.Empty;
    public bool IsBase { get; set; }
    public string? Architecture { get; set; }
    public bool HasIl2Cpp { get; set; }
    public bool HasMetadata { get; set; }
}