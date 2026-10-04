#include "vecadd.h"

#include <inttypes.h>
#include <stddef.h>
#include <stdio.h>

#include "sys/alt_cache.h"
#include "workloads/fp32_ref.h"

static volatile uint32_t *const ddr_a =
    (volatile uint32_t *)(uintptr_t)VECADD_A_BASE;
static volatile uint32_t *const ddr_b =
    (volatile uint32_t *)(uintptr_t)VECADD_B_BASE;
static volatile uint32_t *const ddr_c =
    (volatile uint32_t *)(uintptr_t)VECADD_C_BASE;

static inline void vecadd_memory_barrier(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

uint32_t vecadd_generate_a(uint32_t index)
{
    return (index & 1u) ? UINT32_C(0x3f000000) : UINT32_C(0x3f800000);
}

uint32_t vecadd_generate_b(uint32_t index)
{
    return (index & 1u) ? UINT32_C(0x3fc00000) : UINT32_C(0x40000000);
}

uint32_t vecadd_reference(uint32_t a, uint32_t b)
{
    return riscbench_vecadd_fp32_reference(a, b);
}

bool vecadd_initialize_ddr(uint32_t size)
{
    size_t byte_count;

    if ((size == 0u) || (size > VECADD_MAX_SIZE)) {
        printf("INPUT_INIT_FAIL size=%" PRIu32 " max_size=%u\n",
               size, VECADD_MAX_SIZE);
        return false;
    }

    for (uint32_t i = 0; i < size; ++i) {
        ddr_a[i] = vecadd_generate_a(i);
        ddr_b[i] = vecadd_generate_b(i);
        ddr_c[i] = 0u;
    }

    byte_count = (size_t)size * sizeof(uint32_t);
    alt_dcache_flush((void *)(uintptr_t)VECADD_A_BASE, byte_count);
    alt_dcache_flush((void *)(uintptr_t)VECADD_B_BASE, byte_count);
    alt_dcache_flush((void *)(uintptr_t)VECADD_C_BASE, byte_count);
    vecadd_memory_barrier();
    return true;
}

bool vecadd_validate_inputs(uint32_t size)
{
    uint32_t mismatches = 0u;
    size_t byte_count = (size_t)size * sizeof(uint32_t);

    /* Read back from DDR, not from potentially retained cache lines. */
    alt_dcache_flush_no_writeback((void *)(uintptr_t)VECADD_A_BASE, byte_count);
    alt_dcache_flush_no_writeback((void *)(uintptr_t)VECADD_B_BASE, byte_count);
    vecadd_memory_barrier();

    for (uint32_t i = 0; i < size; ++i) {
        uint32_t expected_a = vecadd_generate_a(i);
        uint32_t expected_b = vecadd_generate_b(i);
        uint32_t actual_a = ddr_a[i];
        uint32_t actual_b = ddr_b[i];

        if ((actual_a != expected_a) || (actual_b != expected_b)) {
            printf("INPUT_MISMATCH index=%" PRIu32
                   " expected_a=0x%08" PRIX32
                   " actual_a=0x%08" PRIX32
                   " expected_b=0x%08" PRIX32
                   " actual_b=0x%08" PRIX32 "\n",
                   i, expected_a, actual_a, expected_b, actual_b);
            ++mismatches;
        }
    }

    if (mismatches == 0u) {
        printf("INPUT_CHECK_PASS\n");
        return true;
    }

    printf("INPUT_CHECK_FAIL mismatches=%" PRIu32 "\n", mismatches);
    return false;
}

bool vecadd_verify_results(uint32_t size)
{
    uint32_t mismatches = 0u;
    size_t byte_count = (size_t)size * sizeof(uint32_t);

    alt_dcache_flush_no_writeback((void *)(uintptr_t)VECADD_C_BASE, byte_count);
    vecadd_memory_barrier();

    for (uint32_t i = 0; i < size; ++i) {
        uint32_t a = ddr_a[i];
        uint32_t b = ddr_b[i];
        uint32_t expected = vecadd_reference(a, b);
        uint32_t actual = ddr_c[i];

        if (actual != expected) {
            printf("RESULT_MISMATCH index=%" PRIu32
                   " a=0x%08" PRIX32 " b=0x%08" PRIX32
                   " expected=0x%08" PRIX32
                   " actual=0x%08" PRIX32 "\n",
                   i, a, b, expected, actual);
            ++mismatches;
        }
    }

    if (mismatches != 0u) {
        printf("RESULT_CHECK_FAIL mismatches=%" PRIu32 "\n", mismatches);
        return false;
    }

    printf("RESULT_CHECK_PASS\n");
    return true;
}
