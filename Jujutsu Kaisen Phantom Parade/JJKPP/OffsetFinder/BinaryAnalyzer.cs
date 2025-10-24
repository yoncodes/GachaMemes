using AsmResolver;
using AsmResolver.IO;
using static OffsetFinder.IL2CPPFinder;

namespace OffsetFinder;

public record AnalysisResult(
    UnityVersion Version,
    List<PatternMatch> Matches,
    TimeSpan AnalysisTime,
    GameInfo? DetectedGame = null,
    List<ExtractedData>? ExtractedData = null
);


public class BinaryAnalyzer
{
    public AnalysisResult Analyze(string binaryPath, string? metadataPath = null)
    {
        var startTime = DateTime.UtcNow;

        // Detect Unity version
        var version = VersionDetector.Detect(binaryPath, metadataPath);

        if (!version.MetadataVersion.HasValue)
            throw new InvalidOperationException("Could not determine Unity metadata version");

        // Load executable segment
        var (segmentData, baseAddress) = LoadExecutableSegment(binaryPath);

        // Get patterns for this version
        var patterns = PatternDatabase.GetPatterns(version.MetadataVersion.Value);

        // Find matches
        var matches = new List<PatternMatch>();

        foreach (var pattern in patterns)
        {
            // Try symbol resolution first (if available)
            var symbolAddress = ResolveSymbol(binaryPath, pattern.Name);
            if (symbolAddress.HasValue)
            {
                matches.Add(new PatternMatch(pattern.Name, symbolAddress.Value, "symbol"));
                continue;
            }

            // Pattern matching
            var addresses = pattern.FindAll(segmentData, baseAddress);
            if (addresses.Count > 0)
            {
                matches.Add(new PatternMatch(pattern.Name, addresses[0], "pattern"));
            }
        }

        var elapsed = DateTime.UtcNow - startTime;
        return new AnalysisResult(version, matches, elapsed);
    }

    private (byte[] Data, long BaseAddress) LoadExecutableSegment(string path)
    {
        var fileData = File.ReadAllBytes(path);

        if (fileData.Length > 4 && fileData[0] == 0x7F && fileData[1] == 0x45 &&
            fileData[2] == 0x4C && fileData[3] == 0x46)
        {
            return LoadElfSegment(fileData);
        }

        return (fileData, 0);
    }

    private (byte[] Data, long BaseAddress) LoadElfSegment(byte[] fileData)
    {
        try
        {
            var reader = new AsmResolver.IO.BinaryStreamReader(fileData);

            reader.Offset = 0;
            var magic = reader.ReadUInt32();
            var elfClass = reader.ReadByte();
            var endianness = reader.ReadByte();
            var version = reader.ReadByte();

            bool is64Bit = elfClass == 2;

            reader.Offset = (ulong)(is64Bit ? 0x20 : 0x1C);
            long phOffset = is64Bit ? (long)reader.ReadUInt64() : reader.ReadUInt32();

            reader.Offset = (ulong)(is64Bit ? 0x38 : 0x2C);
            ushort phNum = reader.ReadUInt16();
            ushort phEntSize = reader.ReadUInt16();

            for (int i = 0; i < phNum; i++)
            {
                reader.Offset = (ulong)(phOffset + i * phEntSize);

                uint pType = reader.ReadUInt32();
                if (pType != 1) // PT_LOAD
                    continue;

                uint pFlags = is64Bit ? reader.ReadUInt32() : 0;
                long pOffset = is64Bit ? (long)reader.ReadUInt64() : reader.ReadUInt32();
                long pVaddr = is64Bit ? (long)reader.ReadUInt64() : reader.ReadUInt32();
                reader.ReadUInt64(); // skip p_paddr
                long pFilesz = is64Bit ? (long)reader.ReadUInt64() : reader.ReadUInt32();
                if (!is64Bit)
                    pFlags = reader.ReadUInt32();

                bool executable = (pFlags & 0x1) != 0;
                if (!executable || pFilesz <= 0)
                    continue;

               
                long baseAddress = pVaddr - pOffset;

                var segment = new byte[pFilesz];
                Array.Copy(fileData, pOffset, segment, 0, pFilesz);

                //Console.WriteLine($"[DEBUG] [ELF] exec segment offset=0x{pOffset:X}, vaddr=0x{pVaddr:X}, size=0x{pFilesz:X}, base=0x{baseAddress:X}");

                return (segment, baseAddress);
            }
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"Failed to parse ELF: {ex.Message}");
        }

        throw new InvalidOperationException("No executable segment found in ELF");
    }


    private long? ResolveSymbol(string binaryPath, string symbolName)
    {
        // Symbols are often stripped in release APKs
        // This is a placeholder for symbol resolution
        return null;
    }
}