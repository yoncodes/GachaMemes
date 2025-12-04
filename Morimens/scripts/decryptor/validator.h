#include <stdint.h>

typedef struct {
    uint32_t reachable_count;   // total number of reachable instructions
    uint32_t trimmed_count;     // if no holes: last_reachable + 1; else = original count
    int      has_holes;         // 1 if there are unreachable instructions before last_reachable
} ReachabilityInfo;

ReachabilityInfo mark_reachable(uint32_t *code, uint32_t count, uint8_t *reachable);

int validate_instruction(int op, int A, int B, int C, int Bx, int k, int num_consts, int num_protos, int count);

// Validation result codes
#define VALID_OK 0          // Instruction is completely valid
#define VALID_NEEDS_FIX 1   // Structure valid but values out of bounds (fixable)
#define VALID_INVALID 2     // Invalid instruction structure