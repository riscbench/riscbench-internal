# Multicore CPU Dataset Documentation

## Overview

The **multicore CPU dataset** extends the SIT CPU baseline with parallel compute workloads to measure throughput scaling, contention, and bottleneck behavior across single and multi-threaded execution models.

### Two Workload Variants

| Workload | Threads | Use Case |
|----------|---------|----------|
| **matmul** | 1 reader + 1 compute + 1 writer | Single-core baseline |
| **matmul_multicore** | 1 reader + N compute + 1 writer | Multi-core scaling analysis |

---

## Architecture

### Three-Thread Pipeline (Shared Rings)

```
DRAM (input tiles)
    ↓
[Reader Thread] → input_ring → [Compute Threads (1..N)] → output_ring → [Writer Thread]
                                    ↓
                                  DRAM (output results)
```

**Key Features:**
- **Lock-free rings** using atomic head/tail pointers (no mutexes)
- **Parallel compute** threads contend on shared input/output rings
- **Configurable depths** to study ring utilization vs. contention
- **Configurable sleeps** to inject bottlenecks (slow reader/writer)
- **Raw trace output** for detailed event-level analysis

---

## Single-Core Baseline: `matmul`

### Purpose
Establish baseline throughput and residency metrics with minimal contention.

### Architecture
```
Reader (1 thread) → Input Ring (depth=2) → Compute (1 thread) → Output Ring (depth=2) → Writer (1 thread)
```

### Quick Start
```bash
# Balanced workload (no bottlenecks)
riscvbench --target cpu --workload matmul --workload_size small --time_us 256

# Force input underflow (slow reader)
riscvbench --target cpu --workload matmul --workload_size small --time_us 256 --underflow

# Force output overflow (slow writer)
riscvbench --target cpu --workload matmul --workload_size small --time_us 256 --overflow
```

### Expected Metrics

**Balanced (no sleeps):**
```
sit_median:       0.50
sit_p95:          0.67
residency_idle:   44.8%   (overhead from sched_yield)
residency_stall:  0.0%    (no blocking)
residency_active: 55.2%   (useful compute)
```

**Underflow (reader slow, 2µs delay):**
```
sit_median:       0.04    (96% throughput loss!)
sit_p95:          0.10
residency_idle:   17.0%   (spin-wait overhead)
residency_stall:  74.6%   (blocked waiting for input)
residency_active: 8.4%
```

**Overflow (writer slow, 5µs delay):**
```
sit_median:       0.10
sit_p95:          0.19
residency_idle:   15.6%
residency_stall:  70.6%   (blocked waiting for output space)
residency_active: 13.8%
```

---

## Multi-Core Scaling: `matmul_multicore`

### Purpose
Study how parallelism impacts throughput and contention under shared-ring coordination.

### Architecture
```
Reader (1) → Input Ring (depth≥N) → Compute (N threads) → Output Ring (depth≥N) → Writer (1)
                                        ↓
                                    Contend on atomic head/tail
```

### Quick Start

**2-thread compute:**
```bash
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 --compute-threads 2
```

**4-thread compute:**
```bash
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 --compute-threads 4
```

**8-thread compute (requires larger ring depths):**
```bash
riscvbench --target cpu --workload matmul_multicore --workload_size med --time_us 256 --compute-threads 8 \
  --in-depth 16 --out-depth 16
```

### Scaling Analysis

#### 2-Thread Multicore (matmul_multicore, tiny)
```
sit_median:       1.00    (perfect throughput for small workload)
sit_p95:          1.00
residency_idle:   10.6%   (less overhead with 2 cores sharing work)
residency_stall:  1.5%
residency_active: 87.9%
```

#### 4-Thread Multicore (matmul_multicore, small)
```
sit_median:       0.55    (parallelism provides ~0.55/0.50 = 10% boost over single-core)
sit_p95:          0.83
residency_idle:   39.6%   (higher idle due to ring contention)
residency_stall:  0.5%
residency_active: 59.9%
```

**Observation:** Throughput doesn't scale linearly (0.55 vs. 0.50) because:
1. Threads contend on atomic ring operations
2. Ring depths may be insufficient for parallel load
3. Writer becomes bottleneck (single thread draining output)

### Ring Depth Impact

Multicore variants **auto-scale ring depths** to match thread count:
```python
# From riscvbench.py
in_depth_final = max(args.in_depth, args.compute_threads)
out_depth_final = max(args.out_depth, args.compute_threads)
```

