#include <inttypes.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "sit/sit.h"
#include "sit/sit_regs.h"
#include "tests/riscbench_debug.h"
#include "tests/riscbench_runner.h"
#include "workloads/fp32_ref.h"
#include "sys/alt_cache.h"
#include "system.h"

#define DDR_RESERVED_BYTES  UINT64_C(0x01000000)
#define DDR_ALIGNMENT       UINT64_C(0x00001000)
#define SIT_TIMEOUT_POLLS   UINT32_MAX
#define MATMUL_FULL_LIMIT   256u
#define TRACE_ARCHIVE_ADDR  UINT32_C(0x00c00000)
#define TRACE_ARCHIVE_MAGIC UINT32_C(0x43484e4b)
#define TRACE_CHUNK_STRIDE  UINT32_C(0x00000900)
#define TRACE_CHUNK_BASE    UINT32_C(0x00000100)
#define MATMUL_TRACE_ARCHIVE_VERSION 3u
#define MATMUL_TRACE_UNIT_SIZE 16u
#define MATMUL_TRACE_RUNS 8u
#define MATMUL_TRACE_RECORD_WORDS 32u
#define VECTOR_CHUNK_WORDS  1024u
#define INT16_CHUNK_ELEMENTS (2u * VECTOR_CHUNK_WORDS)
#define INT8_CHUNK_ELEMENTS  (4u * VECTOR_CHUNK_WORDS)

static const uint32_t vector_sizes[] = {
    1024u, 2048u, 4096u, 8192u, 16384u, 32768u,
    65536u, 131072u, 262144u, 524288u, 1048576u
};
static const uint32_t matmul_sizes[] = {
    256u, 512u, 1024u, 2048u, 4096u, 6144u, 8192u
};
static bool quiet_output;
static uint32_t active_precision = SIT_PRECISION_FP32;
static inline void memory_barrier(void);

void riscbench_debug_write(uint32_t address, uint32_t value)
{
    volatile uint32_t *word = (volatile uint32_t *)(uintptr_t)address;
    *word = value;
    memory_barrier();
}

void riscbench_debug_progress(uint32_t marker)
{
    riscbench_debug_write(RISCBENCH_DEBUG_PROGRESS_ADDR, marker);
}

void riscbench_set_quiet(bool quiet) { quiet_output = quiet; }
void riscbench_set_precision(uint32_t precision) { active_precision = precision; }

static const char *precision_name(void)
{
    switch (active_precision) {
    case SIT_PRECISION_INT8:  return "int8";
    case SIT_PRECISION_INT16: return "int16";
    case SIT_PRECISION_INT32: return "int32";
    case SIT_PRECISION_FP16:  return "fp16";
    case SIT_PRECISION_FP32:  return "fp32";
    default:                  return "unsupported";
    }
}

typedef union { uint32_t bits; float value; } fp32_t;
typedef struct {
    uint32_t a, b, c;
    uint64_t bytes_per_matrix;
} ddr_layout_t;

static inline uint64_t align_up(uint64_t value)
{
    return (value + DDR_ALIGNMENT - 1u) & ~(DDR_ALIGNMENT - 1u);
}

static bool make_layout(uint64_t words_per_matrix, ddr_layout_t *layout)
{
    uint64_t bytes = words_per_matrix * sizeof(uint32_t);
    uint64_t a = align_up(DDR_RESERVED_BYTES);
    uint64_t b = align_up(a + bytes);
    uint64_t c = align_up(b + bytes);
    uint64_t end = c + bytes;
    uint64_t ddr_end = (uint64_t)EMIF_IO96B_DDR4COMP_0_BASE +
                       (uint64_t)EMIF_IO96B_DDR4COMP_0_SPAN;

    if (words_per_matrix == 0u || bytes > UINT32_MAX || end > ddr_end) {
        return false;
    }
    layout->a = (uint32_t)a;
    layout->b = (uint32_t)b;
    layout->c = (uint32_t)c;
    layout->bytes_per_matrix = bytes;
    return true;
}

