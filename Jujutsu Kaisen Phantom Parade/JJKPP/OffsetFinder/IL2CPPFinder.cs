namespace OffsetFinder;

public class IL2CPPFinder
{
    public AnalysisResult AnalyzeApk(string apkPath, string? targetArch = "arm64")
    {
        if (apkPath.EndsWith(".xapk", StringComparison.OrdinalIgnoreCase))
        {
            return AnalyzeXapk(apkPath, targetArch);
        }

        using var apk = new ApkExtractor(apkPath);

        var metadata = apk.ExtractMetadata();
        if (metadata == null)
            throw new InvalidOperationException("global-metadata.dat not found in APK");

        var libs = apk.FindNativeLibraries();
        var targetLib = libs.FirstOrDefault(l =>
            l.Name.Contains("il2cpp") && l.Architecture == targetArch)
            ?? libs.FirstOrDefault(l => l.Name.Contains("il2cpp"));

        if (targetLib == null)
            throw new InvalidOperationException("libil2cpp.so not found in APK");

        var tempLib = Path.GetTempFileName();
        var tempMeta = Path.GetTempFileName();

        try
        {
            var libData = apk.ExtractLibrary(targetLib.Name);
            if (libData == null)
                throw new InvalidOperationException($"Failed to extract {targetLib.Name}");

            File.WriteAllBytes(tempLib, libData);
            File.WriteAllBytes(tempMeta, metadata);

            return AnalyzeInternal(tempLib, tempMeta, apkPath);
        }
        finally
        {
            try { File.Delete(tempLib); } catch { }
            try { File.Delete(tempMeta); } catch { }
        }
    }

    public AnalysisResult AnalyzeXapk(string xapkPath, string? targetArch = "arm64")
    {
        using var xapk = new XapkExtractor(xapkPath);

        var metadata = xapk.ExtractMetadata();
        if (metadata == null)
        {
            var apkInfos = xapk.GetApkInfo();
            throw new InvalidOperationException(
                "global-metadata.dat not found in XAPK\n" +
                $"APKs found: {string.Join(", ", apkInfos.Select(a => a.Name))}"
            );
        }

        var il2cppLib = xapk.ExtractIl2CppLibrary(targetArch);
        if (il2cppLib == null)
        {
            var apkInfos = xapk.GetApkInfo();
            var availableArchs = apkInfos.Where(a => a.Architecture != null)
                .Select(a => a.Architecture)
                .Distinct();

            throw new InvalidOperationException(
                $"libil2cpp.so not found for '{targetArch}' in XAPK\n" +
                $"Available: {string.Join(", ", availableArchs)}"
            );
        }

        var tempLib = Path.GetTempFileName();
        var tempMeta = Path.GetTempFileName();

        try
        {
            File.WriteAllBytes(tempLib, il2cppLib);
            File.WriteAllBytes(tempMeta, metadata);

            return AnalyzeInternal(tempLib, tempMeta, xapkPath);
        }
        finally
        {
            try { File.Delete(tempLib); } catch { }
            try { File.Delete(tempMeta); } catch { }
        }
    }

    public record ExtractedData(string Name, long Address, byte[] Data);

