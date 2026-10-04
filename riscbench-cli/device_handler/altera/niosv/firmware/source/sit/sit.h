#ifndef SIT_H
#define SIT_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t mode;
    uint32_t size;
    uint32_t a_base;
    uint32_t b_base;
    uint32_t c_base;
    uint32_t alpha;
    uint32_t precision;
} sit_config_t;

typedef struct {
    uint32_t total_cycles;
    uint32_t active_cycles;
    uint32_t stall_cycles;
    uint32_t mem_wait_cycles;
    uint32_t ops_done;
} sit_counters_t;

typedef struct {
    uint64_t timestamp;
    uint16_t event_mask;
} sit_trace_entry_t;

void sit_configure(const sit_config_t *config);
void sit_start(void);
bool sit_wait_done(uint32_t timeout);
uint32_t sit_read_status(void);
sit_counters_t sit_get_counters(void);
void sit_print_counters(const sit_counters_t *counters);
uint32_t sit_trace_count(void);
bool sit_trace_overflow(void);
void sit_trace_read(uint32_t index, sit_trace_entry_t *entry);
void sit_trace_clear(void);

#endif
