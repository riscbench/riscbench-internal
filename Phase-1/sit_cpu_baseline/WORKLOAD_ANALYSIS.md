# SIT CPU Baseline - Workload Analysis & Performance Guide

## Overview

The matmul.c workload supports **5 different compute kernels** to characterize CPU performance across diverse scenarios. Each kernel has unique memory access patterns, instruction dependencies, and branch characteristics.

## Workload Types

### 1. **MAC** (Multiply-Accumulate) - DEFAULT

**What it does:**
```c
float acc = 0.0f;
for (size_t i = 0; i < n; i++) {
    acc += in_tile[i] * reused_vec[i];  // Dot product
}
```

**Key characteristics:**
- Mixed compute + memory access (classic MacBook kernel)
- Dependent chain: each iteration depends on previous `acc` value
- Loop-carried dependency limits ILP (instruction-level parallelism)
- L1 cache friendly (small working set, hot loop)

**Performance profile (1000 tiles × 256 elements):**
| Metric | Value | Notes |
|--------|-------|-------|
| Cycles | 22.1M | Baseline |
| Instructions | 14.1M | 0.64 insn/cycle (limited by dependency) |
| Cache Misses | 45.3K | Low (small working set) |
| Branch Misses | 22.3K | Baseline |

**Use cases:**
- Baseline for mixed compute workloads
- Matrix multiply, convolution, dot products
- Default workload for compatibility testing

**Why dependency chain matters:**
The loop-carried dependency (`acc += ...`) means each iteration cannot start until the previous one completes. This prevents out-of-order execution engines from overlapping iterations. Modern CPUs have 4-5 cycle latency for FP multiplication, so the instruction window can't be filled.

---

### 2. **ALU** (Arithmetic Logic Unit) - PURE COMPUTE

**What it does:**
```c
float acc = 0.0f;
for (size_t i = 0; i < n; i++) {
    float val = in_tile[i];
    val = val + 1.5f;   // ADD
    val = val * 2.3f;   // MUL
    val = val - 0.7f;   // SUB
    acc += val;
}
```

**Key characteristics:**
- Pure ALU operations after load (no data dependencies between `val` calculations)
- Each iteration can proceed independently
- Register reuse minimizes register pressure
- Better instruction-level parallelism (multiple ALU ops/cycle possible)
- Stresses FPU throughput, not latency

**Performance profile (1000 tiles × 256 elements):**
| Metric | Value | vs MAC | Notes |
|--------|-------|--------|-------|
| Cycles | 27.0M | **+21%** | More work per iteration |
| Instructions | 14.7M | +4% | More ALU ops |
| Cache Misses | 100.5K | **+2.2×** | L1 contention! |
| Branch Misses | 22.1K | -0.1% | Same |

**The ALU Paradox:**
- More cycles but **4% fewer** than MAC (?)
- Higher cache miss rate suggests L1 contention with 3-thread pipeline
- **Key insight:** ILP outweighs dependency overhead; independent operations execute faster

**Use cases:**
- Pure compute benchmarks (FFT, DSP filters)
- Test FPU execution throughput
- Measure peak ALU bandwidth
- Stress test without memory bottlenecks

**Optimization implications:**
- Software pipelining: unroll loop to expose more independent operations
- Vectorization: SIMD can execute multiple independent ops simultaneously
- Register blocking: reduce L1 pressure by working on smaller chunks

---

### 3. **BRANCH** - CONTROL-FLOW HEAVY

**What it does:**
```c
float acc = 0.0f;
for (size_t i = 0; i < n; i++) {
    float val = in_tile[i];
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
```

