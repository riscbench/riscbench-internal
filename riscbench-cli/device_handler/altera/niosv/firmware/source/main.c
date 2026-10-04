#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "run_config.h"
#include "sit/sit.h"
#include "sit/sit_regs.h"
#include "sys/alt_cache.h"
#include "system.h"
#include "tests/riscbench_runner.h"
#include "tests/riscbench_debug.h"

#define RISCBENCH_MAILBOX_MAGIC UINT32_C(0x52425354)
#define RISCBENCH_MAILBOX_FAILURE_MAGIC UINT32_C(0x52424641)

#define SIT_MONITOR_CTRL_OFFSET       0x1Cu
#define SIT_TOTAL_CYCLES_LO_OFFSET    0x60u
#define SIT_TOTAL_CYCLES_HI_OFFSET    0x64u
#define SIT_ACTIVE_CYCLES_LO_OFFSET   0x68u
#define SIT_ACTIVE_CYCLES_HI_OFFSET   0x6Cu
#define SIT_MEM_WAIT_CYCLES_LO_OFFSET 0x70u
#define SIT_MEM_WAIT_CYCLES_HI_OFFSET 0x74u
#define SIT_OPS_COMPLETED_LO_OFFSET   0x78u
#define SIT_OPS_COMPLETED_HI_OFFSET   0x7Cu

typedef struct {
    uint64_t total_cycles;
    uint64_t active_cycles;
    uint64_t mem_wait_cycles;
    uint64_t ops_completed;
} sit_perf_t;

