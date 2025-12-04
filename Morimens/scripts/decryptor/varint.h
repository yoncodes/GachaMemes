#ifndef VARINT_H
#define VARINT_H

#include <stdint.h>
#include <stddef.h>

int read_7bit_int(const uint8_t *data, size_t len, size_t *offset, uint32_t *result);
int write_7bit_int(uint8_t *data, size_t file_size, size_t *offset, uint32_t value);

#endif
