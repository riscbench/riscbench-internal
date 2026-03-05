# SIT CPU Baseline - Complete Documentation Index

## Overview

The **SIT (System Integration Test) CPU Baseline** is a deterministic workload modeling a 3-stage data pipeline (reader → compute → writer) with configurable bottlenecks and multiple compute kernels. It emits raw trace events for residency analysis and supports 5 different workload types to stress-test different CPU subsystems.

**Purpose:** Generate baseline performance data for CPU adapters (perf, spike, RTL) in the SIT engine, including deterministic underflow/overflow markers and residency timelines.

---

## Document Map

### 📄 Core Documentation

| Document | Purpose | Size | Quick Link |
|----------|---------|------|------------|
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | **START HERE** - CLI commands, workload types, common patterns | 303 lines | ⭐ Most concise |
| [WORKLOAD_ANALYSIS.md](WORKLOAD_ANALYSIS.md) | Detailed analysis of 5 compute kernels (MAC, ALU, BRANCH, DRAM_READ, DRAM_WRITE) | 444 lines | 📊 Performance metrics |
| [TRACE_ANALYSIS_EXAMPLES.md](TRACE_ANALYSIS_EXAMPLES.md) | Real-world trace examples, parsing, adapter integration | 411 lines | 🔍 Trace interpretation |
| [.github/copilot-instructions.md](../.github/copilot-instructions.md) | AI coding agent guide (for extending/modifying code) | 158 lines | 🤖 For developers |

### 📝 Source Code

| File | Purpose | Lines | Language |
|------|---------|-------|----------|
| [matmul.c](matmul.c) | Single-file implementation: SPSC rings, 3 threads, 5 kernels, trace emission | 529 | C11 + pthreads |

---

## Quick Navigation

### I want to... 

