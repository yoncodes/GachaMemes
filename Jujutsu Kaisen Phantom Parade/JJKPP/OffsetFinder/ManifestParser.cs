using System.Text;
using System.Text.RegularExpressions;

namespace OffsetFinder;

public static class ManifestParser
{
    public static string? TryGetPackageName(Stream manifestStream)
    {
        using var ms = new MemoryStream();
        manifestStream.CopyTo(ms);
        var data = ms.ToArray();

        //Console.WriteLine($"[DEBUG] Manifest size: {data.Length} bytes");
        //Console.WriteLine($"[DEBUG] First bytes: {BitConverter.ToString(data.Take(8).ToArray())}");

        // ===========================================================
        // STEP 1 — Quick XML Scan (works even inside binary AXML)
        // ===========================================================
        try
        {
            var rawText = Encoding.UTF8.GetString(data);
            var xmlMatch = Regex.Match(rawText, @"package\s*=\s*""([^""]+)""");
            if (xmlMatch.Success)
            {
                var foundPkg = xmlMatch.Groups[1].Value;
                //Console.WriteLine($"[DEBUG] Found package via direct XML scan: {foundPkg}");
                return foundPkg;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[DEBUG] XML scan failed: {ex.Message}");
        }

        // ===========================================================
        // STEP 2 — Text-Based XML Decode (UTF-8 / UTF-16)
        // ===========================================================
        try
        {
            var encoding = DetectEncoding(data);
            Console.WriteLine($"[DEBUG] Trying text parse with {encoding.EncodingName}...");

            var text = encoding.GetString(data)
                .Trim('\0', ' ', '\r', '\n', '\t')
                .Replace("\r", "")
                .Replace("\n", " ");

            var match = Regex.Match(
                text,
                @"<manifest[^>]*\s+package\s*=\s*""([^""]+)""",
                RegexOptions.IgnoreCase
            );

            if (match.Success)
            {
                var pkg = match.Groups[1].Value;
                Console.WriteLine($"[DEBUG] Found package via text XML: {pkg}");
                return pkg;
            }

            //Console.WriteLine("[DEBUG] Text parse failed: no <manifest ... package=\"...\"> match found");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[DEBUG] Text parse threw exception: {ex.Message}");
        }

        // ===========================================================
        // STEP 3 — Binary AXML Decode
        // ===========================================================
        try
        {
            Console.WriteLine("[DEBUG] Falling back to binary AXML parse...");
            var pkg = ParseBinaryAXML(data);
            if (!string.IsNullOrEmpty(pkg))
            {
                //Console.WriteLine($"[DEBUG] Found package via binary AXML: {pkg}");
                return pkg;
            }

            Console.WriteLine("[DEBUG] Binary parse failed: no package found");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[DEBUG] Binary manifest parse failed: {ex.Message}");
        }

        //Console.WriteLine("[DEBUG] ManifestParser failed to detect any package name");
        return null;
    }

    // ===============================================================
    // Encoding Detection
    // ===============================================================
    private static Encoding DetectEncoding(byte[] data)
    {
        if (data.Length >= 3 && data[0] == 0xEF && data[1] == 0xBB && data[2] == 0xBF)
        {
            //Console.WriteLine("[DEBUG] Detected UTF-8 BOM");
            return new UTF8Encoding(true);
        }
        if (data.Length >= 2)
        {
            if (data[0] == 0xFF && data[1] == 0xFE)
            {
                Console.WriteLine("[DEBUG] Detected UTF-16 LE BOM");
                return Encoding.Unicode;
            }
            if (data[0] == 0xFE && data[1] == 0xFF)
            {
                Console.WriteLine("[DEBUG] Detected UTF-16 BE BOM");
                return Encoding.BigEndianUnicode;
            }
        }

        Console.WriteLine("\n[DEBUG] Defaulting to UTF-8 (no BOM found)");
        return new UTF8Encoding(false);
    }

    // ===============================================================
    // Binary Manifest (AXML) Parsing
    // ===============================================================
    private static string? ParseBinaryAXML(byte[] data)
    {
        try
        {
            // Validate header signature (0x00080003)
            if (data.Length < 8 || BitConverter.ToUInt32(data, 0) != 0x00080003)
            {
                Console.WriteLine("[DEBUG] Not a binary AXML file (missing header 0x00080003)");
                return null;
            }

            int offset = 8;
            int maxScan = Math.Min(data.Length - 8, 0x8000); // scan first 32KB
            bool found = false;

            while (offset + 8 < data.Length && offset < maxScan)
            {
                ushort chunkType = BitConverter.ToUInt16(data, offset);
                ushort headerSize = BitConverter.ToUInt16(data, offset + 2);
                int chunkSize = BitConverter.ToInt32(data, offset + 4);

                if (chunkSize <= 0 || chunkSize > data.Length - offset)
                    break;

                //Console.WriteLine($"[DEBUG] Chunk @0x{offset:X}: Type=0x{chunkType:X4}, Header=0x{headerSize:X4}, Size=0x{chunkSize:X}");

                if (chunkType == 0x0001) // RES_STRING_POOL_TYPE
                {
                    //Console.WriteLine($"[DEBUG] Found StringPool chunk @ 0x{offset:X}");
                    found = true;
                    return ParseStringPoolForPackage(data, offset, chunkSize);
                }

                offset += ((chunkSize + 3) / 4) * 4; // 4-byte alignment
            }

            if (!found)
                Console.WriteLine("[DEBUG] No StringPool chunk found within 32KB window");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[DEBUG] Binary AXML parse exception: {ex.Message}");
        }

        return null;
    }

    // ===============================================================
    // String Pool Parser (binary AXML)
    // ===============================================================
    private static string? ParseStringPoolForPackage(byte[] data, int offset, int chunkSize)
    {
        int stringCount = BitConverter.ToInt32(data, offset + 8);
        int flags = BitConverter.ToInt32(data, offset + 16);
        int stringsStart = BitConverter.ToInt32(data, offset + 20);

        bool isUtf8 = (flags & 0x100) != 0;
        Console.WriteLine($"[DEBUG] StringPool: Count={stringCount}, UTF8={isUtf8}, stringsStart=0x{stringsStart:X}");

        var results = new List<string>();

        for (int i = 0; i < stringCount; i++)
        {
            int strOffset = BitConverter.ToInt32(data, offset + 28 + i * 4);
            int stringPos = offset + stringsStart + strOffset;
            if (stringPos >= data.Length)
                continue;

            string decoded;
            try
            {
                if (isUtf8)
                {
                    int u8len = data[stringPos];
                    stringPos += (u8len >= 0x80) ? 2 : 1;
                    int byteLen = data[stringPos];
                    stringPos += (byteLen >= 0x80) ? 2 : 1;
                    decoded = Encoding.UTF8.GetString(data, stringPos, byteLen);
                }
                else
                {
                    int u16len = BitConverter.ToUInt16(data, stringPos);
                    decoded = Encoding.Unicode.GetString(data, stringPos + 2, u16len * 2);
                }
                if (!string.IsNullOrWhiteSpace(decoded))
                    results.Add(decoded);
            }
            catch { /* ignore bad entries */ }
        }

        //foreach (var s in results.Take(10))
            //Console.WriteLine($"[DEBUG] StringPool sample: {s}");

        // Match package names with at least 2 segments
        var candidates = results
            .Where(s => Regex.IsMatch(s, @"^[a-z]{2,}\.[a-z0-9_]+(\.[a-z0-9_]+)*$", RegexOptions.IgnoreCase))
            .Distinct()
            .ToList();

        if (candidates.Count == 0)
        {
            Console.WriteLine("[DEBUG] No package-like strings found in StringPool");
            return null;
        }

        //Console.WriteLine("[DEBUG] Initial candidate package strings: " +
           // string.Join(", ", candidates.Take(10)) +
            //(candidates.Count > 10 ? $", ... ({candidates.Count} total)" : ""));

        // Filter out SDK/library packages and Android system packages
        var filtered = candidates
            .Where(s =>
                !Regex.IsMatch(s,
                    @"\b(adjust|facebook|appsflyer|firebase|google|vending|android|twitter|unity|base|sdk|adcolony|applovin|iron|chartboost|gameanalytics|tencent|huawei|androidx|kotlinx|onevcat|uniwebview|sentry)\b",
                    RegexOptions.IgnoreCase)
            )
            .ToList();

        // CRITICAL: Remove strings that are clearly class names (end with Activity, Provider, Receiver, Service, etc.)
        var packageOnly = filtered
            .Where(s =>
            {
                var lastSegment = s.Split('.').Last();
                // Exclude if last segment looks like a class name (starts with uppercase or contains Activity/Provider/etc)
                return !Regex.IsMatch(lastSegment,
                    @"^[A-Z]|Activity$|Provider$|Receiver$|Service$|Application$|Broadcast$|Manager$|Handler$|Listener$",
                    RegexOptions.IgnoreCase);
            })
            .ToList();

        // Clean suffixes for remaining candidates
        var cleaned = packageOnly
            .Select(s =>
            {
                // Remove trailing .permission.*, .receiver.*, etc.
                var m = Regex.Match(
                    s,
                    @"^(?<base>[a-z]{2,}\.[a-z0-9_]+(\.[a-z0-9_]+)*?)\.(permission|receiver|activity|service|provider|exported|broadcast|fileprovider)(\.|$)",
                    RegexOptions.IgnoreCase);
                if (m.Success)
                    return m.Groups["base"].Value;

                // Remove final uppercase snake-case segments
                var parts = s.Split('.');
                if (parts.Length > 2)
                {
                    var lastPart = parts.Last();
                    if (Regex.IsMatch(lastPart, @"^[A-Z0-9_]+$") && lastPart.Length > 3)
                    {
                        return string.Join(".", parts.Take(parts.Length - 1));
                    }
                }

                return s;
            })
            .Distinct()
            .Where(s => s.Split('.').Length >= 2)
            .ToList();

        // If we filtered too aggressively, fall back
        if (cleaned.Count == 0 && packageOnly.Count > 0)
            cleaned = packageOnly;
        if (cleaned.Count == 0 && filtered.Count > 0)
            cleaned = filtered;
        if (cleaned.Count == 0)
            cleaned = candidates.Take(20).ToList();

        //Console.WriteLine("[DEBUG] Cleaned candidate strings: " +
            //string.Join(", ", cleaned.Take(10)) +
            //(cleaned.Count > 10 ? $", ... ({cleaned.Count} total)" : ""));

        // Scoring system
        var scored = cleaned
            .Select(s => new
            {
                Package = s,
                Score = CalculatePackageScore(s, cleaned)
            })
            .OrderByDescending(x => x.Score)
            .ThenBy(x => x.Package) // Stable sort
            .ToList();

        //foreach (var item in scored.Take(5))
            //Console.WriteLine($"[DEBUG] Score {item.Score}: {item.Package}");

        string? pkg = scored.FirstOrDefault()?.Package;

        //Console.WriteLine($"[DEBUG] Selected package: {pkg}");
        return pkg;
    }

    private static int CalculatePackageScore(string package, List<string> allCandidates)
    {
        int score = 0;
        var parts = package.Split('.');

        // MAJOR bonus for packages with 3-5 segments (typical app structure)
        if (parts.Length >= 3 && parts.Length <= 5)
            score += 200;
        else if (parts.Length == 2)
            score += 80;
        else if (parts.Length > 5)
            score += 50;

        // CRITICAL: Check if this is a base package (other packages start with it)
        int dependentCount = allCandidates.Count(c =>
            c != package &&
            c.StartsWith(package + ".", StringComparison.OrdinalIgnoreCase));

        if (dependentCount > 0)
        {
            // This is likely the base app package!
            score += 300 + (dependentCount * 10); // More dependents = more likely to be base
            Console.WriteLine($"[DEBUG] {package} has {dependentCount} dependent packages");
        }

        // Bonus for common TLDs
        if (Regex.IsMatch(parts[0], @"^(com|org|net|io|app)$", RegexOptions.IgnoreCase))
            score += 30;

        // Penalty for very short last segment (likely incomplete)
        var lastSegment = parts.Last();
        if (lastSegment.Length <= 2)
            score -= 100;

        // Penalty for generic-looking final segments
        if (Regex.IsMatch(lastSegment, @"^(app|main|core|base|lib|util|utils|common|test|debug)$", RegexOptions.IgnoreCase))
            score -= 50;

        // Penalty for prefix-only packages (like "cct.com.something")
        if (parts[0].Length <= 3 && !Regex.IsMatch(parts[0], @"^(com|org|net|app|dev|pro|xyz)$", RegexOptions.IgnoreCase))
            score -= 80;

        // Bonus for alphanumeric variety (real app packages aren't all lowercase)
        if (Regex.IsMatch(package, @"[0-9]"))
            score += 20;

        return score;
    }
}
