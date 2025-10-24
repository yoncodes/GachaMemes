using System.Text.RegularExpressions;

namespace OffsetFinder;

public class UnityVersion
{
    public int? MetadataVersion { get; init; }
    public string? FullString { get; init; }
    public string? MappedVersion { get; init; }
    public bool IsMetadataEncrypted { get; init; }

    public override string ToString()
    {
        var encrypted = IsMetadataEncrypted ? " [[ENCRYPTED METADATA]]" : "";

        if (MappedVersion != null && MetadataVersion.HasValue && FullString != null)
            return $"Unity {MappedVersion} [[metadata v{MetadataVersion}, raw: {FullString}]]{encrypted}";
        if (MappedVersion != null && MetadataVersion.HasValue)
            return $"Unity {MappedVersion} [[metadata v{MetadataVersion}]]{encrypted}";
        if (MetadataVersion.HasValue)
            return $"Metadata version: {MetadataVersion} (Unknown Unity version){encrypted}";
        return "Unity version not found";
    }
}

public static class VersionDetector
{
    private static readonly Dictionary<int, string> MetadataMapping = new()
    {
        { 21, "5.3.x" },
        { 22, "5.4.x" },
        { 23, "5.5–5.6.x" },
        { 24, "2017–2018.x" },
        { 25, "2019.x" },
        { 26, "2020.x" },
        { 27, "2021.x" },
        { 28, "2022.x" },
        { 29, "2023.x" },
        { 30, "2023.3+" },
        { 31, "6000.0.x" } // Unity 6
    };

    public static UnityVersion Detect(string binaryPath, string? metadataPath = null)
    {
        var fullString = ScanForVersionString(binaryPath);
        int? metadataVersion = null;
        bool isEncrypted = false;

        if (metadataPath != null)
        {
            var (version, encrypted) = ParseMetadataVersion(metadataPath);
            metadataVersion = version;
            isEncrypted = encrypted;
        }

        // Map version string to metadata version if we don't have it from file
        if (fullString != null && !metadataVersion.HasValue)
        {
            metadataVersion = MapVersionStringToMetadata(fullString);
        }

        var mappedVersion = metadataVersion.HasValue
            ? MetadataMapping.GetValueOrDefault(metadataVersion.Value)
            : null;

        return new UnityVersion
        {
            FullString = fullString,
            MetadataVersion = metadataVersion,
            MappedVersion = mappedVersion,
            IsMetadataEncrypted = metadataVersion == null || isEncrypted
        };

    }

    /// <summary>
    /// Detect Unity version from APK/XAPK by scanning multiple sources
    /// </summary>
    public static UnityVersion DetectFromApk(string apkPath, string? metadataPath = null)
    {
        string? versionString = null;
        int? metadataVersion = null;
        bool isEncrypted = false;

        // Parse metadata if provided
        if (metadataPath != null)
        {
            var (version, encrypted) = ParseMetadataVersion(metadataPath);
            metadataVersion = version;
            isEncrypted = encrypted;
        }

        try
        {
            // Check if XAPK
            if (apkPath.EndsWith(".xapk", StringComparison.OrdinalIgnoreCase))
            {
                versionString = ScanXapkForVersion(apkPath);
            }
            else
            {
                versionString = ScanApkForVersion(apkPath);
            }
        }
        catch { }

        // Determine final metadata version
        if (versionString != null && !metadataVersion.HasValue)
        {
            metadataVersion = MapVersionStringToMetadata(versionString);
        }

        var mappedVersionString = metadataVersion.HasValue
            ? MetadataMapping.GetValueOrDefault(metadataVersion.Value)
            : null;

        return new UnityVersion
        {
            FullString = versionString,
            MetadataVersion = metadataVersion,
            MappedVersion = mappedVersionString,
            IsMetadataEncrypted = isEncrypted
        };
    }

    private static string? ScanXapkForVersion(string xapkPath)
    {
        using var xapkArchive = System.IO.Compression.ZipFile.OpenRead(xapkPath);

        var apkEntries = xapkArchive.Entries
            .Where(e => e.FullName.EndsWith(".apk", StringComparison.OrdinalIgnoreCase))
            .ToList();

        foreach (var apkEntry in apkEntries)
        {
            try
            {
                using var apkStream = apkEntry.Open();
                using var apkArchive = new System.IO.Compression.ZipArchive(apkStream, System.IO.Compression.ZipArchiveMode.Read);

                var version = ScanApkArchiveForVersion(apkArchive);
                if (version != null)
                    return version;
            }
            catch { }
        }

        return null;
    }

    private static string? ScanApkForVersion(string apkPath)
    {
        try
        {
            using var apkArchive = System.IO.Compression.ZipFile.OpenRead(apkPath);
            return ScanApkArchiveForVersion(apkArchive);
        }
        catch
        {
            return null;
        }
    }

