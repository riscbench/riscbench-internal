#ifndef FP32_REF_H
#define FP32_REF_H

#include <stdbool.h>
#include <stdint.h>

uint32_t riscbench_fp32_add(uint32_t a, uint32_t b);
uint32_t riscbench_fp32_mul(uint32_t a, uint32_t b);
uint32_t riscbench_vecadd_fp32_reference(uint32_t a, uint32_t b);
uint16_t riscbench_fp16_add_reference(uint16_t a, uint16_t b);
uint32_t riscbench_vecadd_fp16_reference(uint32_t a, uint32_t b);
uint32_t riscbench_vecmul_reference(uint32_t a, uint32_t b);
uint32_t riscbench_vecadd_int16_reference(uint32_t a, uint32_t b,
                                         bool lane1_valid);
uint32_t riscbench_vecmul_int16_reference(uint32_t a, uint32_t b,
                                         bool lane1_valid);
uint32_t riscbench_saxpy_int16_reference(int16_t alpha, uint32_t a, uint32_t b,
                                        bool lane1_valid);
uint32_t riscbench_dot_int16_reference(const uint32_t *a, const uint32_t *b,
                                      uint32_t logical_size);
uint32_t riscbench_vecadd_int8_reference(uint32_t a,uint32_t b,uint32_t valid_lanes);
uint32_t riscbench_vecmul_int8_reference(uint32_t a,uint32_t b,uint32_t valid_lanes);
uint32_t riscbench_saxpy_int8_reference(int8_t alpha,uint32_t a,uint32_t b,uint32_t valid_lanes);
uint32_t riscbench_dot_int8_reference(const uint32_t *a,const uint32_t *b,uint32_t logical_size);
uint32_t riscbench_saxpy_reference(uint32_t alpha, uint32_t a, uint32_t b);
uint32_t riscbench_dot_reference(const uint32_t *a, const uint32_t *b, uint32_t size);
void riscbench_matmul_reference(const uint32_t *a, const uint32_t *b,
                               uint32_t *c, uint32_t n);

#endif
