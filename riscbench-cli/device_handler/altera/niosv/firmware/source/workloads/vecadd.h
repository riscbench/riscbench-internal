#ifndef VECADD_H
#define VECADD_H

#include <stdbool.h>
#include <stdint.h>

#define VECADD_A_BASE        0x00100000u
#define VECADD_B_BASE        0x00200000u
#define VECADD_C_BASE        0x00300000u
#define VECADD_MAX_SIZE      1024u

uint32_t vecadd_generate_a(uint32_t index);
uint32_t vecadd_generate_b(uint32_t index);
uint32_t vecadd_reference(uint32_t a, uint32_t b);
bool vecadd_initialize_ddr(uint32_t size);
bool vecadd_validate_inputs(uint32_t size);
bool vecadd_verify_results(uint32_t size);

#endif