    private static string? ScanApkArchiveForVersion(System.IO.Compression.ZipArchive apkArchive)
    {
        // Priority 1: Check unity default resources (most reliable)
        var unityResources = apkArchive.GetEntry("assets/bin/Data/unity default resources");
        if (unityResources != null)
        {
            try
            {
                using var stream = unityResources.Open();
                using var ms = new MemoryStream();
                stream.CopyTo(ms);
                var data = ms.ToArray();

                var version = ScanBytesForVersion(data);
                if (version != null)
                    return version;
            }
            catch { }
        }

        // Priority 2: Check libunity.so
        string[] unityLibPaths =
        {
            "lib/arm64-v8a/libunity.so",
            "lib/armeabi-v7a/libunity.so",
            "lib/x86_64/libunity.so",
            "lib/x86/libunity.so"
        };

        foreach (var libPath in unityLibPaths)
        {
            var libEntry = apkArchive.GetEntry(libPath);
            if (libEntry != null)
            {
                try
                {
                    using var stream = libEntry.Open();
                    using var ms = new MemoryStream();
                    stream.CopyTo(ms);
                    var data = ms.ToArray();

                    var version = ScanBytesForVersion(data);
                    if (version != null)
                        return version;
                }
                catch { }
            }
        }

        // Priority 3: Check globalgamemanagers or data.unity3d
        string[] dataFiles =
        {
            "assets/bin/Data/globalgamemanagers",
            "assets/bin/Data/data.unity3d"
        };

        foreach (var dataFile in dataFiles)
        {
            var entry = apkArchive.GetEntry(dataFile);
            if (entry != null)
            {
                try
                {
                    using var stream = entry.Open();
                    // Only read first chunk for performance
                    var buffer = new byte[Math.Min(1024 * 100, entry.Length)];
                    stream.Read(buffer, 0, buffer.Length);

                    var version = ScanBytesForVersion(buffer);
                    if (version != null)
                        return version;
                }
                catch { }
            }
        }

        return null;
    }

    private static string? ScanForVersionString(string path)
    {
        try
        {
            using var fs = File.OpenRead(path);
            var buffer = new byte[4096];
            int bytesRead;

            while ((bytesRead = fs.Read(buffer, 0, buffer.Length)) > 0)
            {
                var text = System.Text.Encoding.UTF8.GetString(buffer, 0, bytesRead);
                var match = Regex.Match(text, @"(20\d{2}|6000|\d+)\.(\d+)\.(\d+)([abcfp]|rc)?\d*");

                if (match.Success && IsValidUnityVersion(match.Value))
                    return match.Value;
            }
        }
        catch { }

        return null;
    }

    private static string? ScanBytesForVersion(byte[] data)
    {
        var pattern = new Regex(@"(6000|20\d{2}|\d+)\.(\d+)\.(\d+)([abcfp]|rc)?\d*");

        const int chunkSize = 8192;
        const int overlap = 128;

        for (int i = 0; i < data.Length; i += chunkSize - overlap)
        {
            var length = Math.Min(chunkSize, data.Length - i);
            var chunk = data.AsSpan(i, length);

            // Try UTF-8
            try
            {
                var text = System.Text.Encoding.UTF8.GetString(chunk);
                var match = pattern.Match(text);

                if (match.Success)
                {
                    var version = match.Value;
                    if (IsValidUnityVersion(version))
                        return version;
                }
            }
            catch { }

            // Try ASCII
            try
            {
                var text = System.Text.Encoding.ASCII.GetString(chunk);
                var match = pattern.Match(text);

                if (match.Success)
                {
                    var version = match.Value;
                    if (IsValidUnityVersion(version))
                        return version;
                }
            }
            catch { }
        }

        return null;
    }

    private static bool IsValidUnityVersion(string version)
    {
        var parts = version.Split('.');
        if (parts.Length < 2)
            return false;

        if (!int.TryParse(parts[0], out var major))
            return false;

        // Valid Unity version: 5.x, 2017-2024, or 6000 (Unity 6)
        return (major >= 5 && major <= 9) || (major >= 2017 && major <= 2025) || major == 6000;
    }

    private static (int? version, bool isEncrypted) ParseMetadataVersion(string path)
    {
        try
        {
            var data = File.ReadAllBytes(path);
            if (data.Length < 8)
                return (null, false);

            // Normal magic: 0xFAB11BAF
            uint magic = BitConverter.ToUInt32(data, 0);

            if (magic == 0xFAB11BAF)
            {
                int version = BitConverter.ToInt32(data, 4);
                return (version == 0 ? null : version, false);
            }

            
            for (int i = 1; i < Math.Min(0x200, data.Length - 8); i++)
            {
                uint testMagic = BitConverter.ToUInt32(data, i);
                if (testMagic == 0xFAB11BAF)
                {
                    int version = BitConverter.ToInt32(data, i + 4);
                    return (version == 0 ? null : version, false);
                }
            }

            
            int highEntropy = data.Take(256).Count(b => b == 0x00 || b == 0xFF);
            bool likelyEncrypted = highEntropy < 16; // very few zeros, likely XORed

            // fallback: assume encrypted if it doesn't start with plausible header
            return (null, likelyEncrypted);
        }
        catch
        {
            return (null, false);
        }
    }


    private static int? MapVersionStringToMetadata(string version)
    {
        var parts = version.Split('.');
        if (parts.Length < 1)
            return null;

        var year = parts[0];
        return year switch
        {
            "6000" => 31,  // Unity 6
            "2024" => 30,
            "2023" => 29,
            "2022" => 28,
            "2021" => 27,
            "2020" => 26,
            "2019" => 25,
            "2018" or "2017" => 24,
            _ when version.StartsWith("5.6") || version.StartsWith("5.5") => 23,
            _ when version.StartsWith("5.4") => 22,
            _ when version.StartsWith("5.3") => 21,
            _ => null
        };
    }
}