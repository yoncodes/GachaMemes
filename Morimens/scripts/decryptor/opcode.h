#pragma once

#include <stdint.h>
#include <stddef.h>
#include "..\xlua\llimits.h"

// Opcode names for debugging (standard Lua 5.4 + Morimens extension)
typedef enum {iABC, iABx, iAsBx, iAx, isJ} OpMode;
typedef enum {OpArgN, OpArgU, OpArgR, OpArgK} OpType;

typedef uint8_t byte;

typedef enum {
/*----------------------------------------------------------------------
  name		args	description
------------------------------------------------------------------------*/
OP_MOVE,/*	A B	R[A] := R[B]					*/
OP_LOADI,/*	A sBx	R[A] := sBx					*/
OP_LOADF,/*	A sBx	R[A] := (lua_Number)sBx				*/
OP_LOADK,/*	A Bx	R[A] := K[Bx]					*/
OP_LOADKX,/*	A	R[A] := K[extra arg]				*/
OP_LOADFALSE,/*	A	R[A] := false					*/
OP_LFALSESKIP,/*A	R[A] := false; pc++				*/
OP_LOADTRUE,/*	A	R[A] := true					*/
OP_LOADNIL,/*	A B	R[A], R[A+1], ..., R[A+B] := nil		*/
OP_GETUPVAL,/*	A B	R[A] := UpValue[B]				*/
OP_SETUPVAL,/*	A B	UpValue[B] := R[A]				*/

OP_GETTABUP,/*	A B C	R[A] := UpValue[B][K[C]:string]			*/
OP_GETTABLE,/*	A B C	R[A] := R[B][R[C]]				*/
OP_GETI,/*	A B C	R[A] := R[B][C]					*/
OP_GETFIELD,/*	A B C	R[A] := R[B][K[C]:string]			*/

OP_SETTABUP,/*	A B C	UpValue[A][K[B]:string] := RK(C)		*/
OP_SETTABLE,/*	A B C	R[A][R[B]] := RK(C)				*/
OP_SETI,/*	A B C	R[A][B] := RK(C)				*/
OP_SETFIELD,/*	A B C	R[A][K[B]:string] := RK(C)			*/

OP_NEWTABLE,/*	A B C k	R[A] := {}					*/

OP_SELF,/*	A B C	R[A+1] := R[B]; R[A] := R[B][RK(C):string]	*/

OP_ADDI,/*	A B sC	R[A] := R[B] + sC				*/

OP_ADDK,/*	A B C	R[A] := R[B] + K[C]				*/
OP_SUBK,/*	A B C	R[A] := R[B] - K[C]				*/
OP_MULK,/*	A B C	R[A] := R[B] * K[C]				*/
OP_MODK,/*	A B C	R[A] := R[B] % K[C]				*/
OP_POWK,/*	A B C	R[A] := R[B] ^ K[C]				*/
OP_DIVK,/*	A B C	R[A] := R[B] / K[C]				*/
OP_IDIVK,/*	A B C	R[A] := R[B] // K[C]				*/

OP_BANDK,/*	A B C	R[A] := R[B] & K[C]:integer			*/
OP_BORK,/*	A B C	R[A] := R[B] | K[C]:integer			*/
OP_BXORK,/*	A B C	R[A] := R[B] ~ K[C]:integer			*/

OP_SHRI,/*	A B sC	R[A] := R[B] >> sC				*/
OP_SHLI,/*	A B sC	R[A] := sC << R[B]				*/

OP_ADD,/*	A B C	R[A] := R[B] + R[C]				*/
OP_SUB,/*	A B C	R[A] := R[B] - R[C]				*/
OP_MUL,/*	A B C	R[A] := R[B] * R[C]				*/
OP_MOD,/*	A B C	R[A] := R[B] % R[C]				*/
OP_POW,/*	A B C	R[A] := R[B] ^ R[C]				*/
OP_DIV,/*	A B C	R[A] := R[B] / R[C]				*/
OP_IDIV,/*	A B C	R[A] := R[B] // R[C]				*/

OP_BAND,/*	A B C	R[A] := R[B] & R[C]				*/
OP_BOR,/*	A B C	R[A] := R[B] | R[C]				*/
OP_BXOR,/*	A B C	R[A] := R[B] ~ R[C]				*/
OP_SHL,/*	A B C	R[A] := R[B] << R[C]				*/
OP_SHR,/*	A B C	R[A] := R[B] >> R[C]				*/

OP_MMBIN,/*	A B C	call C metamethod over R[A] and R[B]		*/
OP_MMBINI,/*	A sB C k	call C metamethod over R[A] and sB	*/
OP_MMBINK,/*	A B C k		call C metamethod over R[A] and K[B]	*/

OP_UNM,/*	A B	R[A] := -R[B]					*/
OP_BNOT,/*	A B	R[A] := ~R[B]					*/
OP_NOT,/*	A B	R[A] := not R[B]				*/
OP_LEN,/*	A B	R[A] := length of R[B]				*/

OP_CONCAT,/*	A B	R[A] := R[A].. ... ..R[A + B - 1]		*/

OP_GAME_CUSTOM,/*	We dont know what this does yet				*/

OP_CLOSE,/*	A	close all upvalues >= R[A]			*/
OP_TBC,/*	A	mark variable A "to be closed"			*/
OP_JMP,/*	sJ	pc += sJ					*/
OP_EQ,/*	A B k	if ((R[A] == R[B]) ~= k) then pc++		*/
OP_LT,/*	A B k	if ((R[A] <  R[B]) ~= k) then pc++		*/
OP_LE,/*	A B k	if ((R[A] <= R[B]) ~= k) then pc++		*/

OP_EQK,/*	A B k	if ((R[A] == K[B]) ~= k) then pc++		*/
OP_EQI,/*	A sB k	if ((R[A] == sB) ~= k) then pc++		*/
OP_LTI,/*	A sB k	if ((R[A] < sB) ~= k) then pc++			*/
OP_LEI,/*	A sB k	if ((R[A] <= sB) ~= k) then pc++		*/
OP_GTI,/*	A sB k	if ((R[A] > sB) ~= k) then pc++			*/
OP_GEI,/*	A sB k	if ((R[A] >= sB) ~= k) then pc++		*/

OP_TEST,/*	A k	if (not R[A] == k) then pc++			*/
OP_TESTSET,/*	A B k	if (not R[B] == k) then pc++ else R[A] := R[B]	*/

OP_CALL,/*	A B C	R[A], ... ,R[A+C-2] := R[A](R[A+1], ... ,R[A+B-1]) */
OP_TAILCALL,/*	A B C k	return R[A](R[A+1], ... ,R[A+B-1])		*/

OP_RETURN,/*	A B C k	return R[A], ... ,R[A+B-2]	(see note)	*/
OP_RETURN0,/*		return						*/
OP_RETURN1,/*	A	return R[A]					*/

OP_FORLOOP,/*	A Bx	update counters; if loop continues then pc-=Bx; */
OP_FORPREP,/*	A Bx	<check values and prepare counters>;
                        if not to run then pc+=Bx+1;			*/

OP_TFORPREP,/*	A Bx	create upvalue for R[A + 3]; pc+=Bx		*/
OP_TFORCALL,/*	A C	R[A+4], ... ,R[A+3+C] := R[A](R[A+1], R[A+2]);	*/
OP_TFORLOOP,/*	A Bx	if R[A+2] ~= nil then { R[A]=R[A+2]; pc -= Bx }	*/

OP_SETLIST,/*	A B C k	R[A][(C-1)*FPF+i] := R[A+i], 1 <= i <= B	*/

OP_CLOSURE,/*	A Bx	R[A] := closure(KPROTO[Bx])			*/

OP_VARARG,/*	A C	R[A], R[A+1], ..., R[A+C-2] = vararg		*/

OP_VARARGPREP,/*A	(adjust vararg parameters)			*/

OP_EXTRAARG,/*	Ax	extra (larger) argument for previous opcode	*/

} OpCodes;

