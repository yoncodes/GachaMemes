#include "opcode.h"

const char *opnames2[NUM_OPCODES] = {
    "MOVE","LOADI","LOADF","LOADK","LOADKX",
    "LOADFALSE","LFALSESKIP","LOADTRUE","LOADNIL",
    "GETUPVAL","SETUPVAL","GETTABUP","GETTABLE",
    "GETI","GETFIELD","SETTABUP","SETTABLE",
    "SETI","SETFIELD","NEWTABLE","SELF",
    "ADDI","ADDK","SUBK","MULK","MODK","POWK",
    "DIVK","IDIVK","BANDK","BORK","BXORK",
    "SHRI","SHLI","ADD","SUB","MUL","MOD",
    "POW","DIV","IDIV","BAND","BOR","BXOR",
    "SHL","SHR","MMBIN","MMBINI","MMBINK",
    "UNM","BNOT","NOT","LEN","CONCAT","EXTRAARG2",
    "CLOSE","TBC","JMP","EQ","LT","LE",
    "EQK","EQI","LTI","LEI","GTI","GEI",
    "TEST","TESTSET",
    "CALL","TAILCALL",
    "RETURN","RETURN0","RETURN1",
    "FORLOOP","FORPREP",
    "TFORPREP","TFORCALL","TFORLOOP",
    "SETLIST",
    "CLOSURE",
    "VARARG","VARARGPREP",
    "EXTRAARG"
};


const Opcode opcode[NUM_OPCODES] = {
/*          MM OT  IT     T       A       mode		   opcode  */
     opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_MOVE */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iAsBx)	/* OP_LOADI */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iAsBx)	/* OP_LOADF */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABx)		/* OP_LOADK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABx)		/* OP_LOADKX */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_LOADFALSE */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_LFALSESKIP */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_LOADTRUE */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_LOADNIL */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_GETUPVAL */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_SETUPVAL */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_GETTABUP */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_GETTABLE */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_GETI */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_GETFIELD */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_SETTABUP */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_SETTABLE */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_SETI */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_SETFIELD */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_NEWTABLE */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_SELF */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_ADDI */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_ADDK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_SUBK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_MULK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_MODK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_POWK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_DIVK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_IDIVK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_BANDK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_BORK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_BXORK */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_SHRI */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_SHLI */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_ADD */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_SUB */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_MUL */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_MOD */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_POW */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_DIV */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_IDIV */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_BAND */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_BOR */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_BXOR */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_SHL */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_SHR */
    ,opmode(1, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_MMBIN */
    ,opmode(1, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_MMBINI*/
    ,opmode(1, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_MMBINK*/
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_UNM */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_BNOT */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_NOT */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_LEN */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABC)		/* OP_CONCAT */

    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iAx)		/* OP_EXTRAARG2 */

    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_CLOSE */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_TBC */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, isJ)		/* OP_JMP */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_EQ */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_LT */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_LE */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_EQK */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_EQI */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_LTI */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_LEI */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_GTI */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_GEI */
    ,opmode(0, 0, OpArgN, OpArgU, OpArgN, iABC)		/* OP_TEST */
    ,opmode(0, 0, OpArgN,OpArgU, OpArgU, iABC)		/* OP_TESTSET */
    ,opmode(0, 1, OpArgU, OpArgN, OpArgU, iABC)		/* OP_CALL */
    ,opmode(0, 1, OpArgU, OpArgN, OpArgU, iABC)		/* OP_TAILCALL */
    ,opmode(0, 0, OpArgU, OpArgN, OpArgN, iABC)		/* OP_RETURN */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_RETURN0 */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_RETURN1 */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABx)		/* OP_FORLOOP */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABx)		/* OP_FORPREP */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABx)		/* OP_TFORPREP */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iABC)		/* OP_TFORCALL */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABx)		/* OP_TFORLOOP */
    ,opmode(0, 0, OpArgU, OpArgN, OpArgN, iABC)		/* OP_SETLIST */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgU, iABx)		/* OP_CLOSURE */
    ,opmode(0, 1, OpArgN, OpArgN, OpArgU, iABC)		/* OP_VARARG */
    ,opmode(0, 0, OpArgU, OpArgN, OpArgU, iABC)		/* OP_VARARGPREP */
    ,opmode(0, 0, OpArgN, OpArgN, OpArgN, iAx)		/* OP_EXTRAARG */

};

int isKFlagOpcode(int op)
{
    switch (op)
    {
        /* Arithmetic RK ops */
        case 34: /* ADD */
        case 35: /* SUB */
        case 36: /* MUL */
        case 37: /* MOD */
        case 38: /* POW */
        case 39: /* DIV */
        case 40: /* IDIV */

        /* Bitwise RK ops */
        case 41: /* BAND */
        case 42: /* BOR */
        case 43: /* BXOR */
        case 44: /* SHL */
        case 45: /* SHR */

        /* Comparison RK ops */
        case 57: /* EQ  */
        case 58: /* LT  */
        case 59: /* LE  */

        /* Immediate comparison variants (these DO use RK(C)) */
        case 60: /* EQK */
        case 61: /* EQI */
        case 62: /* LTI */
        case 63: /* LEI */

        /* MMBIN / MMBINK (your VM uses RK) */
        case 46: /* MMBIN  */
        case 47: /* MMBINI */
        case 48: /* MMBINK */
            return 1;

        default:
            return 0;
    }
}
