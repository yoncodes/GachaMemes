#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "varint.h"
#include "crypto.h"
#include "bytecode.h"
#include "proto.h"
#include "summary.h"
#include <stdlib.h>
#include "header.h"


/* ============================================================
 *  Constant table
 *  const_type:
 *    3  -> number  (8 bytes)
 *    19 -> integer (7bit varint)
 *    4,20 -> string (7bit length + data, RC4-encrypted)
 * ============================================================ */
void decrypt_constants(uint8_t *data, size_t *offset, size_t file_size,
                       uint8_t encryption_flag, int depth)
{
    uint32_t num_constants;
    if (!read_7bit_int(data, file_size, offset, &num_constants)) return;

    //printf("%*sConstants: %u\n", depth * 2, "", num_constants);

    for (uint32_t i = 0; i < num_constants; i++)
    {
        if (*offset >= file_size) break;

        uint8_t tag = data[(*offset)++];

        switch (tag)
        {
        case TAG_NIL: // 0x00
            //printf("%*s  [K%u] NIL\n", depth*2, "", i);
            break;

        case TAG_BOOLEAN_FALSE: // 0x01
            //printf("%*s  [K%u] BOOLEAN: false\n", depth*2, "", i);
            break;

        case TAG_BOOLEAN_TRUE: // 0x11 (17 decimal)
            //printf("%*s  [K%u] BOOLEAN: true\n", depth*2, "", i);
            break;

        case TAG_NUMBER: // 0x03 (3 decimal) - 8-byte INTEGER
            if (*offset + 8 > file_size) return;
            {
                int64_t v;
                memcpy(&v, &data[*offset], 8);
                *offset += 8;
                //printf("%*s  [K%u] INTEGER: %lld\n", depth*2, "", i, (long long)v);
            }
            break;

        case TAG_INTEGER: // 0x13 (19 decimal) - 8-byte FLOAT
            if (*offset + 8 > file_size) return;
            {
                double d;
                memcpy(&d, &data[*offset], 8);
                *offset += 8;
                //printf("%*s  [K%u] FLOAT: %g\n", depth*2, "", i, d);
            }
            break;

        case TAG_SHORT_STR:  // 0x04 (4 decimal)
        case TAG_LONG_STR:   // 0x14 (20 decimal)
        {
            uint32_t len;
            if (!read_7bit_int(data, file_size, offset, &len)) return;
            uint32_t slen = (len > 0 ? len - 1 : 0);

            if (*offset + slen > file_size) return;

            // Decrypt string characters ONLY
            decrypt_string_at(data, *offset, slen, encryption_flag);

            *offset += slen;
            break;
        }

        default:
            printf("%*s  [K%u] UNKNOWN CONST TAG %u (0x%02X) — stopping\n",
                   depth*2, "", i, tag, tag);
            return;
        }
    }
}

/* ============================================================
 *  Upvalues (non-name part)
 * ============================================================ */
void decrypt_upvalues(uint8_t *data, size_t *offset, size_t file_size, uint8_t encryption_flag, int depth) {
    uint32_t num_upvalues;
    if (!read_7bit_int(data, file_size, offset, &num_upvalues)) return;

    //printf("%*sUpvalues: %u\n", depth * 2, "", num_upvalues);

    // each upvalue: instack, idx, kind (3 bytes)
    for (uint32_t i = 0; i < num_upvalues; i++) {
        if (*offset + 3 > file_size) return;
        *offset += 3;
    }
}

