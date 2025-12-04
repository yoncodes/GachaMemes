#include "crypto.h"
#include "opcode.h"
#include "validator.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

static void rc4_ksa(uint8_t *S, const uint8_t *key, unsigned int key_len) {
    unsigned int i, j = 0;
    for (i = 0; i < 256; i++) S[i] = (uint8_t)i;
    for (i = 0; i < 256; i++) {
        j = (j + S[i] + key[i % key_len]) & 0xFF;
        uint8_t tmp = S[i];
        S[i] = S[j];
        S[j] = tmp;
    }
}

static void rc4_prga(uint8_t *S, uint8_t *buf, unsigned int len) {
    unsigned int i = 0, j = 0;
    while (len--) {
        i = (i + 1) & 0xFF;
        uint8_t si = S[i];
        j = (j + si) & 0xFF;
        uint8_t sj = S[j];
        S[i] = sj;
        S[j] = si;
        uint8_t k = S[(si + sj) & 0xFF];
        *buf++ ^= k;
    }
}

void decrypt_string_at(uint8_t *data, size_t offset, uint32_t len, uint8_t flag) {
    if (!flag) return;

    uint8_t mod_val = len % 0xFE;
    if (!mod_val) return;

    uint8_t key[8] = {0};
    key[6] = mod_val;
    key[7] = mod_val + 1;

    uint8_t S[256];
    rc4_ksa(S, key, 8);
    rc4_prga(S, &data[offset], len);
}

/// probably wrong stock lua is opcode & 0x7F
uint32_t decrypt_instruction(uint32_t encrypted, uint32_t position) {


   /* uint32_t dec = encrypted ^ position;
    uint8_t op = (uint8_t)(dec & 0x7F);
    if (op <= 83) return dec;

    op = (uint8_t)(encrypted & 0x7F);
    if (op <= 83) return encrypted;

    uint32_t alt = position ^ 0x40;
    dec = encrypted ^ alt;
    op = (uint8_t)(dec & 0x7F);
    if (op <= 83) return dec;

    return encrypted ^ position; */

    return encrypted;
}

/**
 * Compute the 16-bit 'inner seed' used by RC4:
 *     inner_seed = ((linedefined XOR seed16) % 0xFFF1) + 15
 */
static inline uint16_t derive_inner_seed(uint32_t linedefined, uint16_t seed16)
{
    uint32_t xor_val = linedefined ^ seed16;
    uint32_t mod_val = xor_val % 0xFFF1;  // 65521 (Adler-32 prime)
    return (uint16_t)((mod_val + 15) & 0xFFFF);
}

/**
 * Reconstruct the runtime Proto+0x88 field from inner seed:
 *     proto_0x88 = (first_inst >> 15) XOR inner_seed
 */
static inline uint16_t compute_proto_0x88(uint32_t first_inst, uint16_t inner_seed)
{
    uint16_t first_shifted = (first_inst >> 15) & 0xFFFF;
    return (first_shifted ^ inner_seed) & 0xFFFF;
}

/* ============================================================
 *  RC4 Implementation for XLua Bytecode
 * ============================================================ */

/**
 * RC4 KSA (Key Scheduling Algorithm) using 8-byte key storage.
 * The seed is stored at positions 6 and 7 (little-endian).
 */
