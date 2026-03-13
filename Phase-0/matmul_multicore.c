// SPDX-License-Identifier: Apache-2.0
// Workload: DRAM -> input circular buffer -> compute -> output circular buffer -> DRAM
// Emits raw residency timeline trace events with flags for bottleneck detection.
//
// Build:
//   gcc -O2 -g -pthread matmul.c -o matmul
//
// Run (balanced):
//   ./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 \
//            --trace results/balanced.trace
//
// Run (force UNDERFLOW: slow reader):
//   ./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 --reader-sleep-ns 2000 \
//            --trace results/underflow.trace
//
// Run (force OVERFLOW: slow writer):
//   ./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 --writer-sleep-ns 5000 \
//            --trace results/overflow.trace
//
// Trace format: ts_us=<timestamp> thread=<tid> event=<EVENT> [flags=<FLAGS>] [key=value ...]
// Events: THREAD_START, THREAD_END, COMPUTE_WORK, INPUT_UNDERFLOW_DETECTED, OUTPUT_OVERFLOW_DETECTED

#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <sched.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static inline void ns_sleep(long ns) {
    if (ns <= 0) return;
    struct timespec ts;
    ts.tv_sec = ns / 1000000000L;
    ts.tv_nsec = ns % 1000000000L;
    nanosleep(&ts, NULL);
}

static inline uint64_t now_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000ULL + (uint64_t)(ts.tv_nsec / 1000ULL);
}

// ------------ ring buffer (SPSC) ------------
// Single-producer single-consumer ring (lock-free with atomics).
// Used for:
//  - input ring: reader -> compute (tile payloads)
//  - output ring: compute -> writer (one float per tile)
typedef struct {
    uint8_t* buf;         // capacity * item_bytes
    size_t capacity;      // number of items
    size_t item_bytes;    // bytes per item
    _Atomic size_t head;  // consumer index
    _Atomic size_t tail;  // producer index
} ring_t;

static int ring_init(ring_t* r, size_t capacity, size_t item_bytes) {
    r->capacity = capacity;
    r->item_bytes = item_bytes;
    atomic_store(&r->head, 0);
    atomic_store(&r->tail, 0);

    size_t bytes = capacity * item_bytes;
    size_t align = 64;
    size_t padded = (bytes + align - 1) & ~(align - 1);

    r->buf = (uint8_t*)aligned_alloc(align, padded);
    if (!r->buf) return -1;
    memset(r->buf, 0, padded);
    return 0;
}

static void ring_free(ring_t* r) {
    free(r->buf);
    r->buf = NULL;
}

static inline uint8_t* ring_slot(ring_t* r, size_t idx) {
    return r->buf + (idx % r->capacity) * r->item_bytes;
}

// full if (tail - head) >= capacity
static inline bool ring_full(const ring_t* r, size_t head, size_t tail) {
    return (tail - head) >= r->capacity;
}

static inline bool ring_empty(size_t head, size_t tail) {
    return head == tail;
}

// ------------ workload types ------------

typedef enum {
    WORKLOAD_MAC,         // Multiply-accumulate (default) - compute + memory mix
    WORKLOAD_ALU,         // Pure ALU operations (add, multiply, shift)
    WORKLOAD_BRANCH,      // Branch-heavy (if/else, loop control)
    WORKLOAD_DRAM_READ,   // Memory read-heavy
    WORKLOAD_DRAM_WRITE   // Memory write-heavy
} workload_type_t;

// ------------ workload context -----------

typedef struct {
    // "DRAM" arrays
    float* A;  // tiles * tile_elems
    float* B;  // tile_elems (reused)
    float* C;  // tiles outputs (one float per tile)
    float* D;  // auxiliary array for DRAM workloads

    size_t tile_elems;   // elements per tile (default 1024 = 32x32)
    size_t total_tiles;  // number of tiles to process

    workload_type_t workload_type;  // which workload to run

    ring_t in_ring;      // input CB (tile payloads)
    ring_t out_ring;     // output CB (one float per tile)

    long reader_sleep_ns;  // slow reader -> underflow
    long writer_sleep_ns;  // slow writer -> overflow

    _Atomic size_t tiles_read;
    _Atomic size_t tiles_done;
    _Atomic size_t tiles_written;

    _Atomic uint64_t input_underflow;
    _Atomic uint64_t output_overflow;

    _Atomic bool stop;

    // residency trace
    FILE* trace_fp;       // optional raw trace file
    pthread_mutex_t trace_lock;  // serialize trace writes
} ctx_t;

