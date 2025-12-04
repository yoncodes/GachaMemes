#ifndef PROTO_H
#define PROTO_H

#include <stdint.h>
#include <stddef.h>
#include <sys/types.h>

#ifdef _MSC_VER
#include <BaseTsd.h>
typedef SSIZE_T ssize_t;
#endif

#ifndef GLOBALS_H
#define GLOBALS_H

extern int g_failed_files;
extern int g_total_files;
extern int g_processed_files;

#endif


size_t decrypt_function(uint8_t *data, size_t *offset, size_t size, uint8_t flag, int depth);

// Write a varint (simple version for values < 16384)
static void write_varint(uint8_t *data, size_t *offset, uint32_t value) {
    if (value < 128) {
        data[(*offset)++] = value;
    } else if (value < 16384) {
        data[(*offset)++] = (value & 0x7F) | 0x80;
        data[(*offset)++] = (value >> 7) & 0x7F;
    } else {
        // Handle larger values if needed
        data[(*offset)++] = (value & 0x7F) | 0x80;
        data[(*offset)++] = ((value >> 7) & 0x7F) | 0x80;
        data[(*offset)++] = (value >> 14) & 0x7F;
    }
}

typedef struct {
    uint8_t raw[128];   // full 128-byte proto header block
} ProtoHeader128;

typedef struct {
    uint32_t seedA;  // from offset 0x80
    uint32_t seedB;  // from offset 0x84
    uint32_t seedC;  // from offset 0x88
} ProtoSeeds;

static inline ProtoSeeds parse_proto_seeds(const uint8_t *ex)
{
    ProtoSeeds s;
    s.seedA = *(const uint32_t *)&ex[0x80];
    s.seedB = *(const uint32_t *)&ex[0x84];
    s.seedC = *(const uint32_t *)&ex[0x88];
    return s;
}



#endif
