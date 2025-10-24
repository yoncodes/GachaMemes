using System.IO.Compression;

namespace OffsetFinder;

public record NativeLibrary(string Name, string? Architecture);

public class ApkExtractor : IDisposable
{
    private readonly ZipArchive _archive;
    private bool _disposed;

    public ApkExtractor(string apkPath)
    {
        if (!File.Exists(apkPath))
            throw new FileNotFoundException($"APK not found: {apkPath}");

        _archive = ZipFile.OpenRead(apkPath);
    }

    public List<NativeLibrary> FindNativeLibraries()
    {
        return _archive.Entries
            .Where(e => e.FullName.StartsWith("lib/") && e.FullName.EndsWith(".so"))
            .Select(e => new NativeLibrary(e.FullName, DetectArchitecture(e.FullName)))
            .ToList();
    }

    public byte[]? ExtractMetadata()
    {
        string[] possiblePaths =
        {
            "assets/bin/Data/Managed/Metadata/global-metadata.dat",
            "assets/bin/Data/Managed/global-metadata.dat"
        };

        foreach (var path in possiblePaths)
        {
            var entry = _archive.GetEntry(path);
            if (entry != null)
                return ReadEntry(entry);
        }

        return null;
    }

    public byte[]? ExtractLibrary(string libraryName)
    {
        var entry = _archive.GetEntry(libraryName);
        return entry != null ? ReadEntry(entry) : null;
    }

    private static byte[] ReadEntry(ZipArchiveEntry entry)
    {
        using var stream = entry.Open();
        using var ms = new MemoryStream();
        stream.CopyTo(ms);
        return ms.ToArray();
    }

    private static string? DetectArchitecture(string path)
    {
        if (path.Contains("arm64-v8a")) return "arm64";
        if (path.Contains("armeabi-v7a")) return "arm32";
        if (path.Contains("x86_64")) return "x86_64";
        if (path.Contains("x86")) return "x86";
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