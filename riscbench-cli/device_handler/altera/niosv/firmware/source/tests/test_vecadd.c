#include <inttypes.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "sit/sit.h"
#include "sit/sit_regs.h"
#include "workloads/vecadd.h"

#define VECADD_STATUS_TIMEOUT  50000000u

static const uint32_t vecadd_sizes[] = {1u, 16u, 20u, 64u, 256u, 1024u};

static bool run_vecadd_test(uint32_t size)
{
    sit_config_t config = {
        .mode = SIT_MODE_VECADD,
        .size = size,
        .a_base = VECADD_A_BASE,
        .b_base = VECADD_B_BASE,
        .c_base = VECADD_C_BASE,
        .precision = SIT_PRECISION_FP32
    };
    sit_counters_t counters = {0};
    bool input_ok;
    bool done = false;
    bool result_ok = false;
    bool ops_ok = false;
    bool active_ok = false;
    bool passed;

    printf("VECADD_TEST_BEGIN size=%" PRIu32 "\n", size);

    input_ok = vecadd_initialize_ddr(size) && vecadd_validate_inputs(size);
    if (input_ok) {
        sit_configure(&config);
        sit_start();
        done = sit_wait_done(VECADD_STATUS_TIMEOUT);

        if (!done) {
            printf("SIT_TIMEOUT status=0x%08" PRIX32 "\n",
                   sit_read_status());
        } else {
            result_ok = vecadd_verify_results(size);
        }

        counters = sit_get_counters();
        ops_ok = done && (counters.ops_done == size);
        active_ok = done && (counters.active_cycles == size);

        if (!ops_ok) {
            printf("OPS_DONE_MISMATCH expected=%" PRIu32
                   " actual=%" PRIu32 "\n",
                   size, counters.ops_done);
        }
        if (!active_ok) {
            printf("ACTIVE_CYCLES_MISMATCH expected=%" PRIu32
                   " actual=%" PRIu32 "\n",
                   size, counters.active_cycles);
        }
    } else {
        printf("SIT_START_SKIPPED reason=INPUT_CHECK_FAIL\n");
    }

    passed = input_ok && done && result_ok && ops_ok && active_ok;

    printf("RISCBENCH_FPGA_COUNTER_BEGIN\n");
    printf("platform=agilex_niosv\n");
    printf("kernel=vecadd_ddr\n");
    printf("size=%" PRIu32 "\n", size);
    printf("status=%s\n", passed ? "PASS" : "FAIL");
    printf("input_check=%s\n", input_ok ? "PASS" : "FAIL");
    sit_print_counters(&counters);
    printf("RISCBENCH_FPGA_COUNTER_END\n");
    printf("VECADD_TEST_END size=%" PRIu32 "\n", size);

    return passed;
}

int test_vecadd_sweep(void)
{
    bool sweep_passed = true;

    for (size_t i = 0; i < sizeof(vecadd_sizes) / sizeof(vecadd_sizes[0]); ++i) {
        if (!run_vecadd_test(vecadd_sizes[i])) {
            sweep_passed = false;
        }
    }

    return sweep_passed ? 0 : 1;
}