#### 🚀 **Run a quick test**
→ See [QUICK_REFERENCE.md#TL;DR](QUICK_REFERENCE.md)
```bash
gcc -O2 -g -pthread matmul.c -o matmul
./matmul --tile-elems 1024 --tiles 50000
```

#### 📊 **Compare workload performance**
→ See [WORKLOAD_ANALYSIS.md#Performance Comparison Summary](WORKLOAD_ANALYSIS.md)
- 5 workload types with measured performance characteristics
- Memory vs compute trade-offs
- Cache miss analysis

#### 🔍 **Understand trace output**
→ See [TRACE_ANALYSIS_EXAMPLES.md](TRACE_ANALYSIS_EXAMPLES.md)
- 6 real-world trace examples (balanced, underflow, overflow, cascading, memory-heavy)
- Parsing strategies
- Adapter integration checklist

#### ⚙️ **Generate custom scenarios**
→ See [QUICK_REFERENCE.md#Common Use Cases](QUICK_REFERENCE.md)
- Force bottlenecks with `--reader-sleep-ns` / `--writer-sleep-ns`
- Select workload with `--workload {mac,alu,branch,dram_read,dram_write}`
- Output trace with `--trace results/out.trace`

#### 🧠 **Extend or modify code**
→ See [.github/copilot-instructions.md](../.github/copilot-instructions.md)
- Architecture patterns (ring buffers, atomic ordering)
- Code patterns (memory alignment, trace emission)
- Common modifications (changing compute kernel, adding bottleneck detection)

---

## Feature Checklist

### Core Architecture ✅
- [x] 3-thread SPSC pipeline (reader → input ring → compute → output ring → writer)
- [x] Lock-free ring buffers using C11 atomics (no mutexes)
- [x] Deterministic bottleneck injection (nanosecond sleep)
- [x] 64-byte cache-line aligned memory
- [x] Monotonic microsecond timestamp tracking

### Compute Kernels ✅
- [x] **MAC** (Multiply-Accumulate) - mixed compute + memory (default)
- [x] **ALU** (Arithmetic Logic Unit) - pure computation
- [x] **BRANCH** - control-flow heavy with nested if/else
- [x] **DRAM_READ** - memory read-heavy (2.4× cache misses)
- [x] **DRAM_WRITE** - memory write-heavy (write-combine optimization)

### Trace & Bottleneck Markers ✅
- [x] Raw event stream format: `ts_us=<timestamp> thread=<id> event=<EVENT> [key=value ...]`
- [x] Event types: `COMPUTE_WORK`, `INPUT_UNDERFLOW_DETECTED`, `OUTPUT_OVERFLOW_DETECTED`
- [x] Cumulative counter tracking: `uf_count`, `of_count`
- [x] Microsecond-precision timing
- [x] Mutex-protected file I/O

### CLI Interface ✅
- [x] `--tile-elems` - elements per tile (working set size)
- [x] `--tiles` - total tiles to process
- [x] `--in-depth`, `--out-depth` - ring buffer sizes
- [x] `--reader-sleep-ns`, `--writer-sleep-ns` - bottleneck injection
- [x] `--workload` - select compute kernel (mac/alu/branch/dram_read/dram_write)
- [x] `--trace` - output trace file path

### Documentation ✅
- [x] Quick reference (CLI, common patterns, debugging)
- [x] Detailed workload analysis (5 kernels, 444 lines of analysis)
- [x] Trace examples (6 real-world scenarios)
- [x] AI coding agent guide (.github/copilot-instructions.md)
- [x] Integration checklist for SIT engine

### Validation ✅
- [x] Balanced pipeline: 0 underflow, minimal overflow
- [x] Underflow injection: 100K+ underflow events on reader slowdown
- [x] Overflow injection: 200K+ overflow events on writer slowdown
- [x] All 5 workloads: Functional tests pass
- [x] Perf analysis: Performance profiles match expectations

---

## Performance Summary

### By Workload Type (1000 tiles × 256 elements)

| Workload | Cycles | Insn/Cycle | Cache Miss | Use Case |
|----------|--------|-----------|------------|----------|
| **MAC** ⭐ | 22.1M | 0.64 | 45.3K | Mixed compute+memory |
| **ALU** | 27.0M | 0.54 | 100.5K | Pure compute |
| **BRANCH** | 23.7M | 0.69 | 39.8K | Control-flow heavy |
| **DRAM_READ** ⚠️ | 40.3M | 0.55 | 109.2K | Memory-intensive |
| **DRAM_WRITE** | 22.2M | 0.65 | 41.3K | Streaming |

**Key insight:** Memory access patterns dominate (DRAM_READ 82% slower than MAC).

### By Bottleneck Scenario (5000 tiles)

| Scenario | Underflow | Overflow | Speedup | Pattern |
|----------|-----------|----------|---------|---------|
| **Balanced** | 0 | ~50 | 1.0× | Normal pipeline |
| **Underflow** | 10K+ | ~10 | 4.8× slower | Reader bottleneck |
| **Overflow** | ~5 | 50K+ | 6.3× slower | Writer bottleneck |
| **Cascading** | 500+ | 500+ | 8× slower | Both bottlenecks |

---

## File Structure

```
sit-cpu-baseline/
├── matmul.c                          (529 lines) Main workload
├── QUICK_REFERENCE.md                (303 lines) CLI guide & quick start
├── WORKLOAD_ANALYSIS.md              (444 lines) Detailed kernel analysis
├── TRACE_ANALYSIS_EXAMPLES.md        (411 lines) Trace examples & parsing
├── README.md                         (This file)
├── .github/
│   └── copilot-instructions.md       (158 lines) AI agent guide
├── results/
│   ├── balanced.trace                (from --trace results/balanced.trace)
│   ├── underflow.trace
│   ├── overflow.trace
│   └── ...
└── [Other files]
```

---

## Key Concepts

### Ring Buffer (Lock-Free SPSC)
- Atomic head/tail pointers (no mutexes)
- Full when `(tail - head) >= capacity`
- Empty when `head == tail`
- Busy-wait backpressure via `sched_yield()` (don't sleep threads)

### Bottleneck Detection
- **Input Underflow:** Compute spins waiting for data (slow reader or fast compute)
- **Output Overflow:** Compute stalls pushing output (slow writer or full ring)
- Both emit raw trace events with timestamps and cumulative counts

### Trace Format
```
ts_us=<timestamp> thread=<id> event=<EVENT> [key=value ...]
```
Raw event stream (not CSV) enables incremental parsing and residency timeline construction.

### Workload Types
- **Balanced (MAC):** Mixed compute + memory; dependent chain limits ILP
- **Pure Compute (ALU):** Independent operations; stresses execution units
- **Control-Flow (BRANCH):** Data-dependent branches; tests prediction accuracy
- **Memory-Heavy (DRAM_READ):** 3 reads/iteration; 82% slower due to cache misses
- **Memory-Write (DRAM_WRITE):** Write-combine optimization; write-back queues hide latency

---

## Integration with SIT Engine

### Trace Adapter Requirements

The workload emits raw events that the SIT adapter must consume:

1. **Parse events** from `.trace` file (ts_us, thread, event, key-value pairs)
2. **Identify bottleneck phases** (COMPUTE_WORK vs underflow vs overflow periods)
3. **Calculate residency** (% compute, % input stall, % output stall)
4. **Build timeline** (microsecond-bucket residency histogram)
5. **Generate report** (bottleneck intensity, pipeline efficiency metrics)

**Pseudo-code example:**
```python
residency = {"COMPUTE": 0, "INPUT_STALL": 0, "OUTPUT_STALL": 0}
for line in trace:
    ts, thread, event, *fields = parse(line)
    if event == "COMPUTE_WORK":
        residency["COMPUTE"] += 1
    elif event == "INPUT_UNDERFLOW_DETECTED":
        residency["INPUT_STALL"] += 1000  # Many detections per compute work
    elif event == "OUTPUT_OVERFLOW_DETECTED":
        residency["OUTPUT_STALL"] += 1000
        
# Report: 70% compute, 15% input stall, 15% output stall
```

See [TRACE_ANALYSIS_EXAMPLES.md#Adapter Integration Checklist](TRACE_ANALYSIS_EXAMPLES.md#adapter-integration-checklist) for full details.

---

## Usage Examples

### Example 1: Baseline Performance (No Bottlenecks)
```bash
./matmul --tile-elems 1024 --tiles 50000 --in-depth 2 --out-depth 2
# Expected: underflow=0, overflow<100, execution time ~0.2s
```

### Example 2: Force Input Underflow (Slow Reader)
```bash
./matmul --tile-elems 1024 --tiles 50000 --reader-sleep-ns 2000 \
         --trace results/underflow.trace
# Expected: underflow>100K, overflow<10, 5× slowdown
```

### Example 3: Force Output Overflow (Slow Writer)
```bash
./matmul --tile-elems 1024 --tiles 50000 --writer-sleep-ns 5000 \
         --trace results/overflow.trace
# Expected: underflow<10, overflow>200K, 6× slowdown
```

### Example 4: Memory-Intensive Workload
```bash
./matmul --tile-elems 4096 --tiles 10000 --workload dram_read \
         --trace results/memory_stress.trace
# Expected: 82% slower than MAC, minimal underflow, some overflow
```

### Example 5: Branch-Heavy Workload
```bash
./matmul --workload branch --tiles 50000 --trace results/branch.trace
# Expected: 33% more branch misses, but 41% faster than DRAM_READ
```

### Example 6: Profiling with perf
```bash
perf stat -e instructions,cycles,cache-misses,branch-misses \
    ./matmul --workload alu --tiles 50000
```

---

## Performance Optimization Tips

### For High Underflow Rates
- Increase `--in-depth` (more buffering)
- Decrease `--tile-elems` (smaller working set, faster compute)
- Reduce `--reader-sleep-ns`

### For High Overflow Rates
- Increase `--out-depth` (more buffering)
- Reduce `--writer-sleep-ns`
- Optimize writer performance

### For Memory-Heavy Workloads
- Use `--workload dram_read` or `dram_write`
- Increase `--tile-elems` to stress memory subsystem
- Run `perf stat` to measure cache misses
- Compare with MAC baseline

### For Cache Performance Analysis
- Start with small `--tile-elems` (256) - fits in L1
- Increase to medium (1024) - L1 conflict
- Increase to large (4096) - L2/L3 miss dominant
- Plot cache miss rate vs tile size

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Compilation fails | Missing pthreads | Install `build-essential`; check `-pthread` flag |
| High underflow on balanced | Reader thread starved | Increase `--in-depth`; reduce `--tile-elems` |
| High overflow on balanced | Writer thread starved | Increase `--out-depth`; check system load |
| Trace file not created | Missing `results/` dir | `mkdir -p results`; check file permissions |
| Inconsistent perf numbers | CPU frequency scaling | Disable: `echo performance \| sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor` |

---

## Key Papers & References

- **Lock-Free Programming:** "Algorithms for Scalable Synchronization on Shared-Memory Multiprocessors" (Mellor-Crummey & Scott)
- **Memory Hierarchy:** "What Every Programmer Should Know About Memory" (Ulrich Drepper)
- **Branch Prediction:** "The Case for Aggressive Branch Prediction" (Yeh & Patt)
- **CPU Pipeline:** Intel/AMD Optimization Manuals (freely available)

---

## Contributing & Extending

### Adding a New Workload Type
1. Add enum to `workload_type_t` in matmul.c
2. Implement kernel function (e.g., `kernel_custom()`)
3. Update compute_thread switch statement
4. Update CLI parsing
5. Test with `./matmul --workload custom --tiles 1000`
6. Profile with `perf stat`
7. Document in WORKLOAD_ANALYSIS.md

See [.github/copilot-instructions.md](../.github/copilot-instructions.md#common-modifications) for detailed guidance.

### Modifying the Pipeline
- Ring buffer capacity: Edit `--in-depth`, `--out-depth` CLI
- Thread sleeps: Edit `--reader-sleep-ns`, `--writer-sleep-ns` CLI
- Trace format: Edit `emit_trace()` call signature (requires adapter update)
- Memory alignment: Change `size_t align = 64;` (cache-line specific)

---

## License

SPDX-License-Identifier: Apache-2.0

---

## Contact & Support

For questions about:
- **Usage:** See QUICK_REFERENCE.md
- **Workload details:** See WORKLOAD_ANALYSIS.md
- **Trace parsing:** See TRACE_ANALYSIS_EXAMPLES.md
- **Code modifications:** See .github/copilot-instructions.md

---

## Summary

The **SIT CPU Baseline** is a lightweight, self-contained workload generator for CPU performance testing. It provides:

✅ **Deterministic bottleneck injection** (underflow/overflow)  
✅ **Multiple compute kernels** (MAC, ALU, BRANCH, DRAM, streaming)  
✅ **Raw trace output** (microsecond-precision events)  
✅ **Lock-free SPSC pipeline** (cache-line aligned, no mutexes)  
✅ **Comprehensive documentation** (usage, analysis, integration)  

**Get started:** Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → Run `gcc -O2 -g -pthread matmul.c -o matmul` → Execute `./matmul --tile-elems 1024 --tiles 50000`

**For deep dives:** See workload performance in [WORKLOAD_ANALYSIS.md](WORKLOAD_ANALYSIS.md) and trace interpretation in [TRACE_ANALYSIS_EXAMPLES.md](TRACE_ANALYSIS_EXAMPLES.md).

