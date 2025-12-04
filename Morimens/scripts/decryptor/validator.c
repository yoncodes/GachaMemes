#include "validator.h"
#include "opcode.h"
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#define MAX_VALID_OPCODE 83

ReachabilityInfo mark_reachable(uint32_t *code, uint32_t count, uint8_t *reachable)
{
    ReachabilityInfo info = {0, count, 0};

    if (count == 0) {
        return info;
    }

    memset(reachable, 0, count);

    uint32_t *queue = (uint32_t *)malloc(count * sizeof(uint32_t));
    if (!queue) {
        // On OOM, behave as "everything reachable, do nothing".
        memset(reachable, 1, count);
        info.reachable_count = count;
        info.trimmed_count   = count;
        info.has_holes       = 0;
        return info;
    }

    int queue_start = 0, queue_end = 0;

    // Entry point is always instruction 0
    reachable[0] = 1;
    queue[queue_end++] = 0;

    while (queue_start < queue_end) {
        uint32_t pc = queue[queue_start++];
        if (pc >= count) continue;

        uint32_t instr = code[pc];
        uint8_t  op    = GET_OPCODE(instr);
        int is_terminal = 0;

        switch (op) {

            case 6: /* LFALSESKIP */
                // True: fallthrough
                if (pc + 1 < count && !reachable[pc + 1]) {
                    reachable[pc + 1] = 1;
                    queue[queue_end++] = pc + 1;
                }
                // False: skip the next instruction
                if (pc + 2 < count && !reachable[pc + 2]) {
                    reachable[pc + 2] = 1;
                    queue[queue_end++] = pc + 2;
                }
                continue;

            case 46: /* MMBIN */
            case 47: /* MMBINI */
            case 48: /* MMBINK */
            case 79: { // SETLIST
                    // Always fallthrough to the next instruction
                    if (pc + 1 < count && !reachable[pc + 1]) {
                        reachable[pc + 1] = 1;
                        queue[queue_end++] = pc + 1;
                    }

                    // If next is EXTRAARG (82), then ALSO fallthrough further.
                    if (pc + 2 < count) {
                        uint32_t next = GET_OPCODE(code[pc + 1]);
                        if (next == 82) {  // Only 82, not 83
                            if (!reachable[pc + 2]) {
                                reachable[pc + 2] = 1;
                                queue[queue_end++] = pc + 2;
                            }
                        }
                    }
                    continue;
                }
            case 20: /* SELF */
                // They ALL fall through normally
                if (pc + 1 < count && !reachable[pc + 1]) {
                    reachable[pc + 1] = 1;
                     queue[queue_end++] = pc + 1;
                }
                // if next is EXTRAARG, include that
                if (pc + 2 < count && (GET_OPCODE(code[pc+1]) == 82)) {
                    if (!reachable[pc + 2]) {
                        reachable[pc + 2] = 1;
                        queue[queue_end++] = pc + 2;
                    }
                }
                continue;

        /* --------------------------------------------------------
         *  Returns (terminal)
         * ----------------------------------------------------- */
        case 71: // RETURN
        case 72: // RETURN0
        case 73: // RETURN1
            is_terminal = 1;
            break;

        /* --------------------------------------------------------
         *  JMP (unconditional)
         *  sJ is signed 25-bit: sJ = (instr >> 7)
         *  pc' = pc + sJ + 1
         * ----------------------------------------------------- */
        case 57: { // JMP
            int sJ = GETARG_sJ(instr);  // Use proper macro for sJ

            int target = (int)pc + 1 + sJ;

            if (target >= 0 && target < (int)count && !reachable[target]) {
                reachable[target] = 1;
                queue[queue_end++] = (uint32_t)target;
            }
            is_terminal = 1;
            break;
        }

        /* --------------------------------------------------------
         *  Conditional branches with skip-next behavior:
         *    EQ, LT, LE, EQK, EQI, LTI, LEI, GTI, GEI, TEST, TESTSET
         *  They can go to:
         *    - pc + 1 (no jump)
         *    - pc + 2 (skip next)
         * ----------------------------------------------------- */
        case 58: // EQ
        case 59: // LT
        case 60: // LE
        case 61: // EQK
        case 62: // EQI
        case 63: // LTI
        case 64: // LEI
        case 65: // GTI
        case 66: // GEI
        case 67: // TEST
        case 68: // TESTSET
            if (pc + 1 < count && !reachable[pc + 1]) {
                reachable[pc + 1] = 1;
                queue[queue_end++] = pc + 1;
            }
            if (pc + 2 < count && !reachable[pc + 2]) {
                reachable[pc + 2] = 1;
                queue[queue_end++] = pc + 2;
            }
            // We handled both successors explicitly.
            continue;

        /* --------------------------------------------------------
         *  Loops
         *
         *  FORLOOP  (74):  pc' = pc - Bx      (loop body), or fallthrough on exit
         *  FORPREP  (75):  pc' = pc + Bx + 1  (forward jump)
         *  TFORPREP (76):  pc' = pc + Bx + 1  (forward jump)
         *  TFORLOOP (78):  pc' = pc - Bx      (loop body), or fallthrough on exit
         * ----------------------------------------------------- */
        case 74: // FORLOOP
        case 78: // TFORLOOP
        {
            int Bx  = GETARG_Bx(instr);
            int sBx = GETARG_sBx(instr);

            // Standard form: target = pc + 1 + sBx
            int target = pc + 1 + sBx;

            // mark jump target
            if (target >= 0 && target < (int)count && !reachable[target]) {
                reachable[target] = 1;
                queue[queue_end++] = target;
            }

            // FORLOOP has fallthrough path (loop exit)
            if (pc + 1 < count && !reachable[pc + 1]) {
                reachable[pc + 1] = 1;
                queue[queue_end++] = pc + 1;
            }

            continue;   // handled both paths
        }

        case 75: // FORPREP
        case 76: // TFORPREP
        {
            int Bx  = GETARG_Bx18(instr);
            int sBx = GETARG_sBx18(instr);

            int target = pc + 1 + sBx;

            if (target >= 0 && target < (int)count && !reachable[target]) {
                reachable[target] = 1;
                queue[queue_end++] = target;
            }

            is_terminal = 1;   // no fallthrough
            break;
        }

        /* --------------------------------------------------------
         *  OP_CLOSE (54) - Signature marker, treat as NOP/fallthrough
         * ----------------------------------------------------- */
        case 54: // CLOSE (signature marker)
            // Treat as fallthrough - it's not executed but we need to continue
            if (pc + 1 < count && !reachable[pc + 1]) {
                reachable[pc + 1] = 1;
                queue[queue_end++] = pc + 1;
            }
            continue;

        default:
            // other opcodes just fall through
            break;
        }

        // Generic fallthrough if not terminal
        if (!is_terminal && pc + 1 < count && !reachable[pc + 1]) {
            reachable[pc + 1] = 1;
            queue[queue_end++] = pc + 1;
        }
    }

    free(queue);

    // Compute stats
    int32_t last_reachable = -1;
    for (uint32_t i = 0; i < count; ++i) {
        if (reachable[i]) {
            info.reachable_count++;
            last_reachable = (int32_t)i;
        }
    }

    if (last_reachable < 0) {
        // Degenerate: nothing reachable? treat as "no trimming".
        info.trimmed_count = count;
        info.has_holes     = 0;
        return info;
    }

    // Check for holes before last_reachable
    for (uint32_t i = 0; i < (uint32_t)last_reachable; ++i) {
        if (!reachable[i]) {
            info.has_holes = 1;
            break;
        }
    }

    if (!info.has_holes) {
        // Safe: reachable[0..last_reachable] all 1, tail 0s only
        info.trimmed_count = (uint32_t)last_reachable + 1;
    } else {
        // Unsafe: internal unreachable regions → do not trim
        info.trimmed_count = count;
    }

    return info;
}

