#include "bytecode.h"
#include "opcode.h"
#include "validator.h"
#include "varint.h"
#include "crypto.h"
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

// Global file-level seed16 (0xFFFF = not discovered yet)
static uint16_t g_file_seed16 = 0xFFFF;

static inline uint8_t decode_opcode(uint32_t instr) {
    uint8_t op = instr & 0x7F;

    // If opcode is out of range, undo the 0x40 flip
    if (op >= NUM_OPCODES) {
        op ^= 0x40;
    }

    return op;
}

#undef GET_OPCODE
#define GET_OPCODE(i) decode_opcode((i))

FILE *g_log_file = NULL;

void open_log_file(const char *path) {
    g_log_file = fopen(path, "a");
    setvbuf(g_log_file, NULL, _IOFBF, 1024 * 1024);
}

void close_log_file(void) {
    if (g_log_file) fclose(g_log_file);
    g_log_file = NULL;
}

void print_instruction(uint32_t pc, uint32_t instr, int fixed);

#define ENABLE_TRIMMING 0

DecryptResult decrypt_bytecode(
    uint8_t *data,
    size_t   offset,
    uint32_t count,
    uint32_t linedefined,       
    int      num_protos,
    int      num_consts,
    int      depth,
    size_t   sizecode_offset,
    size_t   file_size
) {
    uint32_t *code = (uint32_t *)&data[offset];
    uint32_t removed_instructions = 0;

    //printf("%*sDecrypting %u instructions...\n", depth*2, "", count);

    // =====================================================================
    // PHASE 0: XLua RC4 Decryption
    // =====================================================================
    if (count > 0) {
        int success = 0;

        // If we already discovered file_seed16, use it
        if (g_file_seed16 != 0xFFFF) {
            //printf("%*s[*] Using file seed16=0x%04X, linedefined=%u\n", depth*2, "", g_file_seed16, linedefined);

            success = decrypt_xlua_bytecode(
                data, offset, count, linedefined, g_file_seed16
            );

            if (success) {
                //printf("%*s[+] ✓ Decryption successful\n", depth*2, "");
            } else {
                printf("%*s[!] ✗ Decryption failed\n", depth*2, "");
            }
        } else {
            // First function - brute force to discover seed16
            //printf("%*s[*] Brute-forcing seed16 (linedefined=%u)...\n", depth*2, "", linedefined);

            uint16_t discovered_seed16;
            success = bruteforce_xlua_seed16(
                data, offset, count, linedefined, &discovered_seed16
            );

            if (success) {
                g_file_seed16 = discovered_seed16;
                //printf("%*s[+] Found seed16=0x%04X (will be used for all nested functions)\n", depth*2, "", g_file_seed16);
            } else {
                printf("%*s[!] Brute-force failed\n", depth*2, "");
            }
        }

        if (!success) {
            // Decryption failed - return as-is
            DecryptResult r;
            r.final_count = count;
            r.removed_instr = 0;
            r.removed_bytes = 0;
            return r;
        }
    }

    // =====================================================================
    // PHASE 1: Decode / Minimal Fix (after XLua decryption)
    // =====================================================================
    for (uint32_t i = 0; i < count; i++) {
        uint32_t dec = code[i];
        uint8_t op = GET_OPCODE(dec);
        int Bx = GETARG_Bx(dec);

        int fixed = 0;

        // Fix LOADK (opcode 3)
        if (op == 3 && num_consts > 0) {
            uint32_t newBx = Bx % num_consts;
            if (newBx != Bx) {
                dec = PATCH_Bx(dec, newBx);
                fixed = 1;
            }
        }

        // Fix JMP (opcode 57)
        if (op == 57) {
            int sBx = GETARG_sBx(dec);
            int target = (int)i + 1 + sBx;
            if (target < 0 || target >= (int)count) {
                while (target < 0) target += count;
                while (target >= count) target -= count;
                int new_sBx = target - ((int)i + 1);
                int new_Bx = new_sBx + BX_HALF;
                dec = PATCH_Bx(dec, new_Bx);
                fixed = 1;
            }
        }

        code[i] = dec;
        //print_instruction(i, dec, fixed);
    }

    // =====================================================================
    // PHASE 2: Reachability Analysis
    // =====================================================================
    uint8_t *reachable = malloc(count);
    ReachabilityInfo ri = mark_reachable(code, count, reachable);

    //printf("%*sReachable: %u/%u\n", depth*2, "", ri.reachable_count, count);

#if ENABLE_TRIMMING
    if (!ri.has_holes && ri.trimmed_count < count) {
        uint32_t old_count = count;
        count = ri.trimmed_count;
        removed_instructions = old_count - count;

        printf("%*sTrimming trailing unreachable: %u -> %u\n",
               depth * 2, "", old_count, count);

        size_t old_end = offset + (size_t)old_count * 4;
        size_t new_end = offset + (size_t)count * 4;
        size_t tail = file_size - old_end;

        memmove(&data[new_end], &data[old_end], tail);

        size_t tmp = sizecode_offset;
        if (!write_7bit_int(data, file_size, &tmp, count)) {
            printf("%*sERROR: failed to update sizecode\n", depth * 2, "");
        }
    }
#endif

    free(reachable);

    // =====================================================================
    // PHASE 3: Validation
    // =====================================================================
    uint32_t valid = 0;
    for (uint32_t i = 0; i < count; i++) {
        uint8_t op = GET_OPCODE(code[i]);
        if (op <= 83) valid++;
    }

    //printf("%*sValid opcodes: %u/%u\n", depth*2, "", valid, count);

    DecryptResult r;
    r.final_count = count;
    r.removed_instr = 0;
    r.removed_bytes = 0;
    return r;
}