#define NUM_OPCODES	((int)(OP_EXTRAARG) + 1)

#define SIZE_OP		7

#define POS_OP		0

typedef l_uint32 Instruction;

#define opmode(mm,ot,it,t,a,m)  \
    (((mm) << 7) | ((ot) << 6) | ((it) << 5) | ((t) << 4) | ((a) << 3) | (m))

/* creates a mask with 'n' 1 bits at position 'p' */
#define MASK1(n,p)	((~((~(Instruction)0)<<(n)))<<(p))

/* creates a mask with 'n' 0 bits at position 'p' */
#define MASK0(n,p)	(~MASK1(n,p))

// Operand usage flags
typedef struct {
    unsigned uses_A : 1;
    unsigned uses_B : 1;
    unsigned uses_C : 1;
    unsigned uses_Bx : 1;
    unsigned B_can_be_const : 1;
    unsigned C_can_be_const : 1;
    unsigned has_k_flag : 1;
} OpcodeFormat;

#define GET_OPCODE(i)   ((uint8_t)((i) & 0x7F))

#define GETARG_A(i)     (((i) >> 7)  & 0xFF)
#define GETARG_k(i)     (((i) >> 15) & 0x1)
#define GETARG_B(i)     (((i) >> 16) & 0xFF)
#define GETARG_C(i)     (((i) >> 24) & 0xFF)

