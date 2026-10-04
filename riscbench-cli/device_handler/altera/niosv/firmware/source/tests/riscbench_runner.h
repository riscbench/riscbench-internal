#ifndef RISCBENCH_RUNNER_H
#define RISCBENCH_RUNNER_H

#include <stdbool.h>
#include <stdint.h>

int riscbench_run_one(uint32_t mode, uint32_t size, bool trace);
int riscbench_run_all_with_trace(bool trace);
int riscbench_run_all(void);
void riscbench_set_quiet(bool quiet);
void riscbench_set_precision(uint32_t precision);

typedef struct {
    uint32_t total_cycles, active_cycles, stall_cycles;
    uint32_t mem_wait_cycles, ops_done, trace_count, chunk_count;
    bool trace_overflow;
} riscbench_chunked_result_t;

int riscbench_run_vecadd_modes(uint32_t total_size, bool trace,
                               riscbench_chunked_result_t *performance,
                               riscbench_chunked_result_t *trace_result);
int riscbench_run_vecmul_modes(uint32_t total_size, bool trace,
                              riscbench_chunked_result_t *performance,
                              riscbench_chunked_result_t *trace_result);
int riscbench_run_saxpy_modes(uint32_t total_size, uint32_t alpha, bool trace,
                             riscbench_chunked_result_t *performance,
                             riscbench_chunked_result_t *trace_result);
int riscbench_run_dot_modes(uint32_t total_size, bool trace,
                           riscbench_chunked_result_t *performance,
                           riscbench_chunked_result_t *trace_result);
int riscbench_run_matmul_pattern(uint32_t n, uint32_t pattern, bool trace);
int riscbench_run_matmul_modes(uint32_t n, uint32_t pattern, bool trace,
                              riscbench_chunked_result_t *performance,
                              riscbench_chunked_result_t *trace_result);

#endif
