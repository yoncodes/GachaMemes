#ifndef SUMMARY_H
#define SUMMARY_H

#include <stdint.h>
#include <stddef.h>

int analyze_instructions(const uint32_t *code, uint32_t count, int depth);

#endif // SUMMARY_H