// ------------ reader: DRAM -> input CB ------------

static void* reader_thread(void* arg) {
    ctx_t* c = (ctx_t*)arg;

    for (size_t t = 0; t < c->total_tiles; t++) {
        while (1) {
            size_t head = atomic_load_explicit(&c->in_ring.head, memory_order_acquire);
            size_t tail = atomic_load_explicit(&c->in_ring.tail, memory_order_acquire);

            if (!ring_full(&c->in_ring, head, tail)) {
                uint8_t* dst = ring_slot(&c->in_ring, tail);
                memcpy(dst, (uint8_t*)(c->A + t * c->tile_elems), c->tile_elems * sizeof(float));
                atomic_store_explicit(&c->in_ring.tail, tail + 1, memory_order_release);
                atomic_fetch_add(&c->tiles_read, 1);
                break;
            } else {
                // input CB full: backpressure on reader; not counted as overflow (overflow is output-side)
                sched_yield();
            }
        }

        ns_sleep(c->reader_sleep_ns);
    }

    return NULL;
}

// ------------ trace emission helper ------------

static void emit_trace(ctx_t* c, int thread_id, const char* event, const char* fmt, ...) {
    if (!c->trace_fp) return;

    pthread_mutex_lock(&c->trace_lock);
    uint64_t ts = now_us();
    fprintf(c->trace_fp, "ts_us=%" PRIu64 " thread=%d event=%s ", ts, thread_id, event);
    if (fmt) {
        va_list ap;
        va_start(ap, fmt);
        vfprintf(c->trace_fp, fmt, ap);
        va_end(ap);
    }
    fprintf(c->trace_fp, "\n");
    fflush(c->trace_fp);
    pthread_mutex_unlock(&c->trace_lock);
}

// ------------ compute kernels (different workload types) ------------

// MAC: Multiply-Accumulate (mixed compute + memory)
static inline float kernel_mac(float* in_tile, float* reused_vec, size_t n) {
    float acc = 0.0f;
    for (size_t i = 0; i < n; i++) {
        acc += in_tile[i] * reused_vec[i];
    }
    return acc;
}

// ALU: Pure arithmetic operations (no memory access after load)
static inline float kernel_alu(float* in_tile, size_t n) {
    float acc = 0.0f;
    for (size_t i = 0; i < n; i++) {
        float val = in_tile[i];
        // Pure ALU: add, multiply, shift operations
        val = val + 1.5f;
        val = val * 2.3f;
        val = val - 0.7f;
        acc += val;
    }
    return acc;
}

// BRANCH: Branch-heavy (if/else conditions)
static inline float kernel_branch(float* in_tile, size_t n) {
    float acc = 0.0f;
    for (size_t i = 0; i < n; i++) {
        float val = in_tile[i];
        // High branch prediction misses
        if (val > 0.5f) {
            if (val > 1.5f) {
                acc += val * 2.0f;
            } else {
                acc += val + 1.0f;
            }
        } else {
            if (val < -0.5f) {
                acc += val * -1.5f;
            } else {
                acc += val - 1.0f;
            }
        }
    }
    return acc;
}

// DRAM_READ: Memory read-heavy (extra reads)
static inline float kernel_dram_read(float* in_tile, float* aux_array, size_t n) {
    float acc = 0.0f;
    for (size_t i = 0; i < n; i++) {
        // Extra memory reads from aux_array
        float val = in_tile[i] + aux_array[i] + aux_array[(i+1) % n];
        acc += val;
    }
    return acc;
}

// DRAM_WRITE: Memory write-heavy (extra writes)
static inline float kernel_dram_write(float* in_tile, float* aux_array, size_t n) {
    float acc = 0.0f;
    for (size_t i = 0; i < n; i++) {
        // Extra memory writes to aux_array
        aux_array[i] = in_tile[i] * 2.0f;
        acc += aux_array[i];
    }
    return acc;
}

// ------------ compute: input CB -> compute -> output CB ------------



