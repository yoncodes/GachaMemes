using System.Buffers.Binary;

namespace OffsetFinder;

/// <summary>
/// Follows ARM64 instructions like ADRP and extracts data from resolved addresses
/// </summary>
public class InstructionFollower
{
    private readonly byte[] _elfData;
    private readonly long _baseAddress;

    public InstructionFollower(byte[] elfData, long baseAddress)
    {
        _elfData = elfData;
        _baseAddress = baseAddress;
    }

    /// <summary>
    /// Follow ADRP instruction and extract data from the target address
    /// </summary>
    /// <param name="instructionOffset">Offset of the ADRP instruction in the ELF</param>
    /// <param name="dataLength">How many bytes to extract</param>
    /// <returns>The bytes at the resolved address, or null if failed</returns>
    public byte[]? FollowADRP(long instructionOffset, int dataLength = 347)
    {
        try
        {
            // Read the instruction (4 bytes for ARM64)
            if (instructionOffset + 4 > _elfData.Length)
                return null;

            uint instruction = BinaryPrimitives.ReadUInt32LittleEndian(
                _elfData.AsSpan((int)instructionOffset, 4)
            );

            // Check if it's ADRP (opcode 0x90000000 with mask 0x9F000000)
            if ((instruction & 0x9F000000) != 0x90000000)
                return null;

            // Extract register and immediate
            int rd = (int)(instruction & 0x1F);
            long immhi = (instruction >> 5) & 0x7FFFF;
            long immlo = (instruction >> 29) & 0x3;

            // Combine immediate (21 bits total, shifted left by 12)
            long imm = ((immhi << 2) | immlo) << 12;

            // Sign extend if negative (bit 20 is sign bit)
            if ((imm & 0x100000000) != 0)
                imm |= unchecked((long)0xFFFFFFFE00000000);

            // Calculate target address
            // ADRP: PC + (imm << 12) with PC page-aligned
            long pc = _baseAddress + instructionOffset;
            long pcPage = pc & ~0xFFF; // Page align PC
            long targetAddress = pcPage + imm;

            // Convert to file offset
            long fileOffset = targetAddress - _baseAddress;

            if (fileOffset < 0 || fileOffset + dataLength > _elfData.Length)
                return null;

            // Extract the data
            var data = new byte[dataLength];
            Array.Copy(_elfData, fileOffset, data, 0, dataLength);

            return data;
        }
        catch
        {
            return null;
        }
    }

    /// <summary>
    /// Find pattern, then follow ADRP and extract data
    /// </summary>
    public (long address, byte[] data)? FindAndFollowADRP(
        WildcardPattern pattern,
        int adrpOffsetInMatch = 0,
        int dataLength = 128)
    {
        var matches = pattern.FindAll(_elfData, _baseAddress);

        foreach (var matchAddress in matches)
        {
            long fileOffset = matchAddress - _baseAddress;
            long adrpOffset = fileOffset + adrpOffsetInMatch;

            var data = FollowADRP(adrpOffset, dataLength);
            if (data != null)
            {
                return (matchAddress, data);
            }
        }

        return null;
    }

    /// <summary>
    /// Follow ADD instruction (adds immediate to register)
    /// Commonly used after ADRP to get the final address
    /// </summary>
    public long? FollowADD(long instructionOffset)
    {
        try
        {
            if (instructionOffset + 4 > _elfData.Length)
                return null;

            uint instruction = BinaryPrimitives.ReadUInt32LittleEndian(
                _elfData.AsSpan((int)instructionOffset, 4)
            );

            // Check if it's ADD immediate (opcode 0x91000000 with mask 0xFF000000)
            if ((instruction & 0xFF000000) != 0x91000000)
                return null;

            // Extract immediate (12 bits)
            long imm = (instruction >> 10) & 0xFFF;

            // Check shift bit (bit 22)
            if ((instruction & 0x400000) != 0)
                imm <<= 12;

            return imm;
        }
        catch
        {
            return null;
        }
    }