/* ============================================================
 *  Nested protos (sub-functions)
 * ============================================================ */
 void decrypt_protos(uint8_t *data, size_t *offset, size_t file_size,
                     uint8_t encryption_flag, int depth, uint32_t parent_linedefined)
 {
     (void)parent_linedefined;

     // ADD DEPTH LIMIT
     if (depth > 50) {
         printf("%*s[ERR] Max proto depth exceeded\n", depth*2, "");
         return;
     }

     size_t start_offset = *offset;
     uint32_t num_protos;

     if (!read_7bit_int(data, file_size, offset, &num_protos)) {
         printf("%*s[ERR] Failed to read proto count\n", depth*2, "");
         return;
     }

     //  ADD SANITY CHECK
     if (num_protos > 10000) {
         printf("%*s[ERR] Unreasonable proto count: %u\n", depth*2, "", num_protos);
         printf("%*s     at offset %zu, bytes: ", depth*2, "", start_offset);
         for (int j = 0; j < 8 && start_offset + j < file_size; j++) {
             printf("%02X ", data[start_offset + j]);
         }
         printf("\n");
         return;
     }

     //printf("%*sNested Protos: %u\n", depth * 2, "", num_protos);

     for (uint32_t i = 0; i < num_protos; i++) {
         //  CHECK BOUNDS
        

         size_t proto_start = *offset;
         //printf("%*s=== Proto [%u] @ offset %zu ===\n", depth * 2, "", i, proto_start);

         decrypt_function(data, offset, file_size, encryption_flag, depth + 1);

         //  VERIFY PROGRESS
         size_t consumed = *offset - proto_start;
         if (consumed == 0) {
             printf("%*s[ERR] Proto %u didn't advance offset\n", depth*2, "", i);
             return;
         }
         if (consumed > 10000000) { // 10MB
             printf("%*s[ERR] Proto %u consumed too much: %zu bytes\n",
                    depth*2, "", i, consumed);
             return;
         }
     }
 }

/* ============================================================
 *  Debug info: lineinfo, abslineinfo, locvars, upvalue names
 * ============================================================ */
size_t decrypt_debug_info(uint8_t *data,
                          size_t  *offset,
                          size_t   file_size,
                          uint8_t  encryption_flag,
                          int      depth,
                          uint32_t final_instruction_count)
{
    (void)final_instruction_count; // for now we DON'T trim based on code size
    size_t bytes_removed = 0;

    /* ------------------------------------------------------------------
       1) LINEINFO: <sizelineinfo varint> + raw bytes
       ------------------------------------------------------------------ */
    size_t sizelineinfo_offset = *offset;

    uint32_t lineinfo_bytes = 0;
    if (!read_7bit_int(data, file_size, offset, &lineinfo_bytes))
        return 0;

    //printf("%*sLine info: %u bytes\n", depth * 2, "", lineinfo_bytes);

    size_t lineinfo_data_offset = *offset;

    if (lineinfo_data_offset + lineinfo_bytes > file_size) {
        printf("%*s[WARN] lineinfo outside file bounds\n", depth * 2, "");
        return 0;
    }

    /* IMPORTANT: **do not** shrink or move anything here.
       Just skip over the existing lineinfo bytes. */
    *offset = lineinfo_data_offset + lineinfo_bytes;

    /* ------------------------------------------------------------------
       2) ABS LINE INFO (pc, line pairs)
       ------------------------------------------------------------------ */
    uint32_t sizeabslineinfo = 0;
    if (!read_7bit_int(data, file_size, offset, &sizeabslineinfo))
        return bytes_removed;

    //printf("%*sAbs line info: %u entries\n", depth * 2, "", sizeabslineinfo);

    for (uint32_t i = 0; i < sizeabslineinfo; i++) {
        uint32_t pc  = 0;
        uint32_t line = 0;
        if (!read_7bit_int(data, file_size, offset, &pc))   return bytes_removed;
        if (!read_7bit_int(data, file_size, offset, &line)) return bytes_removed;

        /* You can *log* the clamp info, but DO NOT write back. */
        uint32_t clamped_pc = pc;
        if (final_instruction_count > 0 && pc >= final_instruction_count) {
            clamped_pc = final_instruction_count - 1;
            //printf("%*s  [ABS] pc %u → %u (would clamp)\n", depth * 2, "", pc, clamped_pc);
        } else {
            //printf("%*s  [ABS] pc %u → %u\n", depth * 2, "", pc, pc);
        }
    }

    /* ------------------------------------------------------------------
       3) LOCAL VARIABLES: name + (startpc,endpc)
       ------------------------------------------------------------------ */
    uint32_t sizelocvars = 0;
    if (!read_7bit_int(data, file_size, offset, &sizelocvars))
        return bytes_removed;

    //printf("%*sLocals: %u\n", depth * 2, "", sizelocvars);

    for (uint32_t i = 0; i < sizelocvars; i++) {

        /* ---- Local name ---- */
        uint32_t name_len = 0;
        if (!read_7bit_int(data, file_size, offset, &name_len))
            return bytes_removed;

        if (name_len > 0) {
            uint32_t actual = name_len - 1;
            if (*offset + actual > file_size) return bytes_removed;

            decrypt_string_at(data, *offset, actual, encryption_flag);
            //printf("%*s  [L%u] NAME: %.*s\n", depth * 2, "", i, (int)actual, &data[*offset]);

            *offset += actual;
        } else {
            //printf("%*s  [L%u] NAME: (empty)\n", depth * 2, "", i);
        }

        /* ---- STARTPC ---- */
        uint32_t startpc = 0;
        if (!read_7bit_int(data, file_size, offset, &startpc))
            return bytes_removed;

        /* ---- ENDP C ---- */
        uint32_t endpc = 0;
        if (!read_7bit_int(data, file_size, offset, &endpc))
            return bytes_removed;

        /* Again: only *log* the clamped range, do not rewrite. */
        uint32_t new_startpc = startpc;
        uint32_t new_endpc   = endpc;

        if (final_instruction_count > 0) {
            if (new_startpc >= final_instruction_count)
                new_startpc = 0;
            if (new_endpc > final_instruction_count)
                new_endpc = final_instruction_count;
        }

       // printf("%*s       RANGE: %u → %u (raw %u → %u)\n", depth * 2, "", new_startpc, new_endpc, startpc, endpc);

        /* DO NOT call write_7bit_int here.
           Re-encoding varints with shorter encodings would misalign
           all the following fields inside the chunk. */
    }

    /* ------------------------------------------------------------------
       4) UPVALUE NAMES
       ------------------------------------------------------------------ */
    uint32_t sizeupvalues = 0;
    if (!read_7bit_int(data, file_size, offset, &sizeupvalues))
        return bytes_removed;

    //printf("%*sUpvalue names: %u\n", depth * 2, "", sizeupvalues);

    for (uint32_t i = 0; i < sizeupvalues; i++) {
        uint32_t str_len = 0;
        if (!read_7bit_int(data, file_size, offset, &str_len))
            return bytes_removed;

        if (str_len > 0) {
            uint32_t actual_len = str_len - 1;
            if (*offset + actual_len > file_size) return bytes_removed;

            decrypt_string_at(data, *offset, actual_len, encryption_flag);
            //printf("%*s  [U%u] NAME: %.*s\n", depth * 2, "", i, (int)actual_len, &data[*offset]);

            *offset += actual_len;
        } else {
            //printf("%*s  [U%u] NAME: (empty)\n", depth * 2, "", i);
        }
    }

    /* We did not remove any bytes from the file layout. */
    return bytes_removed;
}


