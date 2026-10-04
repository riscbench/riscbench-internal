#include "sit.h"

#include <inttypes.h>
#include <stddef.h>
#include <stdio.h>

#include "sit_regs.h"

static inline void sit_memory_barrier(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

static inline void sit_write_register(uint32_t offset, uint32_t value)
{
    volatile uint32_t *reg =
        (volatile uint32_t *)(uintptr_t)(SIT_CSR_BASE + offset);

    *reg = value;
    sit_memory_barrier();
}

static inline uint32_t sit_read_register(uint32_t offset)
{
    volatile const uint32_t *reg =
        (volatile const uint32_t *)(uintptr_t)(SIT_CSR_BASE + offset);
    uint32_t value = *reg;

    sit_memory_barrier();
    return value;
}

void sit_configure(const sit_config_t *config)
{
    if (config == NULL) {
        return;
    }

    sit_write_register(SIT_MODE_OFFSET, config->mode);
    sit_write_register(SIT_SIZE_OFFSET, config->size);
    sit_write_register(SIT_A_BASE_OFFSET, config->a_base);
    sit_write_register(SIT_B_BASE_OFFSET, config->b_base);
    sit_write_register(SIT_C_BASE_OFFSET, config->c_base);
    sit_write_register(SIT_ALPHA_OFFSET, config->alpha);
    sit_write_register(SIT_PRECISION_OFFSET, config->precision);
}

void sit_start(void)
{
    sit_write_register(SIT_CTRL_OFFSET, SIT_CTRL_START);
}

bool sit_wait_done(uint32_t timeout)
{
    for (uint32_t poll = 0; poll < timeout; ++poll) {
        if ((sit_read_status() & SIT_STATUS_DONE) != 0u) {
            return true;
        }
    }

    return false;
}

uint32_t sit_read_status(void)
{
    return sit_read_register(SIT_STATUS_OFFSET);
}

sit_counters_t sit_get_counters(void)
{
    sit_counters_t counters;

    counters.total_cycles    = sit_read_register(SIT_TOTAL_CYCLES_LO_OFFSET);
    counters.active_cycles   = sit_read_register(SIT_ACTIVE_CYCLES_LO_OFFSET);
    counters.mem_wait_cycles = sit_read_register(SIT_MEM_WAIT_CYCLES_LO_OFFSET);
    counters.ops_done        = sit_read_register(SIT_OPS_COMPLETED_LO_OFFSET);
    counters.stall_cycles    = (counters.total_cycles >= counters.active_cycles + counters.mem_wait_cycles)
                               ? (counters.total_cycles - counters.active_cycles - counters.mem_wait_cycles) : 0u;
    return counters;
}

void sit_print_counters(const sit_counters_t *counters)
{
    if (counters == NULL) {
        return;
    }

    printf("total_cycles=%" PRIu32 "\n", counters->total_cycles);
    printf("active_cycles=%" PRIu32 "\n", counters->active_cycles);
    printf("stall_cycles=%" PRIu32 "\n", counters->stall_cycles);
    printf("mem_wait_cycles=%" PRIu32 "\n", counters->mem_wait_cycles);
    printf("ops_done=%" PRIu32 "\n", counters->ops_done);
}

uint32_t sit_trace_count(void)
{
    return sit_read_register(SIT_TRACE_COUNT_OFFSET);
}

bool sit_trace_overflow(void)
{
    return sit_read_register(SIT_TRACE_OVERFLOW_OFFSET) != 0u;
}

void sit_trace_read(uint32_t index, sit_trace_entry_t *entry)
{
    if (entry == NULL) return;
    sit_write_register(SIT_TRACE_EVENT_INDEX_OFFSET, index);
    (void)sit_read_register(SIT_TRACE_EVENT_LO_OFFSET);
    uint64_t raw = (uint64_t)sit_read_register(SIT_TRACE_EVENT_LO_OFFSET) |
                   ((uint64_t)sit_read_register(SIT_TRACE_EVENT_HI_OFFSET) << 32);
    entry->timestamp = raw & UINT64_C(0x0000ffffffffffff);
    entry->event_mask = (uint16_t)(raw >> 48);
}

void sit_trace_clear(void) { sit_write_register(SIT_TRACE_CLEAR_OFFSET, 1u); }