#define GETARG_Bx(i)     (((i) >> 15) & 0x1FFFFu)
#define GETARG_sBx(i)    ((int)GETARG_Bx(i) - 131071)
#define GETARG_sJ(i)     ((int32_t)(i) >> 7)

#define GETARG_sC(i)  ((int)(((i) >> 24) & 0xFF) - 127)
#define GETARG_sB(i)     ((int8_t)(((i) >> 16) & 0xFF)) // -128..127

#define BX_MAX   0x1FFFFu   // 131071
#define BX_HALF  (BX_MAX >> 1)   // 65535

#define PATCH_Bx(i, newBx) \
    ((i & ~0xFFFF8000u) | ((uint32_t)(newBx) << 15))

#define PATCH_sBx(i, newsBx)  PATCH_Bx(i, (newsBx) + BX_HALF)

#define PATCH_A(i, newA) \
    ((i & ~0x00007F80u) | ((newA & 0xFF) << 7))

#define PATCH_C(i, newC) \
    ((i & 0x00FFFFFFu) | ((uint32_t)(newC) << 24))

/* === 18-bit FORPREP / TFORPREP fields === */

#define MAXARG_Bx18   ((1u << 18) - 1u)     // 262143
#define BX_HALF18     (MAXARG_Bx18 >> 1)    // 131071

#define GETARG_Bx18(i)   (((i) >> 15) & MAXARG_Bx18)
#define GETARG_sBx18(i)  ((int)GETARG_Bx18(i) - (int)BX_HALF18)

#define PATCH_Bx18(i, newBx) \
    (((i) & ~(MAXARG_Bx18 << 15)) | (((uint32_t)(newBx) & MAXARG_Bx18) << 15))

#define PATCH_sBx18(i, newsBx) \
    PATCH_Bx18(i, (uint32_t)((int)(newsBx) + (int)BX_HALF18))

extern const char *opnames2[NUM_OPCODES];

    typedef struct {
        byte testFlag;      // operator is a test (next instruction must be a jump)
        byte setAFlag;      // instruction set register A
        byte argBMode;      // B arg mode
        byte argCMode;      // C arg mode
        byte opMode;
    }Opcode;

extern const Opcode opcode[NUM_OPCODES];
int isKFlagOpcode(int op);