/* ============================================================
 *  Single function/proto
 * ============================================================ */
 size_t decrypt_function(uint8_t *data,
                         size_t  *offset,
                         size_t   file_size,
                         uint8_t  encryption_flag,
                         int      depth)
 {
     size_t function_base = *offset;
     size_t total_bytes_removed = 0;


     /* ======================================================
      * 1) SOURCE NAME
      * ====================================================== */
     uint32_t str_len;
     if (!read_7bit_int(data, file_size, offset, &str_len))
         return 0;

     //printf("%*sFunction at offset %zu\n", depth * 2, "", function_base);

     if (str_len > 0) {
         uint32_t actual = str_len - 1;
         if (*offset + actual > file_size) return 0;

         decrypt_string_at(data, *offset, actual, encryption_flag);
         printf("%*sSource: %.*s\n",
                depth * 2, "",
                (int)actual, (char *)&data[*offset]);

         *offset += actual;
     }

     /* ======================================================
      * 2) FUNCTION HEADER
      * ====================================================== */
     uint32_t linedefined, lastlinedefined;
     if (!read_7bit_int(data, file_size, offset, &linedefined)) return 0;
     if (!read_7bit_int(data, file_size, offset, &lastlinedefined)) return 0;

     if (*offset + 3 > file_size) return 0;

     uint8_t numparams       = data[(*offset)++];
     uint8_t is_vararg       = data[(*offset)++];
     size_t  maxstack_offset = *offset;
     uint8_t maxstack_raw    = data[(*offset)++];

     //printf("%*sLine defined:      %u\n", depth * 2, "", linedefined);
     //printf("%*sLast line defined: %u\n", depth * 2, "", lastlinedefined);
     //printf("%*sNum parameters:    %u\n", depth * 2, "", numparams);
     //printf("%*sVararg flag:       %u\n", depth * 2, "", is_vararg);
    //printf("%*sMax stack size:    %u (raw)\n",  depth * 2, "", maxstack_raw);

     /* ======================================================
      * 3) CODE SECTION
      * ====================================================== */
     uint32_t sizecode;
     size_t sizecode_offset = *offset;

     if (!read_7bit_int(data, file_size, offset, &sizecode))
         return 0;

     size_t code_offset = *offset;

     //printf("%*sCode: %u instructions @ %zu\n", depth * 2, "", sizecode, code_offset);

     /* ======================================================
      * 4) PEEK CONSTS / UPVALUES / PROTOS (unchanged)
      * ====================================================== */
     size_t temp_offset = code_offset + (size_t)sizecode * 4;

     uint32_t num_consts = 0;
     read_7bit_int(data, file_size, &temp_offset, &num_consts);

     for (uint32_t i = 0; i < num_consts; i++) {
         if (temp_offset >= file_size) break;

         uint8_t type = data[temp_offset++];
         if (type == 3 || type == 19) temp_offset += 8;
         else if (type == 4 || type == 20) {
             uint32_t sl;
             if (!read_7bit_int(data, file_size, &temp_offset, &sl)) break;
             temp_offset += (sl > 0 ? sl - 1 : 0);
         }
         else if (type != 0 && type != 1 && type != 17) break;
     }

     uint32_t num_upvalues = 0;
     read_7bit_int(data, file_size, &temp_offset, &num_upvalues);
     temp_offset += (size_t)num_upvalues * 3;

     uint32_t num_protos = 0;
     read_7bit_int(data, file_size, &temp_offset, &num_protos);

     //printf("%*sPeeked: consts=%u, upvalues=%u, protos=%u\n", depth * 2, "", num_consts, num_upvalues, num_protos);

     uint32_t final_instruction_count = sizecode;

     /* ======================================================
      * 5) REAL DECRYPT — USE FIXED MORIMEN RC4 KEY
      * ====================================================== */
     if (encryption_flag && sizecode > 0) {

         //printf("%*sApplying Morimen RC4 (fixed key 0000000000005000)\n", depth * 2, "");

         //decrypt_code_rc4_vm(data, code_offset, sizecode);

         /* =====================
          * 6) VALIDATE / FIX
          * ===================== */
         //printf("%*sRunning validator / fixer...\n", depth * 2, "");

         DecryptResult res = decrypt_bytecode(
             data,
             code_offset,
             sizecode,
             linedefined,
             num_protos,
             num_consts,
             depth,
             sizecode_offset,
             file_size
         );

         final_instruction_count = res.final_count;
         total_bytes_removed += res.removed_bytes;

         //printf("%*sFinal instruction count = %u\n", depth * 2, "", final_instruction_count);

         /* ==================================================
          * 7) FIX MAXSTACK
          * ================================================== */
         int real_max_reg = analyze_instructions(
             (uint32_t *)&data[code_offset],
             final_instruction_count,
             depth + 1
         );

         uint8_t current_max = data[maxstack_offset];
         if (real_max_reg + 5 >= current_max || real_max_reg >= current_max) {
             uint8_t fixed = (real_max_reg >= 240) ? 250 : (real_max_reg + 8);
             //printf("%*sFix maxstack: %u → %u (used=%d)\n", depth * 2, "", current_max, fixed, real_max_reg);
             data[maxstack_offset] = fixed;
         }

         /* ==================================================
          * SUMMARY
          * ================================================== */
         if (depth == 0) {
             //printf("\n");
             //printf(" MAIN FUNCTION SUMMARY\n");
             //printf(" Instructions: %u\n", final_instruction_count);
             //printf(" Nested protos: %u\n", num_protos);
             //printf("\n");
         }
     }

     /* ======================================================
      * 8) ADVANCE OFFSET PAST REAL CODE SIZE
      * ====================================================== */
     *offset = code_offset + (size_t)final_instruction_count * 4;

     /* ======================================================
      * 9–12) CONSTANTS / UPVALUES / PROTOS / DEBUG
      * ====================================================== */
     decrypt_constants(data, offset, file_size, encryption_flag, depth);
     decrypt_upvalues(data, offset, file_size, encryption_flag, depth);
     decrypt_protos(data, offset, file_size, encryption_flag, depth, linedefined);
     decrypt_debug_info(
         data, offset, file_size,
         encryption_flag, depth,
         final_instruction_count
     );

     return total_bytes_removed;
 }