static void* compute_thread(void* arg) {
    ctx_t* c = (ctx_t*)arg;

    emit_trace(c, 1, "THREAD_START", "");

    // Work until all tiles are done (not a fixed loop for multicore)
    while (1) {
        size_t tiles_done_now = atomic_load_explicit(&c->tiles_done, memory_order_acquire);
        if (tiles_done_now >= c->total_tiles) {
            break;  // All work done
        }

        float* in_tile = NULL;

        // Try to pop input tile (non-blocking check)
        size_t head = atomic_load_explicit(&c->in_ring.head, memory_order_acquire);
        size_t tail = atomic_load_explicit(&c->in_ring.tail, memory_order_acquire);

        if (!ring_empty(head, tail)) {
            in_tile = (float*)ring_slot(&c->in_ring, head);
            // Simple store (not CAS) since this is SPSC-safe for head pointer as consumer
            atomic_store_explicit(&c->in_ring.head, head + 1, memory_order_release);

            // compute (dispatch based on workload type)
            float acc = 0.0f;
            size_t n = c->tile_elems;
            
            switch (c->workload_type) {
                case WORKLOAD_MAC:
                    acc = kernel_mac(in_tile, c->B, n);
                    break;
                case WORKLOAD_ALU:
                    acc = kernel_alu(in_tile, n);
                    break;
                case WORKLOAD_BRANCH:
                    acc = kernel_branch(in_tile, n);
                    break;
                case WORKLOAD_DRAM_READ:
                    acc = kernel_dram_read(in_tile, c->D, n);
                    break;
                case WORKLOAD_DRAM_WRITE:
                    acc = kernel_dram_write(in_tile, c->D, n);
                    break;
            }

            // push output (with backpressure)
            while (1) {
                size_t out_head = atomic_load_explicit(&c->out_ring.head, memory_order_acquire);
                size_t out_tail = atomic_load_explicit(&c->out_ring.tail, memory_order_acquire);

                if (!ring_full(&c->out_ring, out_head, out_tail)) {
                    float* out_slot = (float*)ring_slot(&c->out_ring, out_tail);
                    *out_slot = acc;
                    atomic_store_explicit(&c->out_ring.tail, out_tail + 1, memory_order_release);

                    atomic_fetch_add_explicit(&c->tiles_done, 1, memory_order_relaxed);

                    // emit compute work event
                    size_t done = atomic_load_explicit(&c->tiles_done, memory_order_acquire);
                    emit_trace(c, 1, "COMPUTE_WORK", "tiles_done=%zu uf=%" PRIu64 " of=%" PRIu64,
                              done,
                              atomic_load_explicit(&c->input_underflow, memory_order_acquire),
                              atomic_load_explicit(&c->output_overflow, memory_order_acquire));
                    break;
                } else {
                    // OUTPUT OVERFLOW: compute produced output but output CB is full
                    atomic_fetch_add_explicit(&c->output_overflow, 1, memory_order_relaxed);
                    emit_trace(c, 1, "OUTPUT_OVERFLOW_DETECTED", "of_count=%" PRIu64,
                              atomic_load_explicit(&c->output_overflow, memory_order_acquire));
                    sched_yield();
                }
            }
        } else {
            // INPUT UNDERFLOW: compute wants input but input CB empty
            atomic_fetch_add_explicit(&c->input_underflow, 1, memory_order_relaxed);
            emit_trace(c, 1, "INPUT_UNDERFLOW_DETECTED", "uf_count=%" PRIu64,
                      atomic_load_explicit(&c->input_underflow, memory_order_acquire));
            sched_yield();
        }
    }

    emit_trace(c, 1, "THREAD_END", "");
    return NULL;
}

// ------------ writer: output CB -> DRAM ------------

static void* writer_thread(void* arg) {
    ctx_t* c = (ctx_t*)arg;
    size_t written = 0;

    while (1) {
        size_t head = atomic_load_explicit(&c->out_ring.head, memory_order_acquire);
        size_t tail = atomic_load_explicit(&c->out_ring.tail, memory_order_acquire);

        if (!ring_empty(head, tail)) {
            float* out_item = (float*)ring_slot(&c->out_ring, head);
            c->C[written] = *out_item;
            written++;

            atomic_store_explicit(&c->out_ring.head, head + 1, memory_order_release);
            atomic_fetch_add_explicit(&c->tiles_written, 1, memory_order_relaxed);

            ns_sleep(c->writer_sleep_ns);
        } else {
            // Check if all tiles are done and output ring is empty
            size_t td = atomic_load_explicit(&c->tiles_done, memory_order_acquire);
            size_t tw = atomic_load_explicit(&c->tiles_written, memory_order_acquire);

            if (tw >= td && td >= c->total_tiles) {
                break;  // All done
            }
            sched_yield();
        }
    }
    return NULL;
}

