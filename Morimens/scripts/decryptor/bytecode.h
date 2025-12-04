#ifndef BYTECODE_H
#define BYTECODE_H

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

typedef struct {
    uint32_t final_count;        // final number of instructions
    uint32_t removed_instr;      // number of unreachable instructions removed
    uint32_t removed_bytes;      // removed_instr * 4
} DecryptResult;


DecryptResult decrypt_bytecode(
    uint8_t *data,
    size_t   offset,
    uint32_t count,
    uint32_t linedefined,
    int      num_protos,
    int      num_consts,
    int      depth,
    size_t   sizecode_offset,
    size_t   file_size
);

extern FILE *g_log_file;   // Only declaration

void open_log_file(const char *path);
void close_log_file(void);

#define LOGF(fmt, ...) do {                     \
    printf(fmt, ##__VA_ARGS__);                 \
    if (g_log_file) fprintf(g_log_file, fmt, ##__VA_ARGS__); \
} while(0)


#endif