static inline void sit_perf_memory_barrier(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

static inline void sit_perf_write_reg(uint32_t offset, uint32_t value)
{
    volatile uint32_t *reg = (volatile uint32_t *)(uintptr_t)(SIT_CSR_BASE + offset);
    *reg = value;
    sit_perf_memory_barrier();
}

static inline uint32_t sit_perf_read_reg(uint32_t offset)
{
    volatile const uint32_t *reg = (volatile const uint32_t *)(uintptr_t)(SIT_CSR_BASE + offset);
    uint32_t value = *reg;
    sit_perf_memory_barrier();
    return value;
}

static inline void sit_perf_monitor_enable(bool enable)
{
    sit_perf_write_reg(SIT_MONITOR_CTRL_OFFSET, enable ? 1u : 0u);
}

static uint64_t sit_perf_read_counter64(uint32_t lo_offset, uint32_t hi_offset)
{
    uint32_t hi1, lo, hi2;
    do {
        hi1 = sit_perf_read_reg(hi_offset);
        lo  = sit_perf_read_reg(lo_offset);
        hi2 = sit_perf_read_reg(hi_offset);
    } while (hi1 != hi2);
    return ((uint64_t)hi1 << 32) | (uint64_t)lo;
}

static void sit_perf_collect(sit_perf_t *perf)
{
    if (perf == NULL) return;
    perf->total_cycles    = sit_perf_read_counter64(SIT_TOTAL_CYCLES_LO_OFFSET, SIT_TOTAL_CYCLES_HI_OFFSET);
    perf->active_cycles   = sit_perf_read_counter64(SIT_ACTIVE_CYCLES_LO_OFFSET, SIT_ACTIVE_CYCLES_HI_OFFSET);
    perf->mem_wait_cycles = sit_perf_read_counter64(SIT_MEM_WAIT_CYCLES_LO_OFFSET, SIT_MEM_WAIT_CYCLES_HI_OFFSET);
    perf->ops_completed   = sit_perf_read_counter64(SIT_OPS_COMPLETED_LO_OFFSET, SIT_OPS_COMPLETED_HI_OFFSET);
}

static inline void direct_jtag_uart_putc(char c)
{
    volatile uint32_t *ctrl = (volatile uint32_t *)(uintptr_t)(JTAG_UART_0_BASE + 4);
    volatile uint32_t *data = (volatile uint32_t *)(uintptr_t)JTAG_UART_0_BASE;
    uint32_t timeout = 50000u;
    while (((*ctrl) & 0xFFFF0000u) == 0 && --timeout) {
        /* wait for space in FIFO with non-blocking timeout */
    }
    if (timeout > 0) {
        *data = (uint32_t)(uint8_t)c;
    }
}

static inline void direct_jtag_uart_puts(const char *s)
{
    while (*s) {
        if (*s == '\n') direct_jtag_uart_putc('\r');
        direct_jtag_uart_putc(*s++);
    }
}

static void sit_perf_dump_counter_regs(void)
{
    char buf[128];
    direct_jtag_uart_puts("CSR_DUMP_0x60_0x7C_BEGIN\n");
    printf("CSR_DUMP_0x60_0x7C_BEGIN\n");
    for (uint32_t offset = 0x60u; offset <= 0x7Cu; offset += 4u) {
        uint32_t val = sit_perf_read_reg(offset);
        snprintf(buf, sizeof(buf), "REG[0x%02" PRIx32 " / 0x%08" PRIx32 "] = 0x%08" PRIx32 " (%" PRIu32 ")\n",
                 offset, (uint32_t)(SIT_CSR_BASE + offset), val, val);
        printf("%s", buf);
        direct_jtag_uart_puts(buf);
    }
    direct_jtag_uart_puts("CSR_DUMP_0x60_0x7C_END\n");
    printf("CSR_DUMP_0x60_0x7C_END\n");
    fflush(stdout);
}

static void sit_perf_print(const sit_perf_t *perf)
{
    if (perf == NULL) return;
    char buf[256];
    snprintf(buf, sizeof(buf), "PERF,total_cycles=%" PRIu64 ",active_cycles=%" PRIu64 ",mem_wait_cycles=%" PRIu64 ",ops_completed=%" PRIu64 "\n",
             perf->total_cycles, perf->active_cycles, perf->mem_wait_cycles, perf->ops_completed);
    printf("%s", buf);
    direct_jtag_uart_puts(buf);
}

typedef struct {
    uint32_t magic;
    uint32_t status;
    uint32_t mode;
    uint32_t size;
    uint32_t total_cycles;
    uint32_t active_cycles;
    uint32_t stall_cycles;
    uint32_t mem_wait_cycles;
    uint32_t ops_done;
    uint32_t trace_count;
} riscbench_result_t;

#if !RISCBENCH_AUTORUN
static void print_info(void)
{
    printf("RISCBENCH_INFO_BEGIN\n");
    printf("platform=agilex_niosv\n");
    printf("modes=0:VECADD,1:VECMUL,2:DOT,3:MATMUL,4:SAXPY,5:ALL\n");
    printf("precisions=0:INT8,1:INT16,2:INT32,3:FP16,4:FP32\n");
    printf("supported_precisions=0:INT8,1:INT16,4:FP32\n");
    printf("ddr_base=0x%08" PRIx32 "\n", (uint32_t)EMIF_IO96B_DDR4COMP_0_BASE);
    printf("ddr_span=%" PRIu32 "\n", (uint32_t)EMIF_IO96B_DDR4COMP_0_SPAN);
    printf("bucket_trace=1\n");
    printf("bucket_cycles=%u\n", SIT_TRACE_BUCKET_CYCLES);
    printf("RISCBENCH_INFO_END\n");
}
#endif

#if !RISCBENCH_AUTORUN
static uint32_t field_u32(const char *line, const char *name, uint32_t fallback)
{
    const char *p = strstr(line, name);
    if (p == NULL) return fallback;
    p += strlen(name);
    return (uint32_t)strtoul(p, NULL, 0);
}

static void run_command(const char *line)
{
    uint32_t mode = field_u32(line, "mode=", UINT32_MAX);
    uint32_t size = field_u32(line, "size=", 0u);
    uint32_t precision = field_u32(line, "precision=", SIT_PRECISION_FP32);
    uint32_t alpha = field_u32(line, "alpha=", 2u);
    bool trace = field_u32(line, "trace=", 1u) != 0u;
    printf("RISCBENCH_RUN_BEGIN\n");
    bool precision_supported = precision == SIT_PRECISION_FP32 || precision == SIT_PRECISION_INT8 ||
        precision == SIT_PRECISION_INT16;
    if (!precision_supported) {
        printf("status=ERROR unsupported_precision\n");
    } else if (mode == 5u) {
        sit_perf_monitor_enable(true);
        int status = riscbench_run_all_with_trace(trace);
        sit_perf_monitor_enable(false);
        sit_perf_t perf;
        sit_perf_collect(&perf);
        sit_perf_print(&perf);
        printf("status=%s\n", status == 0 ? "PASS" : "FAIL");
    } else if (mode > SIT_MODE_SAXPY || size == 0u) {
        printf("status=ERROR invalid_run_parameters\n");
    } else {
        riscbench_set_precision(precision);
        sit_perf_monitor_enable(true);
        int status;
        if (precision == SIT_PRECISION_INT16 || precision == SIT_PRECISION_INT8) {
            riscbench_chunked_result_t performance = {0}, trace_result = {0};
            status = mode == SIT_MODE_VECADD ?
                riscbench_run_vecadd_modes(size, trace, &performance, &trace_result) :
                mode == SIT_MODE_VECMUL ?
                riscbench_run_vecmul_modes(size, trace, &performance, &trace_result) :
                mode == SIT_MODE_SAXPY ?
                riscbench_run_saxpy_modes(size, alpha, trace, &performance, &trace_result) :
                mode == SIT_MODE_DOT ?
                riscbench_run_dot_modes(size, trace, &performance, &trace_result) :
                riscbench_run_matmul_pattern(size,0u,trace);
        } else {
            status = riscbench_run_one(mode, size, trace);
        }
        sit_perf_monitor_enable(false);
        sit_perf_dump_counter_regs();
        sit_perf_t perf;
        sit_perf_collect(&perf);
        sit_perf_print(&perf);
        printf("status=%s\n", status == 0 ? "PASS" : "FAIL");
    }
    printf("RISCBENCH_RUN_END\n");
    fflush(stdout);
}
#endif

#if !RISCBENCH_AUTORUN
static bool read_command_line(char *line, size_t capacity)
{
    size_t length = 0;
    if (line == NULL || capacity < 2u) return false;

    printf("> ");
    fflush(stdout);
    for (;;) {
        int value = getchar();
        if (value == EOF) {
            clearerr(stdin);
            continue;
        }
        if (value == '\r' || value == '\n') {
            printf("\r\n");
            if (length == 0u) {
                printf("> ");
                fflush(stdout);
                continue;
            }
            line[length] = '\0';
            fflush(stdout);
            return true;
        }
        if (value == '\b' || value == 0x7f) {
            if (length != 0u) {
                --length;
                printf("\b \b");
                fflush(stdout);
            }
            continue;
        }
        if (value >= 0x20 && value <= 0x7e && length + 1u < capacity) {
            line[length++] = (char)value;
            putchar(value);
            fflush(stdout);
        }
    }
}
#endif

int main(void)
{
    /* Ensure machine interrupts (MIE) are enabled for JTAG UART ISR */
    __asm__ volatile ("csrs mstatus, %0" :: "r"(0x00000008u));
    direct_jtag_uart_puts("RISCBENCH_BOOT_OK\n");
    printf("RISCBENCH_BOOT_OK\n");
    fflush(stdout);
#if RISCBENCH_AUTORUN
    volatile riscbench_result_t *result =
        (volatile riscbench_result_t *)(uintptr_t)RISCBENCH_MAILBOX_ADDR;
    result->magic = 0u;
    __asm__ volatile ("fence rw, rw" ::: "memory");
    riscbench_debug_progress(RISCBENCH_PROGRESS_MAIN);
    usleep(RISCBENCH_AUTORUN_DELAY_US);
    riscbench_set_quiet(true);
    riscbench_set_precision(RISCBENCH_PRECISION);
    riscbench_debug_progress(RISCBENCH_PROGRESS_CONFIG);
    sit_perf_monitor_enable(true);
    uint32_t mon_enable_rb = sit_perf_read_reg(SIT_MONITOR_CTRL_OFFSET);
    char buf[128];
    snprintf(buf, sizeof(buf), "DEBUG_MONITOR_ENABLE=%" PRIu32 "\n", mon_enable_rb);
    printf("%s", buf);
    direct_jtag_uart_puts(buf);
    fflush(stdout);
    riscbench_chunked_result_t performance = {0}, trace_result = {0};
    int run_status;
    bool is_chunked = (RISCBENCH_PRECISION == SIT_PRECISION_INT8 || RISCBENCH_PRECISION == SIT_PRECISION_INT16);

    if (is_chunked && RISCBENCH_MODE == SIT_MODE_MATMUL && RISCBENCH_SIZE != 0u) {
        run_status = riscbench_run_matmul_modes(
            RISCBENCH_SIZE, RISCBENCH_MATMUL_PATTERN,
            RISCBENCH_TRACE != 0u, &performance, &trace_result);
    } else if (is_chunked &&
        (RISCBENCH_MODE == SIT_MODE_VECADD || RISCBENCH_MODE == SIT_MODE_VECMUL ||
         RISCBENCH_MODE == SIT_MODE_DOT || RISCBENCH_MODE == SIT_MODE_SAXPY) &&
        RISCBENCH_SIZE != 0u) {
        run_status = RISCBENCH_MODE == SIT_MODE_VECADD
            ? riscbench_run_vecadd_modes(RISCBENCH_SIZE, RISCBENCH_TRACE != 0u,
                                         &performance, &trace_result)
            : RISCBENCH_MODE == SIT_MODE_VECMUL
              ? riscbench_run_vecmul_modes(RISCBENCH_SIZE, RISCBENCH_TRACE != 0u,
                                           &performance, &trace_result)
              : RISCBENCH_MODE == SIT_MODE_SAXPY
                ? riscbench_run_saxpy_modes(RISCBENCH_SIZE, RISCBENCH_ALPHA_BITS,
                                          RISCBENCH_TRACE != 0u,
                                          &performance, &trace_result)
                : riscbench_run_dot_modes(RISCBENCH_SIZE, RISCBENCH_TRACE != 0u,
                                          &performance, &trace_result);
    } else {
        int one_status = (RISCBENCH_MODE <= SIT_MODE_SAXPY && RISCBENCH_SIZE != 0u)
            ? (RISCBENCH_MODE == SIT_MODE_MATMUL
                ? riscbench_run_matmul_pattern(RISCBENCH_SIZE,
                      RISCBENCH_MATMUL_PATTERN, RISCBENCH_TRACE != 0u)
                : riscbench_run_one(RISCBENCH_MODE, RISCBENCH_SIZE,
                                    RISCBENCH_TRACE != 0u)) : 1;
        run_status = one_status;
    }
    sit_counters_t counters = sit_get_counters();
    result->status = (uint32_t)run_status;
    result->mode = RISCBENCH_MODE;
    result->size = RISCBENCH_SIZE;
    result->total_cycles = is_chunked ? performance.total_cycles : counters.total_cycles;
    result->active_cycles = is_chunked ? performance.active_cycles : counters.active_cycles;
    result->stall_cycles = is_chunked ? performance.stall_cycles : counters.stall_cycles;
    result->mem_wait_cycles = is_chunked ? performance.mem_wait_cycles : counters.mem_wait_cycles;
    result->ops_done = is_chunked ? performance.ops_done : counters.ops_done;
    result->trace_count = is_chunked ? trace_result.trace_count : (RISCBENCH_TRACE ? sit_trace_count() : 0u);
    riscbench_debug_progress(RISCBENCH_PROGRESS_FILLED);
    __asm__ volatile ("fence rw, rw" ::: "memory");
    result->magic = run_status == 0 ? RISCBENCH_MAILBOX_MAGIC :
                                     RISCBENCH_MAILBOX_FAILURE_MAGIC;
    __asm__ volatile ("fence rw, rw" ::: "memory");

    snprintf(buf, sizeof(buf), "RUN_RETURN=%d\n", run_status);
    direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "FINAL_STATUS=%" PRIu32 "\n", result->status);
    direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "FINAL_MAGIC=%s\n", result->magic == RISCBENCH_MAILBOX_MAGIC ? "RBST" : "RBFA");
    direct_jtag_uart_puts(buf); printf("%s", buf);
    fflush(stdout);

    sit_perf_monitor_enable(false);
    sit_perf_dump_counter_regs();
    uint32_t total_lo   = sit_perf_read_reg(SIT_TOTAL_CYCLES_LO_OFFSET);
    uint32_t total_hi   = sit_perf_read_reg(SIT_TOTAL_CYCLES_HI_OFFSET);
    uint32_t active_lo  = sit_perf_read_reg(SIT_ACTIVE_CYCLES_LO_OFFSET);
    uint32_t active_hi  = sit_perf_read_reg(SIT_ACTIVE_CYCLES_HI_OFFSET);
    uint32_t memwait_lo = sit_perf_read_reg(SIT_MEM_WAIT_CYCLES_LO_OFFSET);
    uint32_t memwait_hi = sit_perf_read_reg(SIT_MEM_WAIT_CYCLES_HI_OFFSET);
    uint32_t ops_lo     = sit_perf_read_reg(SIT_OPS_COMPLETED_LO_OFFSET);
    uint32_t ops_hi     = sit_perf_read_reg(SIT_OPS_COMPLETED_HI_OFFSET);

    snprintf(buf, sizeof(buf), "DEBUG_TOTAL_LO=%" PRIu32 "\n", total_lo); direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "DEBUG_TOTAL_HI=%" PRIu32 "\n", total_hi); direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "DEBUG_ACTIVE_LO=%" PRIu32 "\n", active_lo); direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "DEBUG_ACTIVE_HI=%" PRIu32 "\n", active_hi); direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "DEBUG_MEMWAIT_LO=%" PRIu32 "\n", memwait_lo); direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "DEBUG_MEMWAIT_HI=%" PRIu32 "\n", memwait_hi); direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "DEBUG_OPS_LO=%" PRIu32 "\n", ops_lo); direct_jtag_uart_puts(buf); printf("%s", buf);
    snprintf(buf, sizeof(buf), "DEBUG_OPS_HI=%" PRIu32 "\n", ops_hi); direct_jtag_uart_puts(buf); printf("%s", buf);
    fflush(stdout);

    sit_perf_t perf;
    sit_perf_collect(&perf);
    sit_perf_print(&perf);
    direct_jtag_uart_puts("RISCBENCH_RUN_END\n");
    printf("RISCBENCH_RUN_END\n");
    fflush(stdout);
    for (;;) usleep(1000000u);
#else
    char line[160];
    printf("RISCBENCH_READY\n");
    fflush(stdout);
    while (read_command_line(line, sizeof(line))) {
        if (strncmp(line, "HELP", 4) == 0)
            printf("commands=HELP INFO RUN mode=<0..5> size=<N> precision=4 trace=<0|1> RESET\n");
        else if (strncmp(line, "INFO", 4) == 0)
            print_info();
        else if (strncmp(line, "RUN ", 4) == 0)
            run_command(line);
        else if (strncmp(line, "RESET", 5) == 0)
            printf("RISCBENCH_RESET_OK\n");
        else
            printf("RISCBENCH_ERROR unknown_command\n");
        fflush(stdout);
    }
#endif
    return 0;
}