// ------------ CLI / main ------------

static void usage(const char* prog) {
    fprintf(stderr,
        "Usage:\n"
        "  %s --tile-elems N --tiles T --in-depth D --out-depth D2 [OPTIONS]\n\n"
        "Options:\n"
        "  --reader-sleep-ns X      Nanoseconds reader sleeps per tile (inject underflow)\n"
        "  --writer-sleep-ns Y      Nanoseconds writer sleeps per tile (inject overflow)\n"
        "  --trace PATH             Write raw trace events to file\n"
        "  --workload TYPE          Compute workload type (default: mac)\n"
        "                           - mac:        Multiply-accumulate (mixed compute+memory)\n"
        "                           - alu:        Pure ALU operations\n"
        "                           - branch:     Branch-heavy (if/else)\n"
        "                           - dram_read:  Memory read-heavy\n"
        "                           - dram_write: Memory write-heavy\n\n"
        "Examples:\n"
        "  MAC workload balanced:\n"
        "    %s --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 --workload mac\n"
        "  ALU workload with underflow:\n"
        "    %s --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 --workload alu --reader-sleep-ns 2000\n"
        "  DRAM_READ workload with trace:\n"
        "    %s --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 --workload dram_read --trace results/dram_read.trace\n",
        prog, prog, prog, prog);
}