    private AnalysisResult AnalyzeInternal(string libPath, string metadataPath, string? originalPath = null)
    {
        var startTime = DateTime.UtcNow;

        // Detect Unity version
        UnityVersion version;
        if (originalPath != null &&
            (originalPath.EndsWith(".apk", StringComparison.OrdinalIgnoreCase) ||
             originalPath.EndsWith(".xapk", StringComparison.OrdinalIgnoreCase)))
        {
            version = VersionDetector.DetectFromApk(originalPath, metadataPath);
        }
        else
        {
            version = VersionDetector.Detect(libPath, metadataPath);
        }

        if (!version.MetadataVersion.HasValue)
        {
            throw new InvalidOperationException(
                "Could not determine Unity metadata version\n" +
                $"Version string: {version.FullString ?? "not found"}\n" +
                $"Encrypted metadata: {version.IsMetadataEncrypted}"
            );
        }

        // Detect game (optional)
        GameInfo? game = null;
        if (originalPath != null)
        {
            game = GameDetector.DetectGame(originalPath);

            if (game == null)
            {
                var packageName = GameDetector.ExtractPackageName(originalPath);
                if (packageName != null)
                    game = GameDetector.DetectGameFromPackage(packageName);
            }
        }

        // Load segment data from binary
        var (segmentData, baseAddress) = LoadExecutableSegment(libPath);
        //Console.WriteLine($"[DEBUG] Loaded ELF base address: 0x{baseAddress:X}");

        // Load patterns
        var patterns = PatternDatabase.GetPatterns(version.MetadataVersion.Value, game);
        var matches = new List<PatternMatch>();
        var follower = new InstructionFollower(segmentData, baseAddress);
        var extractedData = new List<ExtractedData>();

        // Run all pattern matches
        foreach (var pattern in patterns)
        {
            var addresses = pattern.FindAll(segmentData, baseAddress);
            if (addresses.Count == 0)
                continue;

            var addr = addresses[0];
            long finalAddr = addr; // what will be displayed in the table

            // Special logic for s_GlobalMetadata: resolve qword pointer
            if (pattern.Name.Equals("s_GlobalMetadata", StringComparison.OrdinalIgnoreCase))
            {
                long fileOff = addr - baseAddress;
                long? resolved = null;

                if (follower.IsADRP(fileOff))
                {
                    // ADRP + LDR/STR case
                    resolved = follower.FollowADRP_LDR_STR_Address(fileOff, derefGOT: true);
                }
                else
                {
                    // Maybe pattern already points at a qword (GOT or global) — try to read it
                    resolved = follower.TryReadPointerVA(addr);

                    if (resolved == null)
                    {
                        // Try to find the ADRP just before this site (compiler layout variance)
                        var backAdrp = follower.FindNearestADRPBefore(fileOff, 0x20);
                        if (backAdrp != null)
                            resolved = follower.FollowADRP_LDR_STR_Address(backAdrp.Value, derefGOT: true);
                    }
                }

                if (resolved != null)
                {
                    //Console.WriteLine($"[INFO] Resolved s_GlobalMetadata qword: 0x{resolved.Value:X}");
                    finalAddr = resolved.Value; // show the true pointer in the table
                }
                else
                {
                    Console.WriteLine($"[WARN] Failed to resolve qword for s_GlobalMetadata @ 0x{addr:X}");
                }
            }


            matches.Add(new PatternMatch(pattern.Name, finalAddr, "pattern"));

            // If encryption pattern → follow ADRP/ADD to extract data
            if (pattern.Name.Contains("encryption", StringComparison.OrdinalIgnoreCase))
            {
                var adrpOffset = addr - baseAddress;

                var data = follower.FollowADRP_ADD(adrpOffset, 128);
                if (data == null)
                {
                    var qwordAddr = follower.FollowADRP_LDR_STR_Address(adrpOffset);
                    if (qwordAddr != null)
                    {
                        Console.WriteLine($"[INFO] {pattern.Name} references qword 0x{qwordAddr:X}");
                        extractedData.Add(new ExtractedData(
                            pattern.Name + "_address",
                            addr,
                            BitConverter.GetBytes(qwordAddr.Value)
                        ));
                    }
                }
                else
                {
                    extractedData.Add(new ExtractedData(
                        pattern.Name + "_data",
                        addr,
                        data
                    ));
                }
            }

            if (pattern.Name == "s_CodeMetadataBlock")
            {
                var adrpOffset = addr - baseAddress;

                var codeRegAddr = follower.FollowADRP_ADD_Addr(adrpOffset + 8, adrpOffset + 0x10);
                var metaRegAddr = follower.FollowADRP_ADD_Addr(adrpOffset + 8, adrpOffset + 0x14);
                var optionsAddr = follower.FollowADRP_LDR_STR_Address(adrpOffset, derefGOT: true);

                // Add resolved addresses to final table results
                if (codeRegAddr.HasValue)
                {
                    matches.Add(new PatternMatch("s_CodeRegistration", codeRegAddr.Value, "resolved"));
                    //Console.WriteLine($"[+] s_CodeRegistration     → 0x{codeRegAddr:X}");
                }
                else
                {
                    Console.WriteLine("[WARN] Failed to resolve s_CodeRegistration");
                }

                if (metaRegAddr.HasValue)
                {
                    matches.Add(new PatternMatch("s_MetadataRegistration", metaRegAddr.Value, "resolved"));
                    //Console.WriteLine($"[+] s_MetadataRegistration → 0x{metaRegAddr:X}");
                }
                else
                {
                    Console.WriteLine("[WARN] Failed to resolve s_MetadataRegistration");
                }

                if (optionsAddr.HasValue)
                {
                    matches.Add(new PatternMatch("s_Il2CppCodeGenOptions", optionsAddr.Value, "resolved"));
                    //Console.WriteLine($"[+] s_Il2CppCodeGenOptions → 0x{optionsAddr:X}");
                }
                else
                {
                    Console.WriteLine("[WARN] Failed to resolve s_Il2CppCodeGenOptions");
                }
            }


        }

        if (version.IsMetadataEncrypted && extractedData.Any())
        {
            try
            {
                var keyEntry = extractedData.FirstOrDefault(d =>
                    d.Name.Contains("key", StringComparison.OrdinalIgnoreCase) ||
                    d.Name.Contains("encrypt", StringComparison.OrdinalIgnoreCase));

                if (keyEntry != null)
                {
                    //Console.WriteLine($"\n[INFO] Detected metadata encryption — decrypting using {keyEntry.Name}...\n");

                    var metaBytes = File.ReadAllBytes(metadataPath);
                    var decrypted = Decryptor.Decrypt(keyEntry.Data, metaBytes);

                    var outDir = Path.Combine(Environment.CurrentDirectory, "extracted");
                    Directory.CreateDirectory(outDir);
                    var outPath = Path.Combine(outDir, "global-metadata-decrypted.dat");

                    File.WriteAllBytes(outPath, decrypted);
                    Console.WriteLine($"[INFO] ✓ Decrypted metadata written to: {outPath}");
                }
                else
                {
                    Console.WriteLine("[WARN] Metadata marked as encrypted but no encryption key found!");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Metadata decryption failed: {ex.Message}");
            }
        }
        // === End decryption logic ===

        var elapsed = DateTime.UtcNow - startTime;
        return new AnalysisResult(version, matches, elapsed, game, extractedData);
    }



    public AnalysisResult AnalyzeBinary(string binaryPath, string? metadataPath = null)
    {
        var tempLib = binaryPath;
        var tempMeta = metadataPath ?? Path.GetTempFileName();

        try
        {
            return AnalyzeInternal(tempLib, tempMeta, null);
        }
        finally
        {
            if (metadataPath == null)
            {
                try { File.Delete(tempMeta); } catch { }
            }
        }
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

                // === Correct rva_base computation (matches goblin) ===
                long baseAddress = pVaddr - pOffset;

                // === Slice only the segment bytes (like Rust does) ===
                var segment = new byte[pFilesz];
                Array.Copy(fileData, pOffset, segment, 0, pFilesz);

               // Console.WriteLine($"[DEBUG] [ELF] exec segment offset=0x{pOffset:X}, vaddr=0x{pVaddr:X}, size=0x{pFilesz:X}, base=0x{baseAddress:X}");

                return (segment, baseAddress);
            }
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException($"Failed to parse ELF: {ex.Message}");
        }

        throw new InvalidOperationException("No executable segment found in ELF");
    }



    public List<WildcardPattern> GetPatterns(int metadataVersion, GameInfo? game = null)
    {
        return PatternDatabase.GetPatterns(metadataVersion, game);
    }

    public UnityVersion DetectVersion(string binaryPath, string? metadataPath = null)
    {
        return VersionDetector.Detect(binaryPath, metadataPath);
    }

    public List<XapkApkInfo> GetXapkInfo(string xapkPath)
    {
        using var xapk = new XapkExtractor(xapkPath);
        return xapk.GetApkInfo();
    }

    public GameInfo? DetectGame(string path)
    {
        return GameDetector.DetectGame(path);
    }
}