    /// <summary>
    /// Follow ADRP + ADD sequence to get final address and (optionally) extract data.
    /// </summary>
    public byte[]? FollowADRP_ADD(long adrpOffset, long dataLength = 128, int searchRange = 24, bool resolveOnly = false)
    {
        try
        {
            if (adrpOffset + 4 > _elfData.Length)
                return null;

            uint adrpInst = BinaryPrimitives.ReadUInt32LittleEndian(_elfData.AsSpan((int)adrpOffset, 4));

            // Must be ADRP
            if ((adrpInst & 0x9F000000) != 0x90000000)
                return null;

            // Decode ADRP
            int rd = (int)(adrpInst & 0x1F);
            long immhi = (adrpInst >> 5) & 0x7FFFF;
            long immlo = (adrpInst >> 29) & 0x3;
            long imm21 = (immhi << 2) | immlo;
            if ((imm21 & (1 << 20)) != 0)
                imm21 |= ~((1L << 21) - 1);
            long pc = _baseAddress + adrpOffset;
            long pcPage = pc & ~0xFFF;
            long baseAddr = pcPage + (imm21 << 12);

            // Search nearby ADD
            for (int delta = 4; delta <= searchRange; delta += 4)
            {
                long addOffset = adrpOffset + delta;
                if (addOffset + 4 > _elfData.Length)
                    break;

                uint addInst = BinaryPrimitives.ReadUInt32LittleEndian(_elfData.AsSpan((int)addOffset, 4));

                // ADD (immediate)
                if ((addInst & 0xFF000000) == 0x91000000)
                {
                    int rdAdd = (int)(addInst & 0x1F);
                    int rnAdd = (int)((addInst >> 5) & 0x1F);

                    if (rdAdd == rd && rnAdd == rd)
                    {
                        long imm12 = (addInst >> 10) & 0xFFF;
                        if ((addInst & (1 << 22)) != 0)
                            imm12 <<= 12;

                        long targetAddress = baseAddr + imm12;

                        // If resolveOnly=true, stop here and return pointer info
                        if (resolveOnly)
                        {
                            Console.WriteLine($"[DEBUG] Resolved ADRP+ADD -> 0x{targetAddress:X}");
                            return BitConverter.GetBytes(targetAddress);
                        }

                        // Otherwise, extract data
                        long fileOffset = targetAddress - _baseAddress;
                        if (fileOffset < 0)
                            return null;

                        if (fileOffset + dataLength > _elfData.Length)
                            dataLength = _elfData.Length - fileOffset;

                        if (dataLength > 0x4000)
                            dataLength = 128;

                        var data = new byte[dataLength];
                        Array.Copy(_elfData, fileOffset, data, 0, dataLength);
                        return data;
                    }
                }
            }

            return null;
        }
        catch
        {
            return null;
        }
    }

    /// <summary>
    /// Resolve the address referenced by ADRP+ADD, without reading data.
    /// </summary>
    public long? FollowADRP_ADD_Address(long adrpOffset, int searchRange = 24)
    {
        var bytes = FollowADRP_ADD(adrpOffset, 0, searchRange, resolveOnly: true);
        if (bytes == null) return null;
        return BitConverter.ToInt64(bytes, 0);
    }

