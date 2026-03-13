# SIT CPU Baseline - Quick Reference Guide

## TL;DR - Getting Started in 30 Seconds

```bash
# Build
gcc -O2 -g -pthread matmul.c -o matmul

# Run default (MAC workload)
./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2

# Run with specific workload
./matmul --tile-elems 1024 --tiles 50000 --workload alu

# Generate trace for analysis
./matmul --tile-elems 1024 --tiles 10000 --trace results/output.trace
```

---

## Command-Line Reference

### Basic Parameters

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| `--tile-elems` | 1024 | 256+ | Elements per tile (working set size) |
| `--tiles` | 50000 | 100+ | Total tiles to process (workload size) |
| `--in-depth` | 2 | 1+ | Input ring buffer depth (max buffered tiles) |
| `--out-depth` | 2 | 1+ | Output ring buffer depth (max buffered results) |

### Bottleneck Injection

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `--reader-sleep-ns` | 0 | Sleep between reads (forces underflow) |
| `--writer-sleep-ns` | 0 | Sleep between writes (forces overflow) |

### Workload & Output

| Parameter | Default | Options |
|-----------|---------|---------|
| `--workload` | mac | mac, alu, branch, dram_read, dram_write |
| `--trace` | (none) | Path to trace output file (e.g., `results/out.trace`) |

---

## Workload Types at a Glance

### MAC (Multiply-Accumulate) ⭐ **DEFAULT**
```c
acc += in_tile[i] * reused_vec[i];
```
- **Use:** Baseline mixed compute+memory
- **Performance:** 0.64 insn/cycle, 22.1M cycles (baseline)
- **Best for:** Matrix multiply, convolution

### ALU (Arithmetic Logic Unit)
```c
val = val + 1.5f; val *= 2.3f; val -= 0.7f;
```
- **Use:** Pure compute (no memory dependencies)
- **Performance:** 0.54 insn/cycle, 27M cycles (+21% slower)
- **Best for:** FFT, DSP filters, compute throughput

### BRANCH (Branch-Heavy)
```c
if (val > 0.5f) { ... } else { ... }
```
- **Use:** Control-flow heavy
- **Performance:** 0.69 insn/cycle, 23.7M cycles (33% more branch misses)
- **Best for:** Video codecs, decoders, irregular algorithms

### DRAM_READ (Memory Read-Heavy)
```c
val = in_tile[i] + aux[i] + aux[i+1];
```
- **Use:** 3× memory reads per iteration
- **Performance:** 0.55 insn/cycle, 40.3M cycles (+82% slower! ⚠️)
- **Best for:** Sparse matrices, graph algorithms, memory stress test

### DRAM_WRITE (Memory Write-Heavy)
```c
aux[i] = in_tile[i] * 2.0f; acc += aux[i];
```
- **Use:** Write-combine buffer exploitation
- **Performance:** 0.65 insn/cycle, 22.2M cycles (near MAC)
- **Best for:** Streaming, filtering, output buffering

---

## Trace Output Format

When `--trace results/file.trace` is specified:

```
ts_us=<timestamp> thread=<thread_id> event=<EVENT_TYPE> [key=value ...]
```

**Events:**
- `COMPUTE_WORK`: Tile processed; e.g., `tiles_done=100 uf=5 of=2`
- `INPUT_UNDERFLOW_DETECTED`: Compute stalled waiting for input; e.g., `uf_count=50`
- `OUTPUT_OVERFLOW_DETECTED`: Compute stalled on full output ring; e.g., `of_count=75`

**Example trace:**
```
ts_us=1000 thread=1 event=COMPUTE_WORK tiles_done=1 uf=0 of=0
ts_us=2000 thread=1 event=COMPUTE_WORK tiles_done=2 uf=0 of=0
ts_us=3000 thread=1 event=INPUT_UNDERFLOW_DETECTED uf_count=1
ts_us=3500 thread=1 event=COMPUTE_WORK tiles_done=3 uf=1 of=0
```

---

## Common Use Cases

### 1️⃣ Baseline Performance (Balanced)
```bash
./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2
# Expected: 0 underflow, minimal overflow, ~0.2s runtime
```

### 2️⃣ Force Input Underflow (Reader Too Slow)
```bash
./matmul --tile-elems 1024 --tiles 50000 --reader-sleep-ns 2000 \
         --trace results/underflow.trace
# Expected: 100K+ underflow events, 5× slowdown
```

### 3️⃣ Force Output Overflow (Writer Too Slow)
```bash
./matmul --tile-elems 1024 --tiles 50000 --writer-sleep-ns 5000 \
         --trace results/overflow.trace
# Expected: 200K+ overflow events, 6× slowdown
```

### 4️⃣ Compare Workload Performance
```bash
for wl in mac alu branch dram_read dram_write; do
    echo "=== $wl ==="
    ./matmul --workload $wl --tiles 10000
done
```

### 5️⃣ Profile with perf
```bash
# Instructions, cycles, cache misses, branch misses
perf stat -e instructions,cycles,cache-misses,branch-misses \
    ./matmul --workload dram_read --tiles 50000

# Memory stalls
perf stat -e LLC-load-misses,LLC-store-misses \
    ./matmul --workload dram_write --tiles 50000
```

### 6️⃣ Stress Test Memory Hierarchy
```bash
# Large tile size = pressure on L1/L2
./matmul --tile-elems 4096 --tiles 10000 --workload dram_read \
         --trace results/memory_stress.trace
```