int main(int argc, char** argv) {
    size_t tile_elems = 1024;
    size_t tiles = 50000;
    size_t in_depth = 2;
    size_t out_depth = 2;
    size_t compute_threads = 1;  // NEW: multicore support
    long reader_sleep_ns = 0;
    long writer_sleep_ns = 0;
    const char* trace_path = NULL;
    workload_type_t workload_type = WORKLOAD_MAC;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--tile-elems") && i + 1 < argc) tile_elems = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--tiles") && i + 1 < argc) tiles = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--compute-threads") && i + 1 < argc) compute_threads = (size_t)strtoull(argv[++i], NULL, 10);  // NEW
        else if (!strcmp(argv[i], "--in-depth") && i + 1 < argc) in_depth = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--out-depth") && i + 1 < argc) out_depth = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--reader-sleep-ns") && i + 1 < argc) reader_sleep_ns = strtol(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--writer-sleep-ns") && i + 1 < argc) writer_sleep_ns = strtol(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--trace") && i + 1 < argc) trace_path = argv[++i];
        else if (!strcmp(argv[i], "--workload") && i + 1 < argc) {
            const char* wl = argv[++i];
            if (!strcmp(wl, "mac")) workload_type = WORKLOAD_MAC;
            else if (!strcmp(wl, "alu")) workload_type = WORKLOAD_ALU;
            else if (!strcmp(wl, "branch")) workload_type = WORKLOAD_BRANCH;
            else if (!strcmp(wl, "dram_read")) workload_type = WORKLOAD_DRAM_READ;
            else if (!strcmp(wl, "dram_write")) workload_type = WORKLOAD_DRAM_WRITE;
            else {
                fprintf(stderr, "Unknown workload type: %s\n", wl);
                usage(argv[0]);
                return 2;
            }
        }
        else {
            usage(argv[0]);
            return 2;
        }
    }

    ctx_t c;
    memset(&c, 0, sizeof(c));
    c.tile_elems = tile_elems;
    c.total_tiles = tiles;
    c.workload_type = workload_type;
    c.reader_sleep_ns = reader_sleep_ns;
    c.writer_sleep_ns = writer_sleep_ns;
    c.trace_fp = NULL;
    atomic_store(&c.stop, false);
    pthread_mutex_init(&c.trace_lock, NULL);

    // Allocate DRAM-like arrays:
    // A: tiles * tile_elems (input)
    // B: tile_elems (reused each tile)
    // C: tiles (one float per tile, output)
    // D: tile_elems (auxiliary for DRAM workloads)
    size_t a_elems = tiles * tile_elems;
    size_t b_elems = tile_elems;
    size_t c_elems = tiles;
    size_t d_elems = tile_elems;

    size_t align = 64;
    size_t a_bytes = ((a_elems * sizeof(float) + align - 1) / align) * align;
    size_t b_bytes = ((b_elems * sizeof(float) + align - 1) / align) * align;
    size_t c_bytes = ((c_elems * sizeof(float) + align - 1) / align) * align;
    size_t d_bytes = ((d_elems * sizeof(float) + align - 1) / align) * align;

    c.A = (float*)aligned_alloc(align, a_bytes);
    c.B = (float*)aligned_alloc(align, b_bytes);
    c.C = (float*)aligned_alloc(align, c_bytes);
    c.D = (float*)aligned_alloc(align, d_bytes);

    if (!c.A || !c.B || !c.C || !c.D) {
        fprintf(stderr, "alloc failed\n");
        return 1;
    }

    for (size_t i = 0; i < a_elems; i++) c.A[i] = (float)((i % 97) * 0.01);
    for (size_t i = 0; i < b_elems; i++) c.B[i] = (float)(((i % 89) + 1) * 0.02);
    for (size_t i = 0; i < d_elems; i++) c.D[i] = (float)(((i % 73) + 1) * 0.03);
    memset(c.C, 0, c_elems * sizeof(float));

    if (ring_init(&c.in_ring, in_depth, tile_elems * sizeof(float)) != 0) {
        fprintf(stderr, "input ring init failed\n");
        return 1;
    }
    if (ring_init(&c.out_ring, out_depth, sizeof(float)) != 0) {
        fprintf(stderr, "output ring init failed\n");
        return 1;
    }

    if (trace_path) {
        c.trace_fp = fopen(trace_path, "w");
        if (!c.trace_fp) {
            perror("fopen trace");
            return 1;
        }
    }

    pthread_t tr, tw;
    pthread_t* tc_arr = (pthread_t*)malloc(compute_threads * sizeof(pthread_t));  // NEW: array of compute threads
    
    if (pthread_create(&tr, NULL, reader_thread, &c) != 0) { perror("pthread_create reader"); return 1; }
    
    // NEW: Create multiple compute threads
    for (size_t i = 0; i < compute_threads; i++) {
        if (pthread_create(&tc_arr[i], NULL, compute_thread, &c) != 0) { 
            perror("pthread_create compute"); 
            return 1; 
        }
    }
    
    if (pthread_create(&tw, NULL, writer_thread, &c) != 0) { perror("pthread_create writer"); return 1; }

    pthread_join(tr, NULL);
    
    // NEW: Join all compute threads
    for (size_t i = 0; i < compute_threads; i++) {
        pthread_join(tc_arr[i], NULL);
    }
    
    pthread_join(tw, NULL);

    uint64_t uf = atomic_load_explicit(&c.input_underflow, memory_order_acquire);
    uint64_t of = atomic_load_explicit(&c.output_overflow, memory_order_acquire);

    // prevent dead-code elimination: checksum some outputs
    double checksum = 0.0;
    size_t lim = (c_elems < 1024 ? c_elems : 1024);
    for (size_t i = 0; i < lim; i++) checksum += c.C[i];

    printf("tiles=%zu tile_elems=%zu compute_threads=%zu in_depth=%zu out_depth=%zu\n", tiles, tile_elems, compute_threads, in_depth, out_depth);
    printf("tiles_read=%zu tiles_done=%zu tiles_written=%zu\n",
           atomic_load_explicit(&c.tiles_read, memory_order_acquire),
           atomic_load_explicit(&c.tiles_done, memory_order_acquire),
           atomic_load_explicit(&c.tiles_written, memory_order_acquire));
    printf("input_underflow=%" PRIu64 " output_overflow=%" PRIu64 "\n", uf, of);
    printf("checksum=%f\n", checksum);

    if (c.trace_fp) fclose(c.trace_fp);
    ring_free(&c.in_ring);
    ring_free(&c.out_ring);
    free(c.A); free(c.B); free(c.C); free(c.D);
    free(tc_arr);  // NEW: free compute thread array
    return 0;
}