    public long? FollowADRP_LDR_STR_Address(long adrpOffset, bool derefGOT = true, int searchRange = 16)
    {
        if (adrpOffset + 4 > _elfData.Length) return null;

        uint adrp = BinaryPrimitives.ReadUInt32LittleEndian(_elfData.AsSpan((int)adrpOffset, 4));
        if ((adrp & 0x9F000000) != 0x90000000) return null;

        // Decode ADRP
        long immhi = (adrp >> 5) & 0x7FFFF;
        long immlo = (adrp >> 29) & 0x3;
        long imm21 = (immhi << 2) | immlo;
        if ((imm21 & (1 << 20)) != 0) imm21 |= ~((1L << 21) - 1);
        long pc = _baseAddress + adrpOffset;
        long pageBase = (pc & ~0xFFF) + (imm21 << 12);

        // Look ahead for LDR/STR Xn,[Xn,#imm]
        for (int delta = 4; delta <= searchRange; delta += 4)
        {
            long nextOff = adrpOffset + delta;
            if (nextOff + 4 > _elfData.Length) break;
            uint inst = BinaryPrimitives.ReadUInt32LittleEndian(_elfData.AsSpan((int)nextOff, 4));
            bool isLdr = (inst & 0xFFC00000) == 0xF9400000;
            bool isStr = (inst & 0xFFC00000) == 0xF9000000;
            if (!isLdr && !isStr) continue;

            int rd = (int)(adrp & 0x1F);
            int xm = (int)((inst >> 5) & 0x1F);
            if (xm != rd) continue;

            long imm12 = ((inst >> 10) & 0xFFF) << 3; // scaled by 8 for 64-bit
            long gotAddr = pageBase + imm12;

            if (!derefGOT || isStr) return gotAddr; // STR: address is the store target

            // LDR: dereference GOT to real target
            long fileOffset = gotAddr - _baseAddress;
            if (fileOffset < 0 || fileOffset + 8 > _elfData.Length) return gotAddr;
            return BinaryPrimitives.ReadInt64LittleEndian(_elfData.AsSpan((int)fileOffset, 8));
        }
        return null;
    }

    public long? FollowADRP_ADD_Addr(long adrpOffset, long addOffset)
    {
        if (adrpOffset + 4 > _elfData.Length || addOffset + 4 > _elfData.Length)
            return null;

        uint adrp = BinaryPrimitives.ReadUInt32LittleEndian(_elfData.AsSpan((int)adrpOffset, 4));
        uint add = BinaryPrimitives.ReadUInt32LittleEndian(_elfData.AsSpan((int)addOffset, 4));

        if ((adrp & 0x9F000000) != 0x90000000) return null;
        if ((add & 0xFF000000) != 0x91000000) return null;

        // Decode ADRP
        long immhi = (adrp >> 5) & 0x7FFFF;
        long immlo = (adrp >> 29) & 0x3;
        long imm21 = (immhi << 2) | immlo;
        if ((imm21 & (1 << 20)) != 0)
            imm21 |= ~((1L << 21) - 1);
        long pc = _baseAddress + adrpOffset;
        long pageBase = (pc & ~0xFFF) + (imm21 << 12);

        // Decode ADD
        long addImm = (add >> 10) & 0xFFF;
        if ((add & (1 << 22)) != 0) addImm <<= 12;

        // Combine
        return pageBase + addImm;
    }

    public bool IsADRP(long fileOffset)
    {
        if (fileOffset < 0 || fileOffset + 4 > _elfData.Length) return false;
        uint inst = BinaryPrimitives.ReadUInt32LittleEndian(_elfData.AsSpan((int)fileOffset, 4));
        return (inst & 0x9F000000) == 0x90000000;
    }

    // Try reading a pointer-sized value at a VA (or data address interpreted as VA)
    public long? TryReadPointerVA(long va)
    {
        long fileOffset = va - _baseAddress;
        if (fileOffset < 0 || fileOffset + 8 > _elfData.Length) return null;
        return BinaryPrimitives.ReadInt64LittleEndian(_elfData.AsSpan((int)fileOffset, 8));
    }

    // Scan backwards up to N bytes (aligned to 4) to find the nearest ADRP
    public long? FindNearestADRPBefore(long startFileOffset, int maxBackBytes = 0x20)
    {
        long begin = Math.Max(0, startFileOffset - maxBackBytes);
        for (long off = startFileOffset; off >= begin; off -= 4)
        {
            if (IsADRP(off)) return off;
        }
        return null;
    }


}