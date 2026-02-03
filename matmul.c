// SPDX-License-Identifier: Apache-2.0
// DRAM -> input CB -> compute -> output CB -> DRAM
// Underflow/Overflow semantic markers for baseline adapters (perf/spike/rtl).

#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <sched.h>
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

// ------------ ring buffer (SPSC) ------------
// Single-producer single-consumer ring (lock-free with atomics)
// We use two separate rings:
//  - input ring: reader -> compute
//  - output ring: compute -> writer

typedef struct {
    uint8_t* buf;         // contiguous storage: capacity * item_bytes
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
    // aligned_alloc requires size multiple of alignment
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

// Returns pointers to slot for producer/consumer
static inline uint8_t* ring_slot(ring_t* r, size_t idx) {
    return r->buf + (idx % r->capacity) * r->item_bytes;
}

// full if (tail - head) == capacity
static inline bool ring_full(ring_t* r, size_t head, size_t tail) {
    return (tail - head) >= r->capacity;
}

// empty if head == tail
static inline bool ring_empty(size_t head, size_t tail) {
    return head == tail;
}

// ------------ workload params ------------

typedef struct {
    // "DRAM" arrays
    float* A;
    float* B;
    float* C;

    size_t tile_elems;     // elements per tile (like 32x32)
    size_t total_tiles;    // how many tiles to process

    ring_t in_ring;
    ring_t out_ring;

    long reader_sleep_ns;  // slow down reader -> causes underflow
    long writer_sleep_ns;  // slow down writer -> causes overflow

    _Atomic size_t tiles_read;
    _Atomic size_t tiles_done;
    _Atomic size_t tiles_written;

    _Atomic uint64_t input_underflow;
    _Atomic uint64_t output_overflow;

    _Atomic bool stop;
} ctx_t;

// ------------ reader thread: DRAM -> input CB ------------

static void* reader_thread(void* arg) {
    ctx_t* c = (ctx_t*)arg;

    for (size_t t = 0; t < c->total_tiles; t++) {
        // wait for free space in input ring
        while (1) {
            size_t head = atomic_load_explicit(&c->in_ring.head, memory_order_acquire);
            size_t tail = atomic_load_explicit(&c->in_ring.tail, memory_order_acquire);
            if (!ring_full(&c->in_ring, head, tail)) {
                // claim slot at tail
                uint8_t* dst = ring_slot(&c->in_ring, tail);
                // copy tile from "DRAM"
                memcpy(dst, (uint8_t*)(c->A + t * c->tile_elems),
                       c->tile_elems * sizeof(float));
                // publish
                atomic_store_explicit(&c->in_ring.tail, tail + 1, memory_order_release);
                atomic_fetch_add(&c->tiles_read, 1);
                break;
            } else {
                // input CB full: reader backpressure (not counted as overflow; overflow is output-side)
                // yield to reduce busy-wait harm
                sched_yield();
            }
        }

        ns_sleep(c->reader_sleep_ns);
    }

    return NULL;
}

// ------------ compute thread: input CB -> compute -> output CB ------------

static void* compute_thread(void* arg) {
    ctx_t* c = (ctx_t*)arg;

    // simple compute: for each tile, do a dot-like MAC against B (same B region reused)
    // This is intentional: creates memory + compute mixture.
    for (size_t t = 0; t < c->total_tiles; t++) {
        // pop from input ring
        float* in_tile = NULL;
        while (1) {
            size_t head = atomic_load_explicit(&c->in_ring.head, memory_order_acquire);
            size_t tail = atomic_load_explicit(&c->in_ring.tail, memory_order_acquire);
            if (!ring_empty(head, tail)) {
                in_tile = (float*)ring_slot(&c->in_ring, head);
                // consume
                atomic_store_explicit(&c->in_ring.head, head + 1, memory_order_release);
                break;
            } else {
                // INPUT UNDERFLOW: compute wants work but input CB empty
                atomic_fetch_add(&c->input_underflow, 1);
                sched_yield();
            }
        }

        // compute into a local tile buffer (avoid writing directly to out ring while computing)
        // keep it stack-friendly by limiting tile size in practice
        size_t n = c->tile_elems;
        float acc = 0.0f;
        // MAC against B slice (reused), and fold into one scalar per tile to keep output small
        // This is "compute" work; you can replace with heavier kernels if needed.
        for (size_t i = 0; i < n; i++) {
            acc += in_tile[i] * c->B[i];
        }

        // push to output ring (one float per tile output)
        while (1) {
            size_t head = atomic_load_explicit(&c->out_ring.head, memory_order_acquire);
            size_t tail = atomic_load_explicit(&c->out_ring.tail, memory_order_acquire);
            if (!ring_full(&c->out_ring, head, tail)) {
                float* out_slot = (float*)ring_slot(&c->out_ring, tail);
                *out_slot = acc;
                atomic_store_explicit(&c->out_ring.tail, tail + 1, memory_order_release);
                atomic_fetch_add(&c->tiles_done, 1);
                break;
            } else {
                // OUTPUT OVERFLOW: compute produced output but output CB is full (writer too slow)
                atomic_fetch_add(&c->output_overflow, 1);
                sched_yield();
            }
        }
    }

    // signal writer to stop once it drains
    atomic_store(&c->stop, true);
    return NULL;
}

// ------------ writer thread: output CB -> DRAM ------------

static void* writer_thread(void* arg) {
    ctx_t* c = (ctx_t*)arg;
    size_t written = 0;

    while (1) {
        size_t head = atomic_load_explicit(&c->out_ring.head, memory_order_acquire);
        size_t tail = atomic_load_explicit(&c->out_ring.tail, memory_order_acquire);

        if (!ring_empty(head, tail)) {
            float* out_tile = (float*)ring_slot(&c->out_ring, head);
            // write to "DRAM" output
            c->C[written] = *out_tile;
            written++;

            atomic_store_explicit(&c->out_ring.head, head + 1, memory_order_release);
            atomic_fetch_add(&c->tiles_written, 1);

            ns_sleep(c->writer_sleep_ns);
        } else {
            if (atomic_load(&c->stop) && atomic_load(&c->tiles_written) >= atomic_load(&c->tiles_done)) {
                break;
            }
            sched_yield();
        }
    }
    return NULL;
}

// ------------ main ------------

static void usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s --tile-elems N --tiles T --in-depth D --out-depth D2 [--reader-sleep-ns X] [--writer-sleep-ns Y]\n"
        "Example (balanced): %s --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2\n"
        "Example (force underflow): %s --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 --reader-sleep-ns 2000\n"
        "Example (force overflow): %s --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 --writer-sleep-ns 5000\n",
        prog, prog, prog, prog);
}