static inline void memory_barrier(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

static uint32_t fp_bits(float value)
{
    fp32_t number;
    number.value = value;
    return number.bits;
}

static uint32_t varied_value(uint32_t index, uint32_t salt)
{
    static const uint32_t values[] = {
        UINT32_C(0x3f000000), /* 0.5 */
        UINT32_C(0x3f800000), /* 1.0 */
        UINT32_C(0x3fc00000), /* 1.5 */
        UINT32_C(0x40000000), /* 2.0 */
        UINT32_C(0x40400000)  /* 3.0 */
    };
    return values[(index + salt) % (sizeof(values)/sizeof(values[0]))];
}

static int16_t varied_int16(uint32_t index, uint32_t salt)
{
    static const int16_t values[] = {
        -32768, -20000, -257, -3, -1, 0, 1, 2, 127, 256, 20000, 32767
    };
    return values[(index + salt) % (sizeof(values)/sizeof(values[0]))];
}

static uint32_t packed_int16_value(uint32_t logical_index, uint32_t salt,
                                   uint32_t logical_size)
{
    uint16_t lane0 = (uint16_t)varied_int16(logical_index, salt);
    uint16_t lane1 = logical_index + 1u < logical_size ?
        (uint16_t)varied_int16(logical_index + 1u, salt) : 0u;
    return (uint32_t)lane0 | ((uint32_t)lane1 << 16);
}
static int8_t varied_int8(uint32_t index,uint32_t salt){
 static const int8_t v[]={-128,-100,-17,-3,-1,0,1,2,15,37,100,127};
 return v[(index+salt)%(sizeof(v)/sizeof(v[0]))];}
static uint32_t packed_int8_value(uint32_t index,uint32_t salt,uint32_t size){
 uint32_t r=0;for(uint32_t i=0;i<4;i++)if(index+i<size)r|=(uint32_t)(uint8_t)varied_int8(index+i,salt)<<(8*i);return r;}

static bool counters_sane(const sit_counters_t *counters, uint32_t expected_ops)
{
    return counters->total_cycles > 0u &&
           counters->active_cycles <= counters->total_cycles &&
           counters->stall_cycles <= counters->total_cycles &&
           counters->mem_wait_cycles <= counters->total_cycles &&
           counters->ops_done == expected_ops;
}

static void flush_region(uint32_t base, uint64_t bytes, bool writeback)
{
    if (writeback)
        alt_dcache_flush((void *)(uintptr_t)base, (size_t)bytes);
    else
        alt_dcache_flush_no_writeback((void *)(uintptr_t)base, (size_t)bytes);
    memory_barrier();
}

static const char *kernel_name(uint32_t mode)
{
    static const char *const names[] = {"vecadd", "vecmul", "dot", "matmul", "saxpy"};
    return mode <= SIT_MODE_SAXPY ? names[mode] : "unknown";
}

static void print_trace(uint32_t mode, uint32_t size)
{
    if (quiet_output) return;
    uint32_t count = sit_trace_count();
    bool overflow = sit_trace_overflow();
    printf("RISCBENCH_EVENT_TRACE_BEGIN\n");
    printf("kernel=%s\n", kernel_name(mode));
    printf("mode=%" PRIu32 "\n", mode);
    printf("size=%" PRIu32 "\n", size);
    printf("precision=%s\n", precision_name());
    printf("precision_raw=%" PRIu32 "\n", active_precision);
    printf("index,timestamp,event_mask\n");
    for (uint32_t i = 0; i < count; ++i) {
        sit_trace_entry_t entry;
        sit_trace_read(i, &entry);
        printf("%" PRIu32 ",%" PRIu64 ",0x%04" PRIx16 "\n",
               i, entry.timestamp, entry.event_mask);
    }
    printf("trace_count=%" PRIu32 "\n", count);
    printf("trace_overflow=%u\n", overflow ? 1u : 0u);
    printf("trace_complete=%s\n", overflow ? "NO" : "YES");
    printf("RISCBENCH_EVENT_TRACE_END\n");
}

static void print_record(uint32_t mode, uint32_t size, const char *status,
                         const char *method, bool validation,
                         uint64_t bytes_read, uint64_t bytes_written,
                         const sit_counters_t *counters)
{
    if (quiet_output) return;
    printf("RISCBENCH_FPGA_COUNTER_BEGIN\n");
    printf("platform=agilex_niosv\n");
    printf("kernel=%s\n", kernel_name(mode));
    printf("mode=%" PRIu32 "\n", mode);
    printf("size=%" PRIu32 "\n", size);
    printf("status=%s\n", status);
    printf("precision=%s\n", precision_name());
    printf("precision_raw=%" PRIu32 "\n", active_precision);
    printf("bytes_read=%" PRIu64 "\n", bytes_read);
    printf("bytes_written=%" PRIu64 "\n", bytes_written);
    printf("validation=%s\n", validation ? "PASS" : "FAIL");
    printf("validation_method=%s\n", method);
    printf("total_cycles=%" PRIu32 "\n", counters->total_cycles);
    printf("active_cycles=%" PRIu32 "\n", counters->active_cycles);
    printf("stall_cycles=%" PRIu32 "\n", counters->stall_cycles);
    printf("mem_wait_cycles=%" PRIu32 "\n", counters->mem_wait_cycles);
    printf("ops_done=%" PRIu32 "\n", counters->ops_done);
    printf("overflow_count=0\n");
    printf("RISCBENCH_FPGA_COUNTER_END\n");
}

static inline void runner_jtag_uart_putc(char c)
{
    volatile uint32_t *ctrl = (volatile uint32_t *)(uintptr_t)(JTAG_UART_0_BASE + 4);
    volatile uint32_t *data = (volatile uint32_t *)(uintptr_t)JTAG_UART_0_BASE;
    uint32_t timeout = 50000u;
    while (((*ctrl) & 0xFFFF0000u) == 0 && --timeout) {
    }
    if (timeout > 0) {
        *data = (uint32_t)(uint8_t)c;
    }
}

static inline void runner_jtag_uart_puts(const char *s)
{
    while (*s) {
        if (*s == '\n') runner_jtag_uart_putc('\r');
        runner_jtag_uart_putc(*s++);
    }
}

static bool run_vector(uint32_t mode, uint32_t size, bool trace,
                       sit_counters_t *captured_counters)
{
    ddr_layout_t layout;
    sit_counters_t counters = {0};
    bool int16_dot = mode == SIT_MODE_DOT && active_precision == SIT_PRECISION_INT16;
    bool int8_dot = mode == SIT_MODE_DOT && active_precision == SIT_PRECISION_INT8;
    uint32_t input_words = int8_dot?(size+3u)/4u:int16_dot ? (size + 1u) / 2u : size;
    uint64_t bytes_read = (uint64_t)input_words * 8u;
    uint64_t bytes_written = (mode == SIT_MODE_DOT) ? 4u : (uint64_t)size * 4u;
    uint32_t output_words = (mode == SIT_MODE_DOT) ? 1u : size;
    bool valid = false, done;

    if (!make_layout(input_words, &layout)) {
        print_record(mode, size, "SKIP_DDR_RANGE", "FULL", false,
                     bytes_read, bytes_written, &counters);
        return false;
    }

    volatile uint32_t *a = (volatile uint32_t *)(uintptr_t)layout.a;
    volatile uint32_t *b = (volatile uint32_t *)(uintptr_t)layout.b;
    volatile uint32_t *c = (volatile uint32_t *)(uintptr_t)layout.c;
    for (uint32_t i = 0; i < input_words; ++i) {
        a[i] = int8_dot ? packed_int8_value(4u*i,0u,size) : int16_dot ? packed_int16_value(2u * i, 0u, size) :
                           varied_value(i, 0u);
        b[i] = int8_dot ? packed_int8_value(4u*i,2u,size) : int16_dot ? packed_int16_value(2u * i, 2u, size) :
                           varied_value(i, 2u);
        c[i] = 0u;
    }
    riscbench_debug_progress(RISCBENCH_PROGRESS_INPUT);
    flush_region(layout.a, layout.bytes_per_matrix, true);
    flush_region(layout.b, layout.bytes_per_matrix, true);
    flush_region(layout.c, layout.bytes_per_matrix, true);
    riscbench_debug_progress(RISCBENCH_PROGRESS_INPUT_VALID);

    sit_config_t config = {
        .mode = mode, .size = size, .a_base = layout.a,
        .b_base = layout.b, .c_base = layout.c,
        .alpha = fp_bits(2.0f), .precision = active_precision
    };
    sit_configure(&config);
    riscbench_debug_progress(RISCBENCH_PROGRESS_CONFIGURED);
    sit_start();
    riscbench_debug_progress(RISCBENCH_PROGRESS_STARTED);
    done = false;
    for (uint32_t poll = 0; poll < SIT_TIMEOUT_POLLS; ++poll) {
        uint32_t status = sit_read_status();
        if ((poll & UINT32_C(0x0000ffff)) == 0u) {
            riscbench_debug_write(RISCBENCH_DEBUG_STATUS_ADDR, status);
            riscbench_debug_write(RISCBENCH_DEBUG_POLL_ADDR, poll);
        }
        if ((status & SIT_STATUS_DONE) != 0u) {
            riscbench_debug_write(RISCBENCH_DEBUG_STATUS_ADDR, status);
            riscbench_debug_write(RISCBENCH_DEBUG_POLL_ADDR, poll);
            done = true;
            break;
        }
    }
    if (done) riscbench_debug_progress(RISCBENCH_PROGRESS_DONE);
    counters = sit_get_counters();
    if (captured_counters != NULL) *captured_counters = counters;
    riscbench_debug_progress(RISCBENCH_PROGRESS_COUNTERS);

    flush_region(layout.c, (uint64_t)output_words * 4u, false);
    if (done) {
        uint32_t expected;
        valid = true;
        printf("VALIDATION_BEGIN\n");
        runner_jtag_uart_puts("VALIDATION_BEGIN\n");
        fflush(stdout);
        if (mode == SIT_MODE_DOT) {
            if(int8_dot) expected=riscbench_dot_int8_reference((const uint32_t*)a,(const uint32_t*)b,size);
            else if (int16_dot) {
                expected = riscbench_dot_int16_reference(
                    (const uint32_t *)a, (const uint32_t *)b, size);
            } else {
                uint32_t accumulator = 0u;
                for (uint32_t i = 0; i < size; ++i)
                    accumulator = riscbench_fp32_add(accumulator,
                        riscbench_fp32_mul(a[i], b[i]));
                expected = accumulator;
            }
        } else expected = 0u;
        for (uint32_t i = 0; i < output_words; ++i) {
            if (mode == SIT_MODE_VECMUL)
                expected = riscbench_vecmul_reference(a[i], b[i]);
            else if (mode == SIT_MODE_SAXPY)
                expected = riscbench_saxpy_reference(config.alpha, a[i], b[i]);
            else if (mode == SIT_MODE_VECADD)
                expected = riscbench_vecadd_fp32_reference(a[i], b[i]);
            if (c[i] != expected) {
                riscbench_debug_write(RISCBENCH_DEBUG_FAIL_INDEX_ADDR, i);
                riscbench_debug_write(RISCBENCH_DEBUG_EXPECTED_ADDR, expected);
                riscbench_debug_write(RISCBENCH_DEBUG_ACTUAL_ADDR, c[i]);
                char err_buf[160];
                snprintf(err_buf, sizeof(err_buf),
                         "VALIDATION_MISMATCH,index=%" PRIu32 ",expected=0x%08" PRIx32 ",actual=0x%08" PRIx32 "\n",
                         i, expected, c[i]);
                printf("%s", err_buf);
                runner_jtag_uart_puts(err_buf);
                if (!quiet_output)
                    printf("VALIDATION_MISMATCH kernel=%s index=%" PRIu32
                           " expected=%08" PRIx32 " actual=%08" PRIx32 "\n",
                           kernel_name(mode), i, expected, c[i]);
                if (!quiet_output)
                    printf("FAIL_OPERANDS a=%08" PRIx32 " b=%08" PRIx32
                           " alpha=%08" PRIx32 "\n", a[i], b[i], config.alpha);
                valid = false;
                break;
            }
        }
        if (valid) {
            printf("VALIDATION_PASS\n");
            runner_jtag_uart_puts("VALIDATION_PASS\n");
        }
        fflush(stdout);
        valid = valid && counters_sane(&counters, output_words);
    }
    if (done) riscbench_debug_progress(RISCBENCH_PROGRESS_VERIFIED);
    print_record(mode, size, done ? (valid ? "PASS" : "FAIL") : "TIMEOUT",
                 "FULL", valid, bytes_read, bytes_written, &counters);
    if (trace) print_trace(mode, size);
    return done && valid;
}

static bool validate_matmul(volatile uint32_t *a, volatile uint32_t *b,
                            volatile uint32_t *c, uint32_t n)
{
    for (uint32_t row = 0; row < n; ++row)
        for (uint32_t col = 0; col < n; ++col) {
            uint32_t expected = 0u;
            for (uint32_t k = 0; k < n; ++k)
                expected = riscbench_fp32_add(expected,
                    riscbench_fp32_mul(a[(uint64_t)row*n+k],
                                       b[(uint64_t)k*n+col]));
            uint64_t index = (uint64_t)row*n+col;
            if (c[index] != expected) {
                riscbench_debug_write(RISCBENCH_DEBUG_FAIL_INDEX_ADDR, (uint32_t)index);
                riscbench_debug_write(RISCBENCH_DEBUG_EXPECTED_ADDR, expected);
                riscbench_debug_write(RISCBENCH_DEBUG_ACTUAL_ADDR, c[index]);
                if (!quiet_output)
                    printf("VALIDATION_MISMATCH kernel=matmul row=%" PRIu32
                           " col=%" PRIu32 " expected=%08" PRIx32
                           " actual=%08" PRIx32 "\n", row, col, expected, c[index]);
                return false;
            }
        }
    return true;
}

static bool run_matmul(uint32_t n, uint32_t pattern, bool trace,
                       sit_counters_t *captured_counters)
{
    bool int16=active_precision==SIT_PRECISION_INT16;
    bool int8=active_precision==SIT_PRECISION_INT8;
    uint32_t row_words=int8?(n+3u)/4u:(n+1u)/2u;
    uint64_t words = (int16||int8) ? (uint64_t)n*row_words : (uint64_t)n * n;
    uint64_t logical_bytes = words * sizeof(uint32_t);
    ddr_layout_t layout;
    sit_counters_t counters = {0};
    bool done = false, valid = false;

    if (!make_layout(words, &layout)) {
        print_record(SIT_MODE_MATMUL, n, "SKIP_DDR_RANGE",
                     "FULL", false,
                     logical_bytes * 2u, logical_bytes, &counters);
        return false;
    }

    volatile uint32_t *a = (volatile uint32_t *)(uintptr_t)layout.a;
    volatile uint32_t *b = (volatile uint32_t *)(uintptr_t)layout.b;
    volatile uint32_t *c = (volatile uint32_t *)(uintptr_t)layout.c;
    const uint32_t zero = fp_bits(0.0f), one = fp_bits(1.0f);
    if(int8){
      for(uint32_t r=0;r<n;r++)for(uint32_t w=0;w<row_words;w++){
        uint32_t aw=0,bw=0;for(uint32_t lane=0;lane<4;lane++){
          uint32_t k=4u*w+lane;if(k<n){aw|=(uint32_t)(uint8_t)varied_int8(r*n+k,0u)<<(8*lane);
            bw|=(uint32_t)(uint8_t)varied_int8(k*n+r,2u)<<(8*lane);}}
        a[(uint64_t)r*row_words+w]=aw;b[(uint64_t)r*row_words+w]=bw;c[(uint64_t)r*row_words+w]=0;
      }
    } else if(int16) {
      for(uint32_t r=0;r<n;r++) for(uint32_t w=0;w<row_words;w++) {
        uint32_t k=2u*w;
        int16_t a0=varied_int16(r*n+k,0u);
        int16_t a1=k+1u<n?varied_int16(r*n+k+1u,0u):0;
        a[(uint64_t)r*row_words+w]=(uint16_t)a0|((uint32_t)(uint16_t)a1<<16);
        /* B is transposed: packed row r represents logical column r. */
        int16_t b0=varied_int16(k*n+r,2u);
        int16_t b1=k+1u<n?varied_int16((k+1u)*n+r,2u):0;
        b[(uint64_t)r*row_words+w]=(uint16_t)b0|((uint32_t)(uint16_t)b1<<16);
        c[(uint64_t)r*row_words+w]=0u;
      }
    } else
    for (uint32_t r = 0; r < n; ++r) {
        uint64_t row = (uint64_t)r * n;
        for (uint32_t col = 0; col < n; ++col) {
            a[row + col] = pattern == 0u ? ((r == col) ? one : zero) :
                           varied_value(r * 3u + col, 0u);
            b[row + col] = varied_value(row + col, 1u);
            c[row + col] = zero;
        }
    }
    flush_region(layout.a, logical_bytes, true);
    flush_region(layout.b, logical_bytes, true);
    flush_region(layout.c, logical_bytes, true);

    sit_config_t config = {
        .mode = SIT_MODE_MATMUL, .size = n, .a_base = layout.a,
        .b_base = layout.b, .c_base = layout.c, .alpha = 0u,
        .precision = active_precision
    };
    sit_configure(&config);
    sit_start();
    done = sit_wait_done(SIT_TIMEOUT_POLLS);
    counters = sit_get_counters();
    if (captured_counters != NULL) *captured_counters = counters;
    if (done) {
        flush_region(layout.c, logical_bytes, false);
        if(int8){valid=true;
          for(uint32_t r=0;r<n&&valid;r++)for(uint32_t col=0;col<n;col++){
            int64_t sum=0;for(uint32_t k=0;k<n;k++)sum+=(int32_t)varied_int8(r*n+k,0u)*(int32_t)varied_int8(k*n+col,2u);
            int8_t expected=sum>127?127:sum< -128?-128:(int8_t)sum;
            uint32_t word=c[(uint64_t)r*row_words+(col>>2)];int8_t actual=(int8_t)(word>>(8*(col&3u)));
            if(actual!=expected)valid=false;
          }
          if((n&3u)&&valid)for(uint32_t r=0;r<n;r++)
            if(c[(uint64_t)r*row_words+row_words-1u]>>(8*(n&3u)))valid=false;
        } else if(int16) { valid=true;
          for(uint32_t r=0;r<n&&valid;r++) for(uint32_t col=0;col<n;col++) {
            int64_t sum=0; for(uint32_t k=0;k<n;k++)
              sum+=(int32_t)varied_int16(r*n+k,0u)*(int32_t)varied_int16(k*n+col,2u);
            int16_t expected=sum>32767?32767:sum< -32768?-32768:(int16_t)sum;
            uint32_t word=c[(uint64_t)r*row_words+(col>>1)];
            int16_t actual=(col&1u)?(int16_t)(word>>16):(int16_t)word;
            if(actual!=expected) valid=false;
          }
          if((n&1u)&&valid) for(uint32_t r=0;r<n;r++)
            if(c[(uint64_t)r*row_words+row_words-1u]>>16) valid=false;
        } else valid = validate_matmul(a, b, c, n);
        valid = valid && counters_sane(&counters, n * n);
    }
    print_record(SIT_MODE_MATMUL, n,
                 done ? (valid ? "PASS" : "FAIL") : "TIMEOUT",
                  "FULL", valid,
                 logical_bytes * 2u, logical_bytes, &counters);
    if (trace) print_trace(SIT_MODE_MATMUL, n);
    return done && valid;
}

static void copy_counters(riscbench_chunked_result_t *result,
                          const sit_counters_t *counters)
{
    result->total_cycles = counters->total_cycles;
    result->active_cycles = counters->active_cycles;
    result->stall_cycles = counters->stall_cycles;
    result->mem_wait_cycles = counters->mem_wait_cycles;
    result->ops_done = counters->ops_done;
    result->chunk_count = 1u;
}

static int run_matmul_stitched_trace(uint32_t pattern,
                                    riscbench_chunked_result_t *performance,
                                    riscbench_chunked_result_t *trace_result)
{
    const uint32_t logical_size = 32u;
    const uint32_t unit_size = MATMUL_TRACE_UNIT_SIZE;
    const uint64_t unit_bytes = (uint64_t)unit_size * unit_size * 4u;
    ddr_layout_t native_layout;
    sit_counters_t native_counters = {0};
    volatile uint32_t *header =
        (volatile uint32_t *)(uintptr_t)TRACE_ARCHIVE_ADDR;
    bool all_valid = true, all_done = true, all_workload_done = true;
    bool all_overflow_zero = true;
    uint32_t trace_events_total = 0u, max_events_per_run = 0u;
    uint32_t stitched_cycles = 0u, run_index = 0u;

    *performance = (riscbench_chunked_result_t){0};
    *trace_result = (riscbench_chunked_result_t){0};
    header[0] = 0u;
    memory_barrier();

    if (!run_matmul(logical_size, pattern, false, &native_counters)) return 1;
    copy_counters(performance, &native_counters);
    if (!make_layout((uint64_t)logical_size * logical_size, &native_layout))
        return 1;

    uint64_t trace_a64 = align_up((uint64_t)native_layout.c +
                                  native_layout.bytes_per_matrix);
    uint64_t trace_b64 = align_up(trace_a64 + unit_bytes);
    uint64_t trace_c64 = align_up(trace_b64 + unit_bytes);
    uint64_t reconstruct64 = align_up(trace_c64 + unit_bytes);
    uint64_t ddr_end = (uint64_t)EMIF_IO96B_DDR4COMP_0_BASE +
                       (uint64_t)EMIF_IO96B_DDR4COMP_0_SPAN;
    if (reconstruct64 + native_layout.bytes_per_matrix > ddr_end) return 1;

    uint32_t trace_a_base = (uint32_t)trace_a64;
    uint32_t trace_b_base = (uint32_t)trace_b64;
    uint32_t trace_c_base = (uint32_t)trace_c64;
    volatile uint32_t *native_a =
        (volatile uint32_t *)(uintptr_t)native_layout.a;
    volatile uint32_t *native_b =
        (volatile uint32_t *)(uintptr_t)native_layout.b;
    volatile uint32_t *native_c =
        (volatile uint32_t *)(uintptr_t)native_layout.c;
    volatile uint32_t *trace_a = (volatile uint32_t *)(uintptr_t)trace_a_base;
    volatile uint32_t *trace_b = (volatile uint32_t *)(uintptr_t)trace_b_base;
    volatile uint32_t *trace_c = (volatile uint32_t *)(uintptr_t)trace_c_base;
    volatile uint32_t *reconstructed =
        (volatile uint32_t *)(uintptr_t)(uint32_t)reconstruct64;

    for (uint32_t index = 0; index < logical_size * logical_size; ++index)
        reconstructed[index] = 0u;

    for (uint32_t i_block = 0; i_block < 2u; ++i_block)
        for (uint32_t j_block = 0; j_block < 2u; ++j_block)
            for (uint32_t k_block = 0; k_block < 2u; ++k_block) {
                uint32_t i_start = i_block * unit_size;
                uint32_t j_start = j_block * unit_size;
                uint32_t k_start = k_block * unit_size;
                volatile uint32_t *record = (volatile uint32_t *)(uintptr_t)
                    (TRACE_ARCHIVE_ADDR + TRACE_CHUNK_BASE +
                     run_index * TRACE_CHUNK_STRIDE);
                sit_counters_t counters = {0};

                for (uint32_t row = 0; row < unit_size; ++row)
                    for (uint32_t column = 0; column < unit_size; ++column) {
                        uint32_t local = row * unit_size + column;
                        trace_a[local] = native_a[(i_start + row) * logical_size +
                                                  k_start + column];
                        trace_b[local] = native_b[(k_start + row) * logical_size +
                                                  j_start + column];
                        trace_c[local] = 0u;
                    }
                flush_region(trace_a_base, unit_bytes, true);
                flush_region(trace_b_base, unit_bytes, true);
                flush_region(trace_c_base, unit_bytes, true);

                sit_trace_clear();
                sit_config_t config = {
                    .mode = SIT_MODE_MATMUL, .size = unit_size,
                    .a_base = trace_a_base, .b_base = trace_b_base,
                    .c_base = trace_c_base, .alpha = 0u,
                    .precision = SIT_PRECISION_FP32
                };
                sit_configure(&config);
                sit_start();
                bool done = sit_wait_done(SIT_TIMEOUT_POLLS);
                counters = sit_get_counters();
                flush_region(trace_c_base, unit_bytes, false);

                bool output_valid = done && validate_matmul(
                    trace_a, trace_b, trace_c, unit_size) &&
                    counters_sane(&counters, unit_size * unit_size);
                uint32_t trace_count = sit_trace_count();
                bool overflow = sit_trace_overflow();
                bool workload_done = false;

                record[0] = run_index;
                record[1] = i_block; record[2] = j_block; record[3] = k_block;
                record[4] = i_start; record[5] = j_start; record[6] = k_start;
                record[7] = unit_size; record[8] = counters.total_cycles;
                record[9] = counters.active_cycles;
                record[10] = counters.stall_cycles;
                record[11] = counters.mem_wait_cycles;
                record[12] = counters.ops_done; record[13] = trace_count;
                record[14] = overflow ? 1u : 0u; record[15] = done ? 1u : 0u;
                record[16] = output_valid ? 1u : 0u;
                for (uint32_t index = 0; index < trace_count && index < 256u;
                     ++index) {
                    sit_trace_entry_t entry;
                    sit_trace_read(index, &entry);
                    uint64_t raw = ((uint64_t)entry.event_mask << 48) |
                                   entry.timestamp;
                    record[MATMUL_TRACE_RECORD_WORDS + 2u * index] =
                        (uint32_t)raw;
                    record[MATMUL_TRACE_RECORD_WORDS + 2u * index + 1u] =
                        (uint32_t)(raw >> 32);
                    if ((entry.event_mask & UINT16_C(0x0800)) != 0u)
                        workload_done = true;
                }
                record[17] = workload_done ? 1u : 0u;

                if (output_valid)
                    for (uint32_t row = 0; row < unit_size; ++row)
                        for (uint32_t column = 0; column < unit_size; ++column) {
                            uint32_t logical = (i_start + row) * logical_size +
                                               j_start + column;
                            uint32_t partial = trace_c[row * unit_size + column];
                            reconstructed[logical] = k_block == 0u ? partial :
                                riscbench_fp32_add(reconstructed[logical], partial);
                        }

                stitched_cycles += counters.total_cycles;
                trace_events_total += trace_count;
                if (trace_count > max_events_per_run)
                    max_events_per_run = trace_count;
                trace_result->total_cycles += counters.total_cycles;
                trace_result->active_cycles += counters.active_cycles;
                trace_result->stall_cycles += counters.stall_cycles;
                trace_result->mem_wait_cycles += counters.mem_wait_cycles;
                trace_result->ops_done += counters.ops_done;
                trace_result->trace_count += trace_count;
                trace_result->chunk_count += 1u;
                trace_result->trace_overflow |= overflow;
                all_done &= done;
                all_valid &= output_valid;
                all_workload_done &= workload_done;
                all_overflow_zero &= !overflow && trace_count < 256u;
                ++run_index;
            }

    bool reconstructed_equal = true;
    for (uint32_t index = 0; index < logical_size * logical_size; ++index)
        if (reconstructed[index] != native_c[index]) {
            reconstructed_equal = false;
            break;
        }

    header[1] = MATMUL_TRACE_ARCHIVE_VERSION;
    header[2] = logical_size; header[3] = run_index;
    header[4] = TRACE_CHUNK_STRIDE; header[5] = unit_size;
    header[6] = stitched_cycles; header[7] = trace_events_total;
    header[8] = max_events_per_run;
    header[9] = all_overflow_zero ? 1u : 0u;
    header[10] = all_workload_done ? 1u : 0u;
    header[11] = all_valid ? 1u : 0u;
    header[12] = reconstructed_equal ? 1u : 2u;
    memory_barrier();
    header[0] = TRACE_ARCHIVE_MAGIC;
    memory_barrier();
    return (run_index == MATMUL_TRACE_RUNS && all_done && all_valid &&
            all_workload_done && all_overflow_zero) ? 0 : 1;
}

int riscbench_run_one(uint32_t mode, uint32_t size, bool trace)
{
    if (mode <= SIT_MODE_DOT || mode == SIT_MODE_SAXPY)
        return run_vector(mode, size, trace, NULL) ? 0 : 1;
    if (mode == SIT_MODE_MATMUL)
        return run_matmul(size, 0u, trace, NULL) ? 0 : 1;
    return 1;
}

static int run_vector_chunks(uint32_t mode, uint32_t alpha,
                             uint32_t total_size,
                             uint32_t chunk_words, bool trace, bool archive,
                             riscbench_chunked_result_t *aggregate)
{
    ddr_layout_t layout;
    uint32_t chunk_count = (total_size + chunk_words - 1u) / chunk_words;
    bool int16 = active_precision == SIT_PRECISION_INT16;
    bool int8 = active_precision == SIT_PRECISION_INT8;
    uint32_t total_words = int8?(total_size+3u)/4u:int16 ? (total_size + 1u) / 2u : total_size;
    uint32_t max_chunk_elements = int8?INT8_CHUNK_ELEMENTS:int16 ? INT16_CHUNK_ELEMENTS : VECTOR_CHUNK_WORDS;
    bool all_valid = true;
    if (aggregate == NULL || chunk_words == 0u || chunk_words > max_chunk_elements ||
        !make_layout(total_words, &layout)) return 1;
    *aggregate = (riscbench_chunked_result_t){0};
    aggregate->chunk_count = chunk_count;

    for (uint32_t chunk = 0, start = 0; chunk < chunk_count; ++chunk) {
        uint32_t chunk_size = total_size - start;
        if (chunk_size > chunk_words) chunk_size = chunk_words;
        uint32_t physical_words = int8?(chunk_size+3u)/4u:int16 ? (chunk_size + 1u) / 2u : chunk_size;
        uint32_t byte_offset = (int8?start/4u:int16 ? start / 2u : start) * sizeof(uint32_t);
        volatile uint32_t *a = (volatile uint32_t *)(uintptr_t)(layout.a + byte_offset);
        volatile uint32_t *b = (volatile uint32_t *)(uintptr_t)(layout.b + byte_offset);
        volatile uint32_t *c = (volatile uint32_t *)(uintptr_t)(layout.c + byte_offset);
        volatile uint32_t *record = (volatile uint32_t *)(uintptr_t)
            (TRACE_ARCHIVE_ADDR + TRACE_CHUNK_BASE + chunk * TRACE_CHUNK_STRIDE);
        bool done = false, valid = true;
        sit_counters_t counters;

        for (uint32_t i = 0; i < physical_words; ++i) {
            a[i] = int8?packed_int8_value(start+4u*i,0u,total_size):int16 ? packed_int16_value(start + 2u*i, 0u, total_size) :
                           varied_value(start + i, 0u);
            b[i] = int8?packed_int8_value(start+4u*i,2u,total_size):int16 ? packed_int16_value(start + 2u*i, 2u, total_size) :
                           varied_value(start + i, 2u);
            c[i] = 0u;
        }
        flush_region(layout.a + byte_offset, (uint64_t)physical_words * 4u, true);
        flush_region(layout.b + byte_offset, (uint64_t)physical_words * 4u, true);
        flush_region(layout.c + byte_offset, (uint64_t)physical_words * 4u, true);
        sit_trace_clear();
        sit_config_t config = {
            .mode = mode, .size = chunk_size,
            .a_base = layout.a + byte_offset, .b_base = layout.b + byte_offset,
            .c_base = layout.c + byte_offset, .alpha = alpha,
            .precision = active_precision
        };
        sit_configure(&config);
        sit_start();
        done = sit_wait_done(SIT_TIMEOUT_POLLS);
        counters = sit_get_counters();
        flush_region(layout.c + byte_offset, (uint64_t)physical_words * 4u, false);
        if (done) {
            uint32_t verify_words = mode == SIT_MODE_DOT ? 1u : physical_words;
            for (uint32_t i = 0; i < verify_words; ++i) {
                uint32_t expected;
                if (mode == SIT_MODE_VECADD)
                    expected = int8?riscbench_vecadd_int8_reference(a[i],b[i],chunk_size-4u*i>=4?4:chunk_size-4u*i):int16 ? riscbench_vecadd_int16_reference(
                        a[i], b[i], 2u*i + 1u < chunk_size) :
                        riscbench_vecadd_fp32_reference(a[i], b[i]);
                else if (mode == SIT_MODE_VECMUL)
                    expected = int8?riscbench_vecmul_int8_reference(a[i],b[i],chunk_size-4u*i>=4?4:chunk_size-4u*i):int16 ? riscbench_vecmul_int16_reference(
                        a[i], b[i], 2u*i + 1u < chunk_size) :
                        riscbench_vecmul_reference(a[i], b[i]);
                else if (mode == SIT_MODE_SAXPY)
                    expected = int8?riscbench_saxpy_int8_reference((int8_t)alpha,a[i],b[i],chunk_size-4u*i>=4?4:chunk_size-4u*i):int16 ? riscbench_saxpy_int16_reference(
                        (int16_t)alpha,a[i],b[i],2u*i+1u<chunk_size) :
                        riscbench_saxpy_reference(alpha, a[i], b[i]);
                else {
                    if(int8) expected=riscbench_dot_int8_reference((const uint32_t*)a,(const uint32_t*)b,chunk_size);
                    else if(int16) expected=riscbench_dot_int16_reference(
                        (const uint32_t*)a,(const uint32_t*)b,chunk_size);
                    else { expected = 0u;
                      for (uint32_t j = 0; j < chunk_size; ++j)
                        expected = riscbench_fp32_add(expected,riscbench_fp32_mul(a[j],b[j])); }
                }
                if (c[i] != expected) {
                    riscbench_debug_write(RISCBENCH_DEBUG_FAIL_INDEX_ADDR,
                                           start + (int8?4u*i:int16 ? 2u*i : i));
                    riscbench_debug_write(RISCBENCH_DEBUG_EXPECTED_ADDR, expected);
                    riscbench_debug_write(RISCBENCH_DEBUG_ACTUAL_ADDR, c[i]);
                    valid = false;
                    break;
                }
            }
            valid = valid && counters_sane(&counters,
                mode == SIT_MODE_DOT ? 1u : chunk_size);
        } else valid = false;

        uint32_t trace_count = trace ? sit_trace_count() : 0u;
        bool overflow = trace && sit_trace_overflow();
        if (archive) {
            record[0] = chunk; record[1] = start; record[2] = chunk_size;
            record[3] = counters.total_cycles; record[4] = counters.active_cycles;
            record[5] = counters.stall_cycles; record[6] = counters.mem_wait_cycles;
            record[7] = counters.ops_done; record[8] = trace_count;
            record[9] = overflow ? 1u : 0u; record[10] = valid ? 1u : 0u;
            record[11] = done ? 1u : 0u;
            for (uint32_t i = 0; i < trace_count; ++i) {
                sit_trace_entry_t entry;
                sit_trace_read(i, &entry);
                uint64_t raw = ((uint64_t)entry.event_mask << 48) | entry.timestamp;
                record[16u + 2u*i] = (uint32_t)raw;
                record[17u + 2u*i] = (uint32_t)(raw >> 32);
            }
            memory_barrier();
        }
        aggregate->total_cycles += counters.total_cycles;
        aggregate->active_cycles += counters.active_cycles;
        aggregate->stall_cycles += counters.stall_cycles;
        aggregate->mem_wait_cycles += counters.mem_wait_cycles;
        aggregate->ops_done += counters.ops_done;
        aggregate->trace_count += trace_count;
        aggregate->trace_overflow = aggregate->trace_overflow || overflow;
        all_valid = all_valid && valid;
        start += chunk_size;
    }
    return all_valid ? 0 : 1;
}

static int run_vector_modes(uint32_t mode, uint32_t alpha,
                            uint32_t total_size, bool trace,
                            riscbench_chunked_result_t *performance,
                            riscbench_chunked_result_t *trace_result)
{
    static const uint32_t candidates[] = {512u, 256u, 128u, 64u};
    volatile uint32_t *header = (volatile uint32_t *)(uintptr_t)TRACE_ARCHIVE_ADDR;
    riscbench_chunked_result_t probe;
    uint32_t selected = 0u;
    uint32_t performance_chunk = active_precision==SIT_PRECISION_INT8?INT8_CHUNK_ELEMENTS:
      active_precision == SIT_PRECISION_INT16 ? INT16_CHUNK_ELEMENTS : VECTOR_CHUNK_WORDS;
    int status = run_vector_chunks(mode, alpha, total_size, performance_chunk,
                                   false, false, performance);
    if (status != 0 || !trace) return status;
    header[0] = 0u;
    header[1] = 2u; header[2] = total_size; header[4] = TRACE_CHUNK_STRIDE;
    header[5] = performance_chunk; header[7] = 0u;
    for (uint32_t i = 0; i < 4u; ++i) {
        uint32_t probe_size = total_size < candidates[i] ? total_size : candidates[i];
        int probe_status = run_vector_chunks(mode, alpha, probe_size, candidates[i],
                                             true, false, &probe);
        header[8u+i] = candidates[i];
        header[12u+i] = probe.trace_count;
        header[16u+i] = probe.trace_overflow ? 1u : 0u;
        if (selected == 0u && probe_status == 0 && !probe.trace_overflow)
            selected = candidates[i];
    }
    header[6] = selected;
    if (selected == 0u) {
        header[7] = 1u; header[3] = 0u; header[0] = TRACE_ARCHIVE_MAGIC;
        memory_barrier();
        return 2;
    }
    status = run_vector_chunks(mode, alpha, total_size, selected, true, true, trace_result);
    header[3] = trace_result->chunk_count;
    header[20] = trace_result->total_cycles;
    header[21] = trace_result->ops_done;
    header[22] = trace_result->trace_overflow ? 1u : 0u;
    header[0] = TRACE_ARCHIVE_MAGIC;
    memory_barrier();
    return status;
}

int riscbench_run_vecadd_modes(uint32_t total_size, bool trace,
                              riscbench_chunked_result_t *performance,
                              riscbench_chunked_result_t *trace_result)
{
    return run_vector_modes(SIT_MODE_VECADD, 0u, total_size, trace,
                            performance, trace_result);
}

int riscbench_run_vecmul_modes(uint32_t total_size, bool trace,
                              riscbench_chunked_result_t *performance,
                              riscbench_chunked_result_t *trace_result)
{
    return run_vector_modes(SIT_MODE_VECMUL, 0u, total_size, trace,
                            performance, trace_result);
}

int riscbench_run_saxpy_modes(uint32_t total_size, uint32_t alpha, bool trace,
                             riscbench_chunked_result_t *performance,
                             riscbench_chunked_result_t *trace_result)
{
    return run_vector_modes(SIT_MODE_SAXPY, alpha, total_size, trace,
                            performance, trace_result);
}

int riscbench_run_dot_modes(uint32_t total_size, bool trace,
                           riscbench_chunked_result_t *performance,
                           riscbench_chunked_result_t *trace_result)
{
    static const uint32_t candidates[] = {512u, 256u, 128u, 64u};
    volatile uint32_t *header = (volatile uint32_t *)(uintptr_t)TRACE_ARCHIVE_ADDR;
    riscbench_chunked_result_t probe;
    sit_counters_t counters = {0};
    uint32_t selected = 0u;
    if (performance == NULL || trace_result == NULL) return 1;
    *performance = (riscbench_chunked_result_t){0};
    if (!run_vector(SIT_MODE_DOT, total_size, false, &counters)) return 1;
    performance->total_cycles = counters.total_cycles;
    performance->active_cycles = counters.active_cycles;
    performance->stall_cycles = counters.stall_cycles;
    performance->mem_wait_cycles = counters.mem_wait_cycles;
    performance->ops_done = counters.ops_done;
    performance->chunk_count = 1u;
    if (!trace) return 0;
    header[0] = 0u;
    header[1] = 2u; header[2] = total_size; header[4] = TRACE_CHUNK_STRIDE;
    header[5] = VECTOR_CHUNK_WORDS; header[7] = 0u;
    for (uint32_t i = 0; i < 4u; ++i) {
        uint32_t probe_size = total_size < candidates[i] ? total_size : candidates[i];
        int probe_status = run_vector_chunks(SIT_MODE_DOT, 0u, probe_size,
                                             candidates[i], true, false, &probe);
        header[8u+i] = candidates[i];
        header[12u+i] = probe.trace_count;
        header[16u+i] = probe.trace_overflow ? 1u : 0u;
        if (selected == 0u && probe_status == 0 && !probe.trace_overflow)
            selected = candidates[i];
    }
    header[6] = selected;
    if (selected == 0u) {
        header[7] = 1u; header[3] = 0u; header[0] = TRACE_ARCHIVE_MAGIC;
        memory_barrier(); return 2;
    }
    int status = run_vector_chunks(SIT_MODE_DOT, 0u, total_size, selected,
                                   true, true, trace_result);
    header[3] = trace_result->chunk_count;
    header[20] = trace_result->total_cycles;
    header[21] = trace_result->ops_done;
    header[22] = trace_result->trace_overflow ? 1u : 0u;
    header[0] = TRACE_ARCHIVE_MAGIC;
    memory_barrier();
    return status;
}

int riscbench_run_matmul_pattern(uint32_t n, uint32_t pattern, bool trace)
{
    riscbench_chunked_result_t performance = {0}, trace_result = {0};
    return riscbench_run_matmul_modes(n, pattern, trace,
                                     &performance, &trace_result);
}

int riscbench_run_matmul_modes(uint32_t n, uint32_t pattern, bool trace,
                               riscbench_chunked_result_t *performance,
                               riscbench_chunked_result_t *trace_result)
{
    sit_counters_t counters = {0};
    if (performance == NULL || trace_result == NULL) return 1;
    *performance = (riscbench_chunked_result_t){0};
    *trace_result = (riscbench_chunked_result_t){0};
    if (trace && n == 32u && active_precision == SIT_PRECISION_FP32)
        return run_matmul_stitched_trace(pattern, performance, trace_result);
    bool valid = run_matmul(n, pattern, trace, &counters);
    copy_counters(performance, &counters);
    if (trace) {
        trace_result->trace_count = sit_trace_count();
        trace_result->trace_overflow = sit_trace_overflow();
        trace_result->chunk_count = 1u;
    }
    return valid ? 0 : 1;
}

int riscbench_run_all_with_trace(bool trace)
{
    bool passed = true;
    const uint32_t vector_modes[] = {
        SIT_MODE_VECADD, SIT_MODE_VECMUL, SIT_MODE_DOT, SIT_MODE_SAXPY
    };
    for (size_t m = 0; m < sizeof(vector_modes)/sizeof(vector_modes[0]); ++m)
        for (size_t s = 0; s < sizeof(vector_sizes)/sizeof(vector_sizes[0]); ++s)
            if (!run_vector(vector_modes[m], vector_sizes[s], trace, NULL)) passed = false;
    for (size_t s = 0; s < sizeof(matmul_sizes)/sizeof(matmul_sizes[0]); ++s)
        if (!run_matmul(matmul_sizes[s], 0u, trace, NULL)) passed = false;
    return passed ? 0 : 1;
}

int riscbench_run_all(void)
{
    return riscbench_run_all_with_trace(true);
}
