#include "varint.h"

int read_7bit_int(const uint8_t *data, size_t len, size_t *offset, uint32_t *result) {
    *result = 0;
    size_t pos = *offset;

    while (pos < len) {
        uint8_t byte = data[pos++];
        *result = (*result << 7) | (byte & 0x7F);

        if (byte & 0x80) {
            *offset = pos;
            return 1;
        }
    }
    return 0;
}

int write_7bit_int(uint8_t *data, size_t file_size, size_t *offset, uint32_t value)
{
    uint8_t tmp[6];
    int n = 0;

    uint32_t v = value;
    do {
        tmp[n++] = (uint8_t)(v & 0x7F);
        v >>= 7;
    } while (v > 0);


    for (int i = n - 1; i >= 0; i--) {
        if (*offset >= file_size) return 0;

        uint8_t byte = tmp[i];

        if (i == 0) {
           
            byte |= 0x80;   // end marker
        } else {
            byte &= 0x7F;   
        }

        data[*offset] = byte;
        (*offset)++;
    }

    return 1;
}