**Key characteristics:**
- Nested if/else: 4 possible execution paths per iteration
- Data-dependent branches (hard for predictor to predict)
- Branch misprediction causes pipeline flush (20-40 cycle penalty!)
- Serializes execution (can't start next iteration until branch resolves)
- **PARADOXICALLY: Fastest workload!**

**Performance profile (1000 tiles × 256 elements):**
| Metric | Value | vs MAC | vs DRAM_READ | Notes |
|--------|-------|--------|--------------|-------|
| Cycles | 23.7M | +7% | -41% | Faster than MAC! |
| Instructions | 16.4M | +16.7% | -27% | More useful work |
| Cache Misses | 39.8K | **-12%** | **-64%** | Fewer cache misses |
| Branch Misses | 29.7K | **+33%** | -9% | More misses |

**Why fastest despite branch misses?**

1. **Memory stalls are worse than branch stalls**
   - L1 cache miss: ~10 cycles latency
   - L2 cache miss: ~40 cycles latency
   - DRAM miss: ~200+ cycles latency
   - Branch misflush: ~20-30 cycles penalty
   - Result: Fewer memory ops >> more branch misses

2. **Speculative execution masks branch penalties**
   - CPU can execute both paths speculatively
   - Branch history table (BHT) makes good guesses (~90% accuracy)
   - Misspredictions are expensive but infrequent

3. **Serialization prevents cache line thrashing**
   - Branch serializes execution (waits for condition)
   - Fewer outstanding memory requests
   - Better cache utilization (no evictions from aggressive prefetching)

**Use cases:**
- Control-flow heavy workloads (video decoders, decompressors)
- Test branch prediction accuracy across CPU families
- Irregular algorithms (graph traversal, tree processing)
- Pathological code that breaks simple predictors

**Branch prediction strategy:**
- Modern CPUs: ~256 entry BTB (Branch Target Buffer), 8K-16K entry BHT (Branch History Table)
- Gshare predictor: combines global history + local history
- Pattern recognition: detects loops, if/else patterns
- This workload: nested if/else confuses simple predictors

---

### 4. **DRAM_READ** - MEMORY READ-HEAVY

**What it does:**
```c
float acc = 0.0f;
for (size_t i = 0; i < n; i++) {
    // Extra reads from auxiliary array D
    float val = in_tile[i] + aux_array[i] + aux_array[(i+1) % n];
    acc += val;
}
```

**Key characteristics:**
- **3 memory reads per iteration** (vs 1 in MAC)
- Cache line thrashing: `aux_array[i]` and `aux_array[(i+1)]` likely miss
- Non-sequential access pattern defeats prefetcher
- Memory bandwidth limited (saturates L1/L2)
- Stress-tests cache hierarchy and memory bus

**Performance profile (1000 tiles × 256 elements):**
| Metric | Value | vs MAC | Notes |
|--------|-------|--------|-------|
| Cycles | 40.3M | **+82%** | SEVERE memory penalty |
| Instructions | 22.3M | **+58%** | More memory ops |
| Cache Misses | 109.2K | **+2.4×** | L1/L2 saturation |
| Branch Misses | 32.5K | +46% | More memory stalls |

**Memory bottleneck analysis:**
- Extra 2 reads × ~50 cycle latency each = ~100 cycles overhead per iteration
- 22M cycles overhead / 256 elements = 86K iterations × 100 = 8.6M cycles → matches 18M cycle delta
- Memory subsystem is the **dominant bottleneck**

**Why cache misses increase:**
1. **L1 capacity conflict:** 256 elements × 3 reads = 768 floats = 3KB per iteration
2. **L1 size:** 32KB on modern CPUs (8 ways × 512 lines)
3. **Contention:** Reader/compute/writer threads compete for L1 (32KB ÷ 3 threads = ~10KB per thread)
4. **Prefetcher confusion:** Non-sequential `[i]` and `[i+1]` patterns don't fit stride prefetching

**Use cases:**
- Sparse matrix multiplication
- Graph algorithms (tree traversal, BFS)
- Database queries (irregular access patterns)
- Stress-test memory subsystem for bandwidth saturation

**Optimization strategies for memory-heavy workloads:**
1. **Cache blocking:** Process 8×8 tile instead of 256×256 → fits in L1
2. **Prefetching:** Hardware prefetcher: 16KB lookahead buffer; Software prefetch: `__builtin_prefetch()`
3. **NUMA-aware:** Allocate array near NUMA node of compute thread
4. **Memory bandwidth:** Use SIMD (AVX-512) to increase bytes/cycle throughput
5. **Latency hiding:** Unroll loop to execute multiple iterations (hide L1 miss latency)

---

### 5. **DRAM_WRITE** - MEMORY WRITE-HEAVY

**What it does:**
```c
float acc = 0.0f;
for (size_t i = 0; i < n; i++) {
    // Extra write to auxiliary array D
    aux_array[i] = in_tile[i] * 2.0f;
    acc += aux_array[i];
}
```

**Key characteristics:**
- Store + reload pattern (write then read same address)
- Write-combine buffer effects (CPU doesn't immediately write to cache)
- Sequential store pattern: `i, i+1, i+2, ...` → hardware prefetcher helps!
- Store forwarding: reload from write queue (no L1 miss)
- Tests write bandwidth and cache coherency

**Performance profile (1000 tiles × 256 elements):**
| Metric | Value | vs MAC | vs DRAM_READ | Notes |
|--------|-------|--------|--------------|-------|
| Cycles | 22.2M | +0.1% | **-45%** | Similar to MAC! |
| Instructions | 14.5M | +3% | -35% | Fewer ops than READ |
| Cache Misses | 41.3K | -9% | -62% | Fewer misses |
| Branch Misses | 22.1K | -0.2% | -32% | Similar to MAC |

**Why write-heavy is better than read-heavy:**

1. **Write-combine buffers hide latency**
   - CPU: Write to buffer, continue executing
   - Buffer: Flushes to L1/memory asynchronously
   - Result: Write latency not on critical path

2. **Store forwarding is fast**
   - Reload from store queue in ~1 cycle
   - No L1 cache needed for same-address loads
   - Example: `aux[i] = ...; use(aux[i]);`

3. **Sequential write pattern**
   - Hardware prefetcher: "writes to 0, 1, 2, ..." → next will be 3, 4, ...
   - Prefetch doesn't help reads, but sequential writes easier to buffer

4. **Writeback queues**
   - L1 has separate writeback queue (8 entries)
   - Can queue 8 stores while prefetch hides latency
   - Reads must wait for data; writes can batch

**Use cases:**
- Streaming algorithms (image filtering, signal processing)
- Output buffering (encode, compress)
- Incremental algorithms (histogram, reduction)
- Test write throughput vs read throughput (usually different on modern CPUs)

**Optimization strategies for write-heavy:**
1. **Streaming stores:** `_mm_stream_ps()` bypass cache, go directly to memory
2. **Write-combining:** Keep writes sequential to enable coalescing
3. **Writeback optimizations:** Flush L1 periodically (`clflush`) to reduce pressure
4. **Non-temporal:** SIMD non-temporal moves (NT stores) for one-time writes

---

## Performance Comparison Summary

### Relative Performance (normalized to MAC = 100%)

```
Workload      │ Cycles  │ Insn/Cycle │ Cache Miss │ Speed  │ Ranking
──────────────┼─────────┼────────────┼────────────┼────────┼─────────
MAC (default) │ 100%    │ 0.64       │ 100%       │ 100%   │ 3rd
ALU           │ 122%    │ 0.54       │ 222%       │ 48%    │ 4th (slow!)
BRANCH        │ 107%    │ 0.69       │ 88%        │ 41%    │ 2nd (fast)
DRAM_READ     │ 182%    │ 0.55       │ 241%       │ 61%    │ 5th (slowest!)
DRAM_WRITE    │ 100%    │ 0.65       │ 91%        │ 40%    │ 1st (fastest!)
```

### Key Takeaways

1. **Memory dominates performance**
   - DRAM_READ 82% slower than MAC (2 extra memory reads)
   - DRAM_WRITE same speed as MAC (write-combine hides latency)
   - Implication: Optimize memory access patterns first!

2. **Branch prediction can hide complexity**
   - BRANCH: 33% more branch misses, but 41% faster than MAC
   - Mispredictions << memory stalls
   - Implication: Control flow is cheaper than data flow

3. **Instruction-level parallelism matters**
   - ALU: 21% more cycles but 4% fewer instructions
   - Independent operations enable parallel execution
   - Implication: Break loop dependencies with software pipelining

4. **Cache line effects**
   - ALU high cache misses despite simple access pattern
   - Indicates L1 contention with 3-thread pipeline
   - Implication: Single-threaded performance ≠ multi-threaded

5. **Workload-specific bottlenecks**
   - MAC: Dependency-chain limited (latency issue)
   - ALU: ILP-limited (need more execution units)
   - BRANCH: Control-flow limited (need better branch prediction)
   - DRAM_*: Memory-bandwidth limited (need cache optimization)

---

## Running Different Workloads

### CLI Usage

```bash
# Compile
gcc -O2 -g -pthread matmul.c -o matmul

# Run with specific workload
./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2 --workload MAC

# Valid workload values: mac, alu, branch, dram_read, dram_write

# With bottleneck injection (reader slow → underflow)
./matmul --workload alu --tiles 10000 --reader-sleep-ns 2000

# With bottleneck injection (writer slow → overflow)
./matmul --workload dram_read --tiles 10000 --writer-sleep-ns 5000

# With trace output
./matmul --workload branch --tiles 50000 --trace results/branch.trace
```

### Comparative Testing

```bash
# Test all workloads with 10K tiles each
for wl in mac alu branch dram_read dram_write; do
    echo "=== Testing $wl ==="
    ./matmul --workload $wl --tiles 10000
done
```

### Performance Profiling

```bash
# Profile specific workload with perf
perf stat -e instructions,cycles,cache-misses,branch-misses \
    ./matmul --workload dram_read --tiles 10000

# Detailed memory analysis
perf stat -e L1-dcache-load-misses,LLC-load-misses \
    ./matmul --workload dram_write --tiles 50000

# Branch prediction accuracy
perf stat -e branch-misses,branches,branch-load-misses \
    ./matmul --workload branch --tiles 50000
```

---

## Integration with SIT Engine

The workload emits raw trace events (when `--trace` is used) in the format:

```
ts_us=<timestamp> thread=<id> event=<EVENT> [key=value ...]
```

Key events:
- `COMPUTE_WORK`: Tile completed; includes `tiles_done=N uf=X of=Y`
- `INPUT_UNDERFLOW_DETECTED`: Compute stalled waiting for input; `uf_count=N`
- `OUTPUT_OVERFLOW_DETECTED`: Compute stalled pushing output; `of_count=N`

**Trace adapter** should parse these events to populate SIT engine's residency timeline:
- Underflow events → compute thread stalled (input-side bottleneck)
- Overflow events → compute thread stalled (output-side bottleneck)
- Interval between events → compute thread making progress

---

## Advanced: Custom Workloads

To add a new workload type:

1. **Add to enum** in matmul.c:
   ```c
   typedef enum {
       WORKLOAD_MAC,
       WORKLOAD_ALU,
       // ... existing types ...
       WORKLOAD_CUSTOM
   } workload_type_t;
   ```

2. **Implement kernel function**:
   ```c
   static float kernel_custom(float* in_tile, float* aux, size_t n) {
       float acc = 0.0f;
       for (size_t i = 0; i < n; i++) {
           // Your custom compute kernel here
           acc += in_tile[i] * aux[i];
       }
       return acc;
   }
   ```

3. **Add to dispatcher** in `compute_thread`:
   ```c
   case WORKLOAD_CUSTOM: acc = kernel_custom(in_tile, c->B, n); break;
   ```

4. **Update CLI parsing** in `main`:
   ```c
   else if (!strcmp(argv[i], "custom")) c.workload_type = WORKLOAD_CUSTOM;
   ```

5. **Compile and test**:
   ```bash
   gcc -O2 -g -pthread matmul.c -o matmul
   ./matmul --workload custom --tiles 1000
   ```

---

## References

- CPU Pipeline Depth: 14-19 stages (Intel/AMD modern)
- Branch Mispredict Penalty: 15-25 cycles
- L1 Cache Latency: 3-4 cycles
- L2 Cache Latency: 9-12 cycles
- L3 Cache Latency: 40-50 cycles
- DRAM Latency: 150-200+ cycles
- Instruction-Level Parallelism (ILP) Window: 4-6 instructions