int validate_instruction(int op, int A, int B, int C, int Bx, int k,
                        int num_consts, int num_protos, int count) {
    // Invalid opcode
    if (op > MAX_VALID_OPCODE)
        return VALID_INVALID;


    const Opcode *fmt = &opcode[op];

    // Basic range checks
    if (A > 255) return VALID_INVALID;
    if (B > 255) return VALID_INVALID;
    if (C > 255) return VALID_INVALID;

    // Check Bx based on opMode
    switch (fmt->opMode) {
        case iABC:
            if (Bx != 0) return VALID_INVALID;
            break;
        case iABx:
        case iAsBx:
            if (Bx > 262143) return VALID_INVALID;
            break;
        case isJ:
            if (Bx > 33554431 || Bx < -16777216) return VALID_INVALID;
            break;
        case iAx:
            if (Bx > 134217727) return VALID_INVALID;
            break;
    }

    // Loop instructions - check Bx is valid jump target
    if (op == 74 || op == 75 || op == 76 || op == 78) {
        if (Bx >= count) {
            return VALID_NEEDS_FIX;
        }
    }

    // Check proto indices for CLOSURE
    if (op == 80) {
        if (num_protos > 0 && Bx >= num_protos) {
            return VALID_INVALID;
        }
    }

    // Check constant indices for EXTRAARG
    if (op == 83) {
        int Ax = Bx;  // For iAx, Bx is already the full Ax value
        if (num_consts > 0 && Ax >= num_consts) {
            return VALID_NEEDS_FIX;
        }
    }

    // Check constant indices for instructions that use constants in Bx
    if (op == 3 || (op >= 22 && op <= 31)) {
        if (num_consts > 0 && Bx >= num_consts) {
            return VALID_NEEDS_FIX;
        }
    }

    // Check constant indices for instructions that use constants in C
    if ((op == 11 || op == 14 || op == 15 || op == 18 || op == 20) && k) {
        if (num_consts > 0 && C >= num_consts) {
            return VALID_NEEDS_FIX;
        }
    }

    return VALID_OK;
}
