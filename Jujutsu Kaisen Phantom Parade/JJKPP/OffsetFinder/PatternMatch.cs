using System;

namespace OffsetFinder;

public record PatternMatch(string Name, long Address, string Source);

public class WildcardPattern
{
    public string Name { get; }
    private readonly byte[] _pattern;
    private readonly bool[] _mask;

    public WildcardPattern(string name, string patternString)
    {
        Name = name;
        var parts = patternString.Split(' ', StringSplitOptions.RemoveEmptyEntries);

        _pattern = new byte[parts.Length];
        _mask = new bool[parts.Length];

        for (int i = 0; i < parts.Length; i++)
        {
            if (parts[i] == "??")
            {
                _pattern[i] = 0;
                _mask[i] = false;
            }
            else
            {
                _pattern[i] = Convert.ToByte(parts[i], 16);
                _mask[i] = true;
            }
        }
    }

    public List<long> FindAll(ReadOnlySpan<byte> data, long baseAddress = 0)
    {
        var matches = new List<long>();
        int patternLength = _pattern.Length;

        // Optimize: find first fixed byte
        int firstFixedIndex = Array.IndexOf(_mask, true);
        if (firstFixedIndex == -1)
            return matches; // all wildcards (useless pattern)

        byte firstByte = _pattern[firstFixedIndex];

        for (int i = 0; i <= data.Length - patternLength; i++)
        {
            if (data[i + firstFixedIndex] != firstByte)
                continue;

            if (MatchesAt(data, i))
                matches.Add(baseAddress + i);
        }

        return matches;
    }

    private bool MatchesAt(ReadOnlySpan<byte> data, int offset)
    {
        for (int i = 0; i < _pattern.Length; i++)
        {
            if (_mask[i] && data[offset + i] != _pattern[i])
                return false;
        }
        return true;
    }
}

public static class PatternDatabase
{
    /// <summary>
    /// Get patterns for a specific metadata version and game.
    /// If the game is not supported, throw an exception immediately.
    /// </summary>
    public static List<WildcardPattern> GetPatterns(int metadataVersion, GameInfo? game = null)
    {
        if (game == null)
            throw new NotSupportedException("No game detected — this title is not supported by OffsetFinder.");

        var shortName = game.ShortName.ToLowerInvariant();

        return shortName switch
        {
            "jjkppjp" => GetJJKPatterns(metadataVersion),
            "jjkppgl" => GetJJKGLPatterns(metadataVersion),
            // Add future games here:
            // "bd2jp" => GetBrownDust2Patterns(metadataVersion),
            // "yuridori" => GetYuridoriPatterns(metadataVersion),
            _ => throw new NotSupportedException($"Game '{game.Name}' is not yet supported by OffsetFinder.")
        };
    }

    /// <summary>
    /// Jujutsu Kaisen Phantom Parade (Japan) — tested, known patterns
    /// </summary>
    private static List<WildcardPattern> GetJJKPatterns(int metadataVersion)
    {
        var patterns = new List<WildcardPattern>();

        patterns.Add(new WildcardPattern(
            "s_GlobalMetadata",
            "?? ?? 04 ?? A0 ?? ?? F9 ?? 0C 00 B4 ?? ?? 04 ?? C0 ?? ?? F9"
        ));

        patterns.Add(new WildcardPattern(
            "s_CodeMetadataBlock",
            "?? ?? 04 ?? 21 ?? ?? F9 ?? ?? ?? ?? ?? ?? ?? ?? 00 ?? ?? 91 42 ?? ?? 91 ?? ?? ?? 14"
        ));

        patterns.Add(new WildcardPattern(
            "jjk_encryption_key_ref",
            "?? ?? 02 ?? E8 03 1F AA 29 ?? ?? 91"
        ));

        return patterns;
    }

    /// <summary>
    /// Jujutsu Kaisen Phantom Parade (Japan) — tested, known patterns
    /// </summary>
    private static List<WildcardPattern> GetJJKGLPatterns(int metadataVersion)
    {
        var patterns = new List<WildcardPattern>();

        patterns.Add(new WildcardPattern(
            "s_GlobalMetadata",
            "?? ?? ?? ?? A0 ?? ?? F9 ?? ?? 00 B4 ?? ?? ?? ?? C0 ?? ?? F9"
        ));

        patterns.Add(new WildcardPattern(
            "jjk_encryption_key_ref",
            "?? ?? 02 ?? E8 03 1F AA 29 ?? ?? 91"
        ));

        return patterns;
    }
}