static void rc4_ksa_xlua(uint8_t S[256], uint16_t seed)
{
    // Build 8-byte key storage with seed at positions 6-7
    uint8_t key_storage[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    key_storage[6] = seed & 0xFF;
    key_storage[7] = (seed >> 8) & 0xFF;

    // Initialize S-box
    for (int i = 0; i < 256; i++) {
        S[i] = (uint8_t)i;
    }

    // KSA - use key_storage[i & 7] pattern
    uint8_t j = 0;
    for (int i = 0; i < 256; i++) {
        j = (uint8_t)(j + S[i] + key_storage[i & 7]);

        // Swap S[i] and S[j]
        uint8_t tmp = S[i];
        S[i] = S[j];
        S[j] = tmp;
    }
}

/**
 * RC4 PRGA (Pseudo-Random Generation Algorithm) for XLua.
 * Decrypts from byte 4 onwards (first instruction stays unencrypted).
 */
static void rc4_prga_xlua(uint8_t S[256], uint8_t *buf, size_t len)
{
    uint8_t i = 0, j = 0;

    // Start decryption from byte 4 (skip first instruction)
    for (size_t offset = 4; offset < len; offset++) {
        i = (uint8_t)(i + 1);
        uint8_t si = S[i];
        j = (uint8_t)(j + si);
        uint8_t sj = S[j];

        // Swap
        S[i] = sj;
        S[j] = si;

        // Generate keystream byte and XOR
        uint8_t k = S[(uint8_t)(si + sj)];
        buf[offset] ^= k;
    }
}

/* ============================================================
 *  Public API Functions
 * ============================================================ */

/**
 * Decrypt XLua bytecode using the seed16 system.
 *
 * @param data          File buffer
 * @param code_offset   Offset where bytecode starts
 * @param sizecode      Number of instructions
 * @param linedefined   Line where function is defined
 * @param seed16        File-level encryption seed (0x0000-0xFFFF)
 * @return              1 if successful, 0 if failed
 */
int decrypt_xlua_bytecode(uint8_t *data,
                          size_t code_offset,
                          uint32_t sizecode,
                          uint32_t linedefined,
                          uint16_t seed16)
{
    if (sizecode == 0) {
        return 0;
    }

    size_t code_size = (size_t)sizecode * 4;

    // Get first instruction (should remain unchanged after decryption)
    uint32_t first_inst;
    memcpy(&first_inst, &data[code_offset], 4);

    // Compute inner_seed
    uint16_t inner_seed = derive_inner_seed(linedefined, seed16);

    // Initialize RC4 with inner_seed
    uint8_t S[256];
    rc4_ksa_xlua(S, inner_seed);

    // Decrypt bytecode (skips first instruction)
    rc4_prga_xlua(S, &data[code_offset], code_size);

    // Validate: first instruction should be unchanged
    uint32_t first_dec;
    memcpy(&first_dec, &data[code_offset], 4);

    return (first_dec == first_inst) ? 1 : 0;
}

/**
 * Brute-force the file-level seed16 value.
 *
 * @param data          File buffer
 * @param code_offset   Offset where bytecode starts
 * @param sizecode      Number of instructions
 * @param linedefined   Line where function is defined (usually 0 for main)
 * @param out_seed16    Output: discovered seed16 value
 * @return              1 if found, 0 if failed
 */
int bruteforce_xlua_seed16(uint8_t *data,
                            size_t code_offset,
                            uint32_t sizecode,
                            uint32_t linedefined,
                            uint16_t *out_seed16)
{
    if (sizecode == 0) {
        return 0;
    }

    size_t code_size = (size_t)sizecode * 4;

    // Backup original bytecode
    uint8_t *backup = malloc(code_size);
    if (!backup) {
        return 0;
    }
    memcpy(backup, &data[code_offset], code_size);

    // Get first instruction for validation
    uint32_t first_inst;
    memcpy(&first_inst, backup, 4);

    // Try all possible seed16 values
    for (uint32_t seed16 = 0; seed16 < 0x10000; seed16++) {
        // Restore original bytecode
        memcpy(&data[code_offset], backup, code_size);

        // Compute inner_seed
        uint16_t inner_seed = derive_inner_seed(linedefined, (uint16_t)seed16);

        // Decrypt
        uint8_t S[256];
        rc4_ksa_xlua(S, inner_seed);
        rc4_prga_xlua(S, &data[code_offset], code_size);

        // Validate: first instruction unchanged
        uint32_t first_dec;
        memcpy(&first_dec, &data[code_offset], 4);

        if (first_dec != first_inst) {
            continue;
        }

        // Check if opcodes look valid
        int valid_count = 0;
        int check_count = (sizecode < 10) ? sizecode : 10;

        for (int i = 0; i < check_count; i++) {
            uint32_t instr;
            memcpy(&instr, &data[code_offset + i * 4], 4);

            uint8_t opcode = instr & 0x7F;
            if (opcode <= 82) {  // Valid opcode range
                valid_count++;
            }
        }

        // If 30% or more opcodes are valid, we found it
        if (valid_count >= check_count * 0.3) {
            *out_seed16 = (uint16_t)seed16;
            free(backup);
            return 1;
        }
    }

    // Failed - restore original
    memcpy(&data[code_offset], backup, code_size);
    free(backup);
    return 0;
}
