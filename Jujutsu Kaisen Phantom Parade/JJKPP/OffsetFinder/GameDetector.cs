using System.IO.Compression;
using System.Text;
using System.Text.RegularExpressions;

namespace OffsetFinder;

public record GameInfo(
    string Name,
    string PackageName,
    string ShortName
);

public static class GameDetector
{
    private static readonly Dictionary<string, GameInfo> KnownGames = new()
    {
        { "jp.co.sumzap.pj0014", new GameInfo(
            "Jujutsu Kaisen Phantom Parade (JP)",
            "jp.co.sumzap.pj0014",
            "jjkppjp"
        )},

        { "com.bilibilihk.jujutsuphanpara.qooapp", new GameInfo(
        "Jujutsu Kaisen Phantom Parade (Global QooApp)",
        "com.bilibilihk.jujutsuphanpara.qooapp",
        "jjkppgl"
    )},
    };

    public static GameInfo? DetectGame(string path)
    {
        string? pkg = null;
        GameInfo? g = null;

        try
        {
            // Try manifest extraction
            pkg = ExtractPackageName(path);
            if (pkg != null)
            {
                g = DetectGameFromPackage(pkg);
                if (g != null)
                    return g;
            }

            // Try filename / xapk heuristic
            var guess = GuessPackageNameFromXapkOrPath(path);
            if (guess != null)
            {
                pkg ??= guess;
                g = DetectGameFromPackage(guess);
                if (g != null)
                    return g;
            }

            // --- No match, fallback mode ---
            Console.WriteLine();
            if (pkg == null)
            {
                Console.WriteLine("[WARN] Game detection failed: Could not determine the package name from manifest or APK name.");
                Console.WriteLine("[WARN] Using generic IL2CPP pattern set as fallback.");
            }
            else
            {
                Console.WriteLine($"[WARN] Detected package name '{pkg}', but it's not registered in KnownGames.");
                Console.WriteLine("[WARN] Using generic IL2CPP pattern set as fallback.");
            }

            // Return null to trigger generic pattern selection later
            return null;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[WARN] Game detection failed: {ex.Message}");
            return null;
        }
    }



    public static GameInfo? DetectGameFromPackage(string packageName)
        => KnownGames.TryGetValue(packageName, out var g) ? g : null;

    /// <summary>
    /// Extract package name from AndroidManifest.xml (handles UTF-8 / UTF-16 / binary XML)
    /// </summary>
    public static string? ExtractPackageName(string path)
    {
        try
        {
            if (path.EndsWith(".xapk", StringComparison.OrdinalIgnoreCase))
            {
                using var xapk = ZipFile.OpenRead(path);
                var apkEntry = xapk.Entries.FirstOrDefault(e => e.FullName.EndsWith(".apk", StringComparison.OrdinalIgnoreCase));
                if (apkEntry == null)
                    return null;

                using var s = apkEntry.Open();
                using var z = new ZipArchive(s, ZipArchiveMode.Read);
                return ExtractPackageNameFromApk(z);
            }

            if (path.EndsWith(".apk", StringComparison.OrdinalIgnoreCase))
            {
                using var z = ZipFile.OpenRead(path);
                return ExtractPackageNameFromApk(z);
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[WARN] Failed to parse AndroidManifest: {ex.Message}");
        }

        return null;
    }

    private static string? ExtractPackageNameFromApk(ZipArchive apk)
    {
        var manifest = apk.GetEntry("AndroidManifest.xml");
        if (manifest == null)
            return null;

        using var stream = manifest.Open();
        return ManifestParser.TryGetPackageName(stream);
    }

    /// <summary>
    /// Fallback: find package name by guessing largest `.apk` or jp/com pattern.
    /// </summary>
    private static string? GuessPackageNameFromXapkOrPath(string path)
    {
        try
        {
            if (path.EndsWith(".xapk", StringComparison.OrdinalIgnoreCase))
            {
                using var zip = ZipFile.OpenRead(path);
                var apks = zip.Entries
                    .Where(e => e.FullName.EndsWith(".apk", StringComparison.OrdinalIgnoreCase))
                    .OrderByDescending(e => e.Length)
                    .ToList();

                var jpOrCom = apks.FirstOrDefault(e =>
                    e.Name.StartsWith("jp.", StringComparison.OrdinalIgnoreCase) ||
                    e.Name.StartsWith("com.", StringComparison.OrdinalIgnoreCase));

                var best = jpOrCom ?? apks.FirstOrDefault();
                if (best != null)
                {
                    var baseName = Path.GetFileNameWithoutExtension(best.Name);
                    if (Regex.IsMatch(baseName, @"^(jp|com)\.[\w\.]+$"))
                        return baseName;
                }
            }

            // fallback to filename itself
            var filename = Path.GetFileNameWithoutExtension(path);
            if (Regex.IsMatch(filename, @"^(jp|com)\.[\w\.]+$"))
                return filename;
        }
        catch { }

        return null;
    }
}