For 4 threads with default `--in-depth 2`:
- Actual in_depth = max(2, 4) = 4
- Actual out_depth = max(2, 4) = 4

Override with explicit values for custom studies:
```bash
# Force small rings (stress contention)
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads 4 --in-depth 2 --out-depth 2

# Large rings (minimize contention)
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads 4 --in-depth 32 --out-depth 32
```

---

## Bottleneck Injection (Both Workloads)

### Slow Reader (Input Starvation)
Simulates slow data source (e.g., memory, network).

```bash
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads 4 --underflow
```

**Effect:** Compute threads spin on empty input ring, blocking ~75% of time.

### Slow Writer (Output Congestion)
Simulates slow sink (e.g., I/O bottleneck).

```bash
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads 4 --overflow
```

**Effect:** Compute threads block pushing to full output ring, blocking ~70% of time.

### Combined Bottleneck
```bash
riscvbench --target cpu --workload matmul_multicore --workload_size med --time_us 256 \
  --compute-threads 4 --underflow --overflow
```

---

## Workload Sizes (Auto-Scaled Tile Counts)

| Size | Tiles | Purpose |
|------|-------|---------|
| tiny | 10 | Quick validation (~1ms execution) |
| small | 100 | Default use case |
| med | 1000 | Medium dataset |
| large | 5000 | Extended runs |

Override with explicit `--tiles`:
```bash
riscvbench --target cpu --workload matmul --workload_size custom --time_us 256 --tiles 5000
```

---

## Trace Analysis

Raw trace events written to:
```
Phase-1/runs/cpu/matmul{_multicore}/{size}/traces/matmul{_multicore}.trace
```

Format:
```
ts_us=<microseconds> thread=<id> event=<EVENT> [key=value ...]
```

**Events:**
- `THREAD_START` / `THREAD_END`: Lifecycle
- `COMPUTE_WORK`: Tile processed; includes `tiles_done=N uf=X of=Y`
- `INPUT_UNDERFLOW_DETECTED`: Bottleneck marker; includes `uf_count=N`
- `OUTPUT_OVERFLOW_DETECTED`: Bottleneck marker; includes `of_count=N`

**Example trace snippet (matmul_multicore, 2 threads):**
```
ts_us=39963044958 thread=1 event=THREAD_START
ts_us=39963045086 thread=1 event=COMPUTE_WORK tiles_done=1 uf=0 of=0
ts_us=39963045091 thread=1 event=COMPUTE_WORK tiles_done=2 uf=0 of=0
ts_us=39963045105 thread=1 event=THREAD_START        # Thread 2 starts
ts_us=39963045162 thread=1 event=COMPUTE_WORK tiles_done=6 uf=0 of=0
...
```

---

## SIT (Sustained Instantaneous Throughput) Metrics

### Definitions

- **sit_median**: Median throughput across all windows (0-1, where 1 = ideal)
- **sit_p95**: 95th percentile throughput (tells you about worst-case windows)
- **residency_active**: Fraction of trace marked as "active" (useful work)
- **residency_idle**: Fraction marked as "idle" (spin-wait overhead)
- **residency_stall**: Fraction marked as "stall" (blocked on ring operations)

### Example Interpretation

```json
{
  "sit_median": 0.04,
  "sit_p95": 0.10,
  "residency_active": 8.4,
  "residency_idle": 17.0,
  "residency_stall": 74.6
}
```

**Reading:** Sustained throughput is only 4% of peak. While 8.4% of execution is active compute, 74.6% is stalled waiting (bottleneck), and 17% is overhead spin-waiting. This is the **underflow workload** signature.

---

## Performance Tuning Guide

### Goal: Maximize sit_median (throughput)

1. **Identify bottleneck:**
   - If `residency_stall` is high → ring is too small or reader/writer is slow
   - If `residency_idle` is high → threads are spinning (consider higher ring depths)
   - If `residency_active` is low → insufficient parallelism or contention

2. **Increase ring depths:**
   ```bash
   riscvbench --target cpu --workload matmul_multicore --workload_size med --time_us 256 \
     --compute-threads 4 --in-depth 32 --out-depth 32
   ```

3. **Reduce thread count:**
   ```bash
   riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
     --compute-threads 2
   ```

4. **Increase workload size:**
   ```bash
   riscvbench --target cpu --workload matmul_multicore --workload_size large --time_us 256 \
     --compute-threads 4
   ```

