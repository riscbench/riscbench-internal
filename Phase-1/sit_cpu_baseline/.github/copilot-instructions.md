# SIT CPU Baseline - AI Coding Assistant Instructions

## Project Purpose
**System Integration Test (SIT) baseline workload** modeling a 3-stage data pipeline with deterministic underflow/overflow markers for CPU baseline adapters (perf/spike/rtl). Core architecture: DRAM → input ring buffer → compute → output ring buffer → DRAM.

## Critical Architecture

### Three-Thread SPSC Pipeline
- **Reader** (`reader_thread`): Copies input tiles from array A into `in_ring`, sleep-controlled via `reader_sleep_ns`
- **Compute** (`compute_thread`): Pops tiles from `in_ring`, performs MAC (multiply-accumulate) fold into scalar, pushes to `out_ring`, **emits trace markers**
- **Writer** (`writer_thread`): Drains `out_ring` to array C, sleep-controlled via `writer_sleep_ns`

### Ring Buffer Design (`ring_t`)
- **Lock-free SPSC** using `_Atomic` size_t for head/tail, no mutexes
- Full when `(tail - head) >= capacity`; empty when `head == tail`
- Busy-wait backpressure via `sched_yield()` (don't sleep threads)
- All buffers **64-byte aligned** for cache line performance

### Bottleneck Tracking
- **Input underflow**: Compute spins waiting for data (slow reader or fast compute)
- **Output overflow**: Compute stalls pushing output (slow writer or slow compute)
- Both emitted as raw trace events with timestamps and cumulative counts

## Trace Format

Raw event stream to FILE when `--trace PATH` specified:
```
ts_us=<microseconds> thread=<id> event=<EVENT> [key=value ...]
```

**Events**:
- `THREAD_START` / `THREAD_END`: Lifecycle
- `COMPUTE_WORK`: Tile processed; includes `tiles_done=N uf=X of=Y`
- `INPUT_UNDERFLOW_DETECTED`: Bottleneck; includes `uf_count=N`
- `OUTPUT_OVERFLOW_DETECTED`: Bottleneck; includes `of_count=N`

**Adapter Integration**: Parse this raw stream to populate SIT engine's internal format with residency flags.

## Build & Run

### Build
```bash
gcc -O2 -g -pthread matmul.c -o matmul
```

### Run Variants

**Balanced** (no markers):
```bash
./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2
```

**With raw trace** (recommended):
```bash
./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 \
         --trace results/balanced.trace
```

**Force underflow** (slow reader):
```bash
./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 \
         --reader-sleep-ns 2000 --trace results/uf.trace
```

**Force overflow** (slow writer):
```bash
./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 \
         --writer-sleep-ns 5000 --trace results/of.trace
```

## Key Code Patterns

### Memory Alignment (DRAM Simulation)
```c
size_t align = 64;  // Cache line
c.A = (float*)aligned_alloc(align, a_bytes);  // Input
c.B = (float*)aligned_alloc(align, b_bytes);  // Reused vector
c.C = (float*)aligned_alloc(align, c_bytes);  // Output
```

### Atomic Ordering (Cross-Thread Synchronization)
- **Acquire** on reads: Don't miss updates from producer
- **Release** on writes: Publish results to consumer
- Underflow/overflow: **Relaxed** (just counts, no ordering needed)

```c
// Consumer reads
size_t head = atomic_load_explicit(&ring->head, memory_order_acquire);
// Producer publishes
atomic_store_explicit(&ring->tail, tail + 1, memory_order_release);
```

### Ring Slot Access
```c
uint8_t* dst = ring_slot(&ring, tail);  // Get pointer
memcpy(dst, src, bytes);                 // Operate in-place
atomic_store_explicit(&ring->tail, tail + 1, memory_order_release);
```

### Trace Emission Helper
```c
void emit_trace(ctx_t* c, int thread_id, const char* event, 
                const char* fmt, ...);  // Printf-style variadic
// Usage: emit_trace(c, 1, "COMPUTE_WORK", "tiles_done=%zu", done);
```

## Common Modifications

### Changing Compute Kernel
Replace MAC loop in `compute_thread` (lines ~225–230):
```c
float acc = 0.0f;
for (size_t i = 0; i < n; i++) {
    acc += in_tile[i] * c->B[i];  // Dot product; substitute heavier ops
}
```

### Adding Thread Bottleneck Detection
Modify trace emission in underflow/overflow branches to include **state flags**:
```c
emit_trace(c, 1, "OUTPUT_OVERFLOW_DETECTED", 
          "of_count=%" PRIu64 " ring_usage=%zu/%zu",
          of_count, tail - head, capacity);
```

### Disabling Thread Tracing
Set trace_path to NULL at CLI or pass `--trace /dev/null` to suppress file writes.

## Testing & Validation

**Quick sanity check**:
```bash
./matmul --tile-elems 256 --tiles 100 --in-depth 2 --out-depth 2
# Expected: tiles_read=100 tiles_done=100 tiles_written=100
```

**Profiling bottlenecks**:
- Increase `reader_sleep_ns` → underflow count rises
- Increase `writer_sleep_ns` → overflow count rises
- Ring depths should absorb transient imbalance; too small blocks

## Files to Know

- [matmul.c](../../matmul.c) (~405 lines):
  - `ring_t` / `ctx_t` definitions
  - Three worker threads + `emit_trace()` helper
  - `now_us()`: Monotonic microsecond timestamps
  - CLI arg parsing + trace file I/O
  - No external dependencies; fully self-contained

## Conventions

- **Naming**: `snake_case` for functions/variables; `ctx_t` for global context
- **Atomics**: All cross-thread shared state uses `_Atomic`; **no mutexes** except trace_lock
- **Memory**: 64-byte alignment for cache line performance
- **Timing**: Nanosecond sleeps (`ns_sleep`), microsecond markers (`now_us`)
- **Output**: CLI printf summary + optional raw trace file