### 7️⃣ Generate Multiple Trace Files
```bash
mkdir -p results
for wl in mac alu branch dram_read dram_write; do
    for scenario in balanced underflow overflow; do
        case $scenario in
            balanced)   args="" ;;
            underflow)  args="--reader-sleep-ns 2000" ;;
            overflow)   args="--writer-sleep-ns 5000" ;;
        esac
        ./matmul --workload $wl --tiles 5000 $args \
                 --trace results/${wl}_${scenario}.trace
    done
done
```

---

## Output Interpretation

```
tiles=50000 tile_elems=1024 in_depth=2 out_depth=2
tiles_read=50000 tiles_done=50000 tiles_written=50000
input_underflow=0 output_overflow=142
checksum=123456.789123
```

| Field | Meaning | Expected |
|-------|---------|----------|
| `tiles_read` | Input tiles loaded from "DRAM" | Should equal `--tiles` |
| `tiles_done` | Tiles completed by compute | Should equal `--tiles` |
| `tiles_written` | Output tiles written to "DRAM" | Should equal `--tiles` |
| `input_underflow` | Times compute stalled on empty input ring | 0 = balanced pipeline |
| `output_overflow` | Times compute stalled on full output ring | 0 = balanced pipeline |
| `checksum` | Sanity check (prevents dead-code elimination) | Varies by workload |

---

## Performance Characteristics (1000 tiles × 256 elements)

| Workload | Cycles | Insn/Cycle | Cache Miss | Branch Miss | Speed |
|----------|--------|-----------|------------|------------|-------|
| **MAC** | 22.1M | 0.64 | 45.3K | 22.3K | 1.0× |
| **ALU** | 27.0M | 0.54 | 100.5K | 22.1K | 1.18× slower |
| **BRANCH** | 23.7M | 0.69 | 39.8K | 29.7K | 1.07× slower |
| **DRAM_READ** | 40.3M | 0.55 | 109.2K | 32.5K | **1.82× slower** ⚠️ |
| **DRAM_WRITE** | 22.2M | 0.65 | 41.3K | 22.1K | Slightly slower |

**Key insight:** Memory access patterns dominate performance. DRAM_READ is 82% slower!

---

## Bottleneck Injection Strategy

### Input Underflow (Reader Slow)
- **Cause:** `--reader-sleep-ns` > time to process tile
- **Symptom:** `input_underflow` counter increases
- **Effect:** Compute thread spins waiting for input (wasted CPU cycles)
- **Example:**
  ```bash
  # Reader sleep 2000 ns/tile, but compute takes ~5000 ns → starves input ring
  ./matmul --tiles 5000 --reader-sleep-ns 2000 --trace results/uf.trace
  ```

### Output Overflow (Writer Slow)
- **Cause:** `--writer-sleep-ns` > time to write tile
- **Symptom:** `output_overflow` counter increases
- **Effect:** Compute thread stalls pushing output (backpressure)
- **Example:**
  ```bash
  # Writer sleep 5000 ns/tile → output ring fills up
  ./matmul --tiles 5000 --writer-sleep-ns 5000 --trace results/of.trace
  ```

### Tuning Ring Depths
- **Small rings (--in-depth 1):** Low memory, but tight coupling → more underflow/overflow
- **Large rings (--in-depth 8):** More buffering, loose coupling → fewer stalls
- **Sweet spot:** Usually 2-4 for balanced pipeline

---

## Debug Tips

### Check that compilation works
```bash
gcc -O2 -g -pthread matmul.c -o matmul 2>&1 | head -20
echo "Compilation status: $?"
```

### Verify workload runs
```bash
./matmul --tile-elems 256 --tiles 100 --workload alu
# Should complete in <1 second
```

### Check trace format
```bash
./matmul --tiles 100 --trace /tmp/test.trace
head -5 /tmp/test.trace
# Should show: ts_us=... thread=... event=...
```

### Verify all workloads compile correctly
```bash
for wl in mac alu branch dram_read dram_write; do
    ./matmul --workload $wl --tiles 10 && echo "✓ $wl" || echo "✗ $wl"
done
```

---

## Integration Checklist

- [x] 3-thread SPSC pipeline (reader → compute → writer)
- [x] Ring buffer backpressure detection
- [x] Raw trace format (ts_us, thread, event, key=value)
- [x] 5 compute kernels (MAC, ALU, BRANCH, DRAM_READ, DRAM_WRITE)
- [x] Deterministic underflow/overflow injection
- [x] Lock-free atomic synchronization
- [x] 64-byte cache-line aligned memory
- [x] Bottleneck event emission (underflow, overflow, compute_work)
- [ ] **Next:** Trace adapter to parse .trace files into SIT engine residency format

---

## More Information

- [WORKLOAD_ANALYSIS.md](WORKLOAD_ANALYSIS.md) - Detailed performance analysis for each workload
- [.github/copilot-instructions.md](../.github/copilot-instructions.md) - Architecture & code patterns
- Run `./matmul --help` - CLI usage (if implemented)

---

## Files

| File | Lines | Purpose |
|------|-------|---------|
| `matmul.c` | 529 | Main workload + SPSC pipeline implementation |
| `WORKLOAD_ANALYSIS.md` | ~300 | Detailed performance analysis per workload type |
| `.github/copilot-instructions.md` | 158 | AI coding agent guide (architecture, patterns, conventions) |