---

## Results Location

All output saved to:
```
Phase-1/runs/cpu/matmul{_multicore}/{size}/
├── traces/
│   └── matmul{_multicore}.trace          # Raw events
├── inputs/
│   ├── state_intervals.csv               # Derived state timeline
│   └── residency_intervals.csv           # Residency spans
├── windows.csv                           # Per-window SIT metrics
├── export/
│   └── summary_v1.json                   # Aggregate summary
└── summary.json
```

### View Results

**Compact metrics:**
```bash
cat Phase-1/runs/cpu/matmul_multicore/small/export/summary_v1.json | python3 -m json.tool | grep -E "sit_|residency_"
```

**Full summary:**
```bash
cat Phase-1/runs/cpu/matmul_multicore/small/export/summary_v1.json | python3 -m json.tool
```

**Per-window analysis:**
```bash
head -20 Phase-1/runs/cpu/matmul_multicore/small/windows.csv
```

---

## Example Workflows

### 1. Single-Core Baseline Characterization
```bash
# Capture balanced, underflow, and overflow
riscvbench --target cpu --workload matmul --workload_size small --time_us 256
riscvbench --target cpu --workload matmul --workload_size small --time_us 256 --underflow
riscvbench --target cpu --workload matmul --workload_size small --time_us 256 --overflow

# Compare sit_median across runs
for dir in Phase-1/runs/cpu/matmul/small/*/export/summary_v1.json; do
  echo "$dir: $(cat $dir | python3 -c 'import sys, json; print(json.load(sys.stdin)["sit_median"])')"
done
```

### 2. Multi-Core Scaling Study
```bash
# Test 1, 2, 4, 8 threads
for threads in 1 2 4 8; do
  echo "=== $threads threads ==="
  riscvbench --target cpu --workload matmul_multicore --workload_size med --time_us 256 \
    --compute-threads $threads --in-depth $((threads * 4)) --out-depth $((threads * 4))
done
```

### 3. Ring Depth vs. Contention
```bash
# Small rings (max contention)
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads 4 --in-depth 1 --out-depth 1

# Moderate rings
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads 4 --in-depth 4 --out-depth 4

# Large rings (minimal contention)
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads 4 --in-depth 32 --out-depth 32
```

---

## Command Reference

```bash
# Single-core balanced
riscvbench --target cpu --workload matmul --workload_size {tiny|small|med|large} --time_us 256

# Single-core with bottleneck
riscvbench --target cpu --workload matmul --workload_size small --time_us 256 [--underflow|--overflow]

# Multi-core balanced
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 --compute-threads N

# Multi-core with custom ring depths
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads N --in-depth M --out-depth M

# Multi-core with bottleneck injection
riscvbench --target cpu --workload matmul_multicore --workload_size med --time_us 256 \
  --compute-threads 4 [--underflow|--overflow]

# Custom tile count
riscvbench --target cpu --workload matmul --workload_size small --time_us 256 --tiles 5000

# All options
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 \
  --compute-threads 4 --tile-elems 1024 --tiles 100 --in-depth 8 --out-depth 8 \
  --reader-sleep-ns 0 --writer-sleep-ns 0
```

---

## Implementation Details

### Source Files
- **[matmul.c](matmul.c)**: Single-core workload (1 reader + 1 compute + 1 writer)
- **[matmul_multicore.c](matmul_multicore.c)**: Multi-core variant (1 reader + N compute + 1 writer)
- **[Phase-1/riscvbench.py](../Phase-1/riscvbench.py)**: CLI orchestrator
- **[Phase-1/adapters/cpu_adapter.py](../Phase-1/adapters/cpu_adapter.py)**: Trace parser

### Key Mechanisms
- **Lock-free rings:** Atomic head/tail with memory_order_acquire/release
- **Contention detection:** Atomic underflow/overflow counters
- **Residency derivation:** State intervals from events → binary intervals [active|idle|stall]
- **SIT analysis:** Fixed-window throughput fractions across residency-masked timeline

---

## References

- **SIT Framework:** See [sit_engine_phase1.py](../Phase-1/sit_engine_phase1.py)
- **CLI Interface:** See [RISCVBENCH_USAGE.md](RISCVBENCH_USAGE.md)
- **Architecture Notes:** See copilot-instructions.md (system integration test baseline design)