int main(int argc, char** argv) {
    size_t tile_elems = 1024;   // 32x32 default
    size_t tiles = 50000;
    size_t in_depth = 2;
    size_t out_depth = 2;
    long reader_sleep_ns = 0;
    long writer_sleep_ns = 0;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--tile-elems") && i + 1 < argc) tile_elems = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--tiles") && i + 1 < argc) tiles = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--in-depth") && i + 1 < argc) in_depth = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--out-depth") && i + 1 < argc) out_depth = (size_t)strtoull(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--reader-sleep-ns") && i + 1 < argc) reader_sleep_ns = strtol(argv[++i], NULL, 10);
        else if (!strcmp(argv[i], "--writer-sleep-ns") && i + 1 < argc) writer_sleep_ns = strtol(argv[++i], NULL, 10);
        else {
            usage(argv[0]);
            return 2;
        }
    }

    ctx_t c;
    memset(&c, 0, sizeof(c));
    c.tile_elems = tile_elems;
    c.total_tiles = tiles;
    c.reader_sleep_ns = reader_sleep_ns;
    c.writer_sleep_ns = writer_sleep_ns;
    atomic_store(&c.stop, false);

    // DRAM-like arrays: A has tiles*tile_elems, B has tile_elems, C has tiles outputs
    size_t a_elems = tiles * tile_elems;
    size_t b_elems = tile_elems;
    size_t c_elems = tiles;

    c.A = (float*)aligned_alloc(64, ((a_elems * sizeof(float) + 63) / 64) * 64);
    c.B = (float*)aligned_alloc(64, ((b_elems * sizeof(float) + 63) / 64) * 64);
    c.C = (float*)aligned_alloc(64, ((c_elems * sizeof(float) + 63) / 64) * 64);
    if (!c.A || !c.B || !c.C) {
        fprintf(stderr, "alloc failed\n");
        return 1;
    }

    // init A,B
    for (size_t i = 0; i < a_elems; i++) c.A[i] = (float)((i % 97) * 0.01);
    for (size_t i = 0; i < b_elems; i++) c.B[i] = (float)(((i % 89) + 1) * 0.02);
    memset(c.C, 0, c_elems * sizeof(float));

    // rings
    if (ring_init(&c.in_ring, in_depth, tile_elems * sizeof(float)) != 0) {
        fprintf(stderr, "input ring init failed\n");
        return 1;
    }
    if (ring_init(&c.out_ring, out_depth, sizeof(float)) != 0) {
        fprintf(stderr, "output ring init failed\n");
        return 1;
    }

    pthread_t tr, tc, tw;
    if (pthread_create(&tr, NULL, reader_thread, &c) != 0) { perror("pthread_create reader"); return 1; }
    if (pthread_create(&tc, NULL, compute_thread, &c) != 0) { perror("pthread_create compute"); return 1; }
    if (pthread_create(&tw, NULL, writer_thread, &c) != 0) { perror("pthread_create writer"); return 1; }

    pthread_join(tr, NULL);
    pthread_join(tc, NULL);
    pthread_join(tw, NULL);

    uint64_t uf = atomic_load(&c.input_underflow);
    uint64_t of = atomic_load(&c.output_overflow);

    // prevent dead-code elimination
    double checksum = 0.0;
    for (size_t i = 0; i < (c_elems < 1024 ? c_elems : 1024); i++) checksum += c.C[i];

    printf("tiles=%zu tile_elems=%zu in_depth=%zu out_depth=%zu\n", tiles, tile_elems, in_depth, out_depth);
    printf("tiles_read=%zu tiles_done=%zu tiles_written=%zu\n",
           atomic_load(&c.tiles_read), atomic_load(&c.tiles_done), atomic_load(&c.tiles_written));
    printf("input_underflow=%" PRIu64 " output_overflow=%" PRIu64 "\n", uf, of);
    printf("checksum=%f\n", checksum);

    ring_free(&c.in_ring);
    ring_free(&c.out_ring);
    free(c.A); free(c.B); free(c.C);
    return 0;
}
