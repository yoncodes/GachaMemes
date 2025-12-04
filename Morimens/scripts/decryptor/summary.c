#include <stdio.h>
#include "summary.h"

int analyze_instructions(const uint32_t *code, uint32_t count, int depth)
{
    int max_register = 0;
    uint32_t closure_count = 0;

    for (uint32_t i = 0; i < count; i++) {
        uint32_t instr = code[i];           // ← already decrypted!
        uint8_t op = instr & 0x7F;

        if (op > 83) continue;

        if (op == 80) closure_count++;      // OP_CLOSURE

        int A = (instr >> 7)  & 0xFF;
        int B = (instr >> 16) & 0xFF;
        int C = (instr >> 24) & 0xFF;

        if (A > max_register && A < 250) max_register = A;

        // Same opcode filter list as before — excellent!
        int uses_BC_as_regs = 1;
        if (op == 3 || op == 4 ||                     // LOADK, LOADKX
            op == 13 || op == 17 || op == 21 ||       // GETI, SETI, ADDI
            op == 24 || op == 25 ||                   // GETTABUP, SETTABUP
            (op >= 22 && op <= 31) ||                 // ADDK..BXORK
            op == 32 || op == 33 ||                   // SHRI, SHLI
            op == 57 ||                               // JMP
            (op >= 60 && op <= 65) ||                 // EQK..GEI
            (op >= 73 && op <= 77) ||                 // FORPREP etc.
            op == 80 ||                               // CLOSURE
            op == 83) {                   // EXTRAARG
            uses_BC_as_regs = 0;
        }

        if (uses_BC_as_regs) {
            if (B > max_register && B < 250) max_register = B;
            if (C > max_register && C < 250) max_register = C;
        }
    }

    //printf("%*sAnalysis: closures=%u, max_register=%d\n", depth*2, "", closure_count, max_register);
    return max_register;
}
