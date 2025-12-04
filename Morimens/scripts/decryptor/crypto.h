#ifndef RC4_H
#define RC4_H

#include <stdint.h>
#include <stddef.h>

void decrypt_string_at(uint8_t *data, size_t offset, uint32_t len, uint8_t flag);
uint32_t decrypt_instruction(uint32_t encrypted, uint32_t position);
int decrypt_xlua_bytecode(uint8_t *data, size_t code_offset, uint32_t sizecode,
                          uint32_t linedefined, uint16_t seed16);

int bruteforce_xlua_seed16(uint8_t *data, size_t code_offset, uint32_t sizecode,
                           uint32_t linedefined, uint16_t *out_seed16);


#endif
