#pragma once

#include <stdint.h>
#include <stddef.h>

typedef uint8_t byte;

#define LUA_SIGNATURE_STR   "\x1bLua"
#define LUAC_VERSION        0x54
#define FLAG1               0x30
#define FLAG2               0x00
#define LUAC_FORMAT         1
#define LUAC_DATA_STR       "\x19\x93\r\n\x1a\n"
#define INSTRUCTION_SIZE    4
#define LUA_INTEGER_SIZE    8
#define LUA_NUMBER_SIZE     8
#define LUAC_INT            0x5678
#define LUAC_NUM            370.5


// Corrected tag definitions to match Python
#define TAG_NIL            0x00  // 0 decimal - Nil
#define TAG_BOOLEAN_FALSE  0x01  // 1 decimal - Boolean false
#define TAG_BOOLEAN_TRUE   0x11  // 17 decimal - Boolean true
#define TAG_NUMBER         0x03  // 3 decimal - 8-byte INTEGER (signed)
#define TAG_SHORT_STR      0x04  // 4 decimal - Short string
#define TAG_INTEGER        0x13  // 19 decimal - 8-byte FLOAT (double)
#define TAG_LONG_STR       0x14  // 20 decimal - Long string


#pragma pack(push, 1)
typedef struct LuaChunkHeader
{
    byte    signature[4];   // signature, magic number:0x1B4C7561
    byte    version;        // version, major_ver * 16 + minor_ver
    byte    flag1;          // custom flag morimen uses no idea what yet
    byte    flag2;          // encryption flag for rsa?
    byte    format;         // format, 0 is official // game has this set to 1
    byte    luacData[6];    // LUAC_DATA, former 2 bytes are 0x1993(lua release year), then 0x0D, 0x0A, 0x1A, 0x0A
    byte    instructionSize; // lua instruction size, usually 4 bytes
    byte    luaIntegerSize;  // lua integer size, usually 8 bytes
    byte    luaNumberSize;   // lua double number size, usually 8 bytes
    int64_t luacInt;         // LUAC_INT, 0x5678(size depends on lua Integer size) to set big-end or small-end
    double  luacNum;         // LUAC_NUM, 370.5(size depends on lua double size) to check float format, usually IEEE 754

    byte    rsaBlock[128];
} LuaChunkHeader;
#pragma pack(pop)


typedef enum {
    CONST_NIL,
    CONST_BOOLEAN,
    CONST_NUMBER,
    CONST_INTEGER,
    CONST_STR
} ConstantType;

typedef struct {
    ConstantType type;
    void        *buf;
    int          buf_size;
} Constant;

typedef struct {
    char    *varName;
    uint32_t startPc;
    uint32_t endPc;
} LocalVar;

typedef struct {
    uint32_t pc;
    uint32_t line;
} AbsLineInfo;

typedef struct {
    byte instack;
    byte idx;
    byte kind;
} UpValue;

typedef struct Prototype {
    char           *source;
    uint32_t        lineDefined;
    uint32_t        lastLineDefined;
    byte            numParams;
    byte            isVararg;
    byte            maxStackSize;

    uint32_t       *code;
    uint32_t        code_count;

    Constant       *constants;
    uint32_t        const_count;

    UpValue        *upvalues;
    uint32_t        upvalue_count;

    struct Prototype **protos;
    uint32_t          proto_count;

    uint32_t       *lineInfos;
    uint32_t        lineInfo_count;

    AbsLineInfo    *absLineInfos;
    uint32_t        absLineInfo_count;

    LocalVar       *locVars;
    uint32_t        locVar_count;

    char          **upValueNames;
    uint32_t        upValueName_count;
} Prototype;