void print_instruction(uint32_t pc, uint32_t instr, int fixed)
{
    uint8_t  op  = GET_OPCODE(instr);
    uint8_t  a   = GETARG_A(instr);
    uint8_t  b   = GETARG_B(instr);
    uint8_t  c   = GETARG_C(instr);
    uint8_t  k   = GETARG_k(instr);
    uint32_t bx  = GETARG_Bx(instr);
    int32_t  sbx = GETARG_sBx(instr);
    int32_t  sj  = GETARG_sJ(instr);
    uint32_t ax  = instr >> 7;

    printf(" %04u: %08X  ", pc, instr);

    switch (op) {
        case 0:   printf("Move         A=%-3u B=%-3u", a, b); break;
        case 1:   printf("LoadI        A=%-3u sBx=%-8d", a, sbx); break;
        case 2:   printf("LoadF        A=%-3u sBx=%-8.0f", a, (double)sbx); break;
        case 3:   printf("LoadK        A=%-3u Bx=%-6u", a, bx); break;
        case 4:   printf("LoadKx       A=%-3u", a); break;
        case 5:   printf("LoadFalse    A=%-3u", a); break;
        case 6:   printf("LFalseSkip   A=%-3u", a); break;
        case 7:   printf("LoadTrue     A=%-3u", a); break;
        case 8:   printf("LoadNil      A=%-3u B=%-3u", a, b); break;
        case 9:   printf("GetUpval     A=%-3u B=%-3u", a, b); break;
        case 10:  printf("SetUpval     A=%-3u B=%-3u", a, b); break;
        case 11:  printf("GetTabup     A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 12:  printf("GetTable     A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 13:  printf("GetI         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 14:  printf("GetField     A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 15:  printf("SetTabup     A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 16:  printf("SetTable     A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 17:  printf("SetI         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 18:  printf("SetField     A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 19:  printf("NewTable     A=%-3u B=%-3u C=%-3u k=%u", a, b, c, k); break;
        case 20:  printf("Self_        A=%-3u B=%-3u C=%-3u", a, b, c); break;

        case 21:  printf("AddI         A=%-3u B=%-3u sC=%-4d", a, b, GETARG_sC(instr)); break;
        case 22:  printf("AddK         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 23:  printf("SubK         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 24:  printf("MulK         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 25:  printf("ModK         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 26:  printf("PowK         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 27:  printf("DivK         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 28:  printf("IDivK        A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 29:  printf("BAndK        A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 30:  printf("BOrK         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 31:  printf("BXorK        A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 32:  printf("ShrI         A=%-3u B=%-3u sC=%-4d", a, b, GETARG_sC(instr)); break;
        case 33:  printf("ShlI         A=%-3u B=%-3u sC=%-4d", a, b, GETARG_sC(instr)); break;

        case 34:  printf("Add          A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 35:  printf("Sub          A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 36:  printf("Mul          A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 37:  printf("Mod          A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 38:  printf("Pow          A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 39:  printf("Div          A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 40:  printf("IDiv         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 41:  printf("BAnd         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 42:  printf("BOr          A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 43:  printf("BXor         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 44:  printf("Shl          A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 45:  printf("Shr          A=%-3u B=%-3u C=%-3u", a, b, c); break;

        case 46:  printf("MmBin        A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 47:  printf("MmBinI       A=%-3u sB=%-4d C=%-3u k=%u", a, (int8_t)b, c, k); break;
        case 48:  printf("MmBinK       A=%-3u B=%-3u C=%-3u k=%u", a, b, c, k); break;

        case 49:  printf("Unm          A=%-3u B=%-3u", a, b); break;
        case 50:  printf("BNot         A=%-3u B=%-3u", a, b); break;
        case 51:  printf("Not          A=%-3u B=%-3u", a, b); break;
        case 52:  printf("Len          A=%-3u B=%-3u", a, b); break;
        case 53:  printf("Concat       A=%-3u B=%-3u", a, b); break;

        case 54:  printf("GAME_CUSTOM  A=%-3u B=%-3u C=%-3u", a, b, c); break;

        case 55:  printf("Close        A=%-3u", a); break;
        case 56:  printf("Tbc          A=%-3u", a); break;
        case 57:  printf("Jmp          sJ=%-8d", sj); break;

        case 58:  printf("Eq           A=%-3u B=%-3u k=%u", a, b, k); break;
        case 59:  printf("Lt           A=%-3u B=%-3u k=%u", a, b, k); break;
        case 60:  printf("Le           A=%-3u B=%-3u k=%u", a, b, k); break;
        case 61:  printf("EqK          A=%-3u B=%-3u k=%u", a, b, k); break;
        case 62:  printf("EqI          A=%-3u sB=%-4d k=%u", a, GETARG_sB(instr), k); break;
        case 63:  printf("LtI          A=%-3u sB=%-4d k=%u", a, GETARG_sB(instr), k); break;
        case 64:  printf("LeI          A=%-3u sB=%-4d k=%u", a, GETARG_sB(instr), k); break;
        case 65:  printf("GtI          A=%-3u sB=%-4d k=%u", a, GETARG_sB(instr), k); break;
        case 66:  printf("GeI          A=%-3u sB=%-4d k=%u", a, GETARG_sB(instr), k); break;

        case 67:  printf("Test         A=%-3u k=%u", a, k); break;
        case 68:  printf("TestSet      A=%-3u B=%-3u k=%u", a, b, k); break;
        case 69:  printf("Call         A=%-3u B=%-3u C=%-3u", a, b, c); break;
        case 70:  printf("TailCall     A=%-3u B=%-3u C=%-3u k=%u", a, b, c, k); break;
        case 71:  printf("Return       A=%-3u B=%-3u C=%-3u k=%u", a, b, c, k); break;
        case 72:  printf("Return0"); break;
        case 73:  printf("Return1      A=%-3u", a); break;

        case 74:  printf("ForLoop      A=%-3u Bx=%-6u", a, bx); break;
        case 75:  printf("ForPrep      A=%-3u Bx=%-6u", a, bx); break;
        case 76:  printf("TForPrep     A=%-3u Bx=%-6u", a, bx); break;
        case 77:  printf("TForCall     A=%-3u C=%-3u", a, c); break;
        case 78:  printf("TForLoop     A=%-3u Bx=%-6u", a, bx); break;

        case 79:  printf("SetList      A=%-3u B=%-3u C=%-3u k=%u", a, b, c, k); break;
        case 80:  printf("Closure      A=%-3u Bx=%-6u", a, bx); break;
        case 81:  printf("Vararg       A=%-3u C=%-3u", a, c); break;
        case 82:  printf("VarargPrep   A=%-3u", a); break;
        case 83:  printf("Extraarg     Ax=%-10u", ax); break;

        default:
            printf("???          op=%-3u raw=0x%08X", op, instr); break;
    }

    if (fixed) printf("  [FIXED]");
    printf("\n");
}
