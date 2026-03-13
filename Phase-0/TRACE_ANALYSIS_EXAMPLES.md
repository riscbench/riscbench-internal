# Trace Analysis Examples & Patterns

## Overview

The matmul.c workload emits raw trace events with microsecond timestamps. This guide shows how to interpret and analyze these traces.

## Trace Format

Raw event stream: `ts_us=<timestamp> thread=<id> event=<EVENT> [key=value ...]`

**Standard events:**
```
ts_us=1000  thread=1  event=COMPUTE_WORK  tiles_done=1 uf=0 of=0
ts_us=2000  thread=1  event=COMPUTE_WORK  tiles_done=2 uf=0 of=0
ts_us=3000  thread=1  event=INPUT_UNDERFLOW_DETECTED  uf_count=1
ts_us=3500  thread=1  event=COMPUTE_WORK  tiles_done=3 uf=1 of=0
ts_us=4000  thread=1  event=OUTPUT_OVERFLOW_DETECTED  of_count=1
ts_us=5000  thread=1  event=COMPUTE_WORK  tiles_done=4 uf=1 of=1
```

---

## Example 1: Balanced Pipeline (No Bottlenecks)

### Generation
```bash
./matmul --tile-elems 256 --tiles 100 --in-depth 2 --out-depth 2 \
         --trace results/balanced.trace
```

### Expected Output
```
tiles=100 tile_elems=256 in_depth=2 out_depth=2
tiles_read=100 tiles_done=100 tiles_written=100
input_underflow=0 output_overflow=5
checksum=12345.678
```

### Trace Pattern
```
ts_us=1000  thread=1  event=COMPUTE_WORK  tiles_done=1 uf=0 of=0
ts_us=2000  thread=1  event=COMPUTE_WORK  tiles_done=2 uf=0 of=0
ts_us=3000  thread=1  event=COMPUTE_WORK  tiles_done=3 uf=0 of=0
...
ts_us=100000  thread=1  event=COMPUTE_WORK  tiles_done=100 uf=0 of=0
```

### Analysis
- **No underflow events:** Reader keeping up with compute
- **Minimal overflow events (5):** Occasional backpressure from writer
- **Regular COMPUTE_WORK spacing:** Consistent compute time per tile
- **Interpretation:** Pipeline is balanced; reader/compute/writer roughly matched

### Key Metrics
```
Underflow percentage:  0%      (reader not slow)
Overflow percentage:   5%      (writer occasionally slow)
Compute efficiency:   95%      (5% time spent stalled)
Avg tile time:       1000 µs   (100000 µs / 100 tiles)
```

---

## Example 2: Input Underflow (Reader Too Slow)

### Generation
```bash
./matmul --tile-elems 256 --tiles 100 --reader-sleep-ns 3000 \
         --trace results/underflow.trace
```

### Expected Output
```
tiles=100 tile_elems=256
tiles_read=100 tiles_done=100 tiles_written=100
input_underflow=2547    ⚠️ MANY underflows
output_overflow=3
checksum=12345.678
```

### Trace Pattern
```
ts_us=1000  thread=1  event=COMPUTE_WORK  tiles_done=1 uf=0 of=0
ts_us=2000  thread=1  event=INPUT_UNDERFLOW_DETECTED  uf_count=1
ts_us=2100  thread=1  event=INPUT_UNDERFLOW_DETECTED  uf_count=2
ts_us=2200  thread=1  event=INPUT_UNDERFLOW_DETECTED  uf_count=3
...  [many underflow detections]
ts_us=7000  thread=1  event=COMPUTE_WORK  tiles_done=2 uf=2547 of=0
ts_us=8000  thread=1  event=COMPUTE_WORK  tiles_done=3 uf=2547 of=0
```

### Analysis
- **Many underflow events:** Compute repeatedly stalls waiting for input
- **Gaps between COMPUTE_WORK:** Compute thread spinning (wasted cycles)
- **Increasing uf_count:** Cumulative underflow counter reaches 2547
- **Interpretation:** Reader is too slow (3000 ns sleep); compute runs out of work

### Bottleneck Signature
```
Pattern: [UNDERFLOW_DETECTED × N] → [COMPUTE_WORK] → [UNDERFLOW_DETECTED × N] ...
Cause:   Reader can't keep up with compute
Impact:  Compute thread ~50% idle (spinning on empty input ring)
Fix:     Increase reader throughput or decrease compute speed
```

### Root Cause Analysis

**Timeline:**
1. Reader loads tile at t=0, puts in input ring
2. Compute pops at t=1, starts work
3. Reader delayed by 3000ns sleep, next tile arrives at t=3000
4. But compute needs next tile at t=2000 → input ring empty
5. Compute spins, emitting underflow events until next tile arrives
6. Reader finally delivers at t=3000 → compute resumes

**Formula:**
```
Underflow count ≈ (reader_sleep_ns / compute_time) × num_tiles
Compute efficiency ≈ 1 - (underflow_detections / compute_iterations)
```

---

## Example 3: Output Overflow (Writer Too Slow)

### Generation
```bash
./matmul --tile-elems 256 --tiles 100 --writer-sleep-ns 5000 \
         --trace results/overflow.trace
```

### Expected Output
```
tiles=100 tile_elems=256
tiles_read=100 tiles_done=100 tiles_written=100
input_underflow=0
output_overflow=4821    ⚠️ MANY overflows
checksum=12345.678
```

### Trace Pattern
```
ts_us=1000  thread=1  event=COMPUTE_WORK  tiles_done=1 uf=0 of=0
ts_us=2000  thread=1  event=COMPUTE_WORK  tiles_done=2 uf=0 of=0
ts_us=3000  thread=1  event=OUTPUT_OVERFLOW_DETECTED  of_count=1
ts_us=3100  thread=1  event=OUTPUT_OVERFLOW_DETECTED  of_count=2
ts_us=3200  thread=1  event=OUTPUT_OVERFLOW_DETECTED  of_count=3
...  [many overflow detections]
ts_us=8000  thread=1  event=COMPUTE_WORK  tiles_done=3 uf=0 of=4821
ts_us=9000  thread=1  event=COMPUTE_WORK  tiles_done=4 uf=0 of=4821
```

### Analysis
- **Many overflow events:** Compute stalls trying to push full output ring
- **Compute makes progress, then stalls:** Output buffer fills up
- **of_count increases:** Cumulative overflow counter reaches 4821
- **Interpretation:** Writer is too slow; output ring backpressures compute

### Bottleneck Signature
```
Pattern: [COMPUTE_WORK × N] → [OVERFLOW_DETECTED × M] → [COMPUTE_WORK] ...
Cause:   Writer can't drain output ring fast enough
Impact:  Compute thread ~50% blocked on full output ring
Fix:     Increase writer throughput or increase out-depth
```

### Root Cause Analysis

**Timeline:**
1. Compute writes result to output ring at t=1
2. Compute writes result at t=2 (output ring now has 2 items, capacity=2)
3. Compute tries to write at t=3, but output ring FULL (can't push)
4. Writer delayed by 5000ns sleep, drains ring slowly
5. Output ring remains full until writer catches up
6. Compute stalls, emitting overflow events
7. Eventually writer drains (after t=5000), compute resumes

**Formula:**
```
Overflow count ≈ (writer_sleep_ns / compute_time) × num_tiles × out_depth
Compute efficiency ≈ 1 - (overflow_detections / compute_iterations)
```

---

## Example 4: Cascading Bottleneck (Underflow + Overflow)

### Generation
```bash
./matmul --tile-elems 256 --tiles 100 \
         --reader-sleep-ns 1500 --writer-sleep-ns 2000 \
         --trace results/cascading.trace
```

### Expected Output
```
tiles=100 tile_elems=256
tiles_read=100 tiles_done=100 tiles_written=100
input_underflow=450
output_overflow=720
checksum=12345.678
```

### Trace Pattern
```
ts_us=1000  thread=1  event=COMPUTE_WORK  tiles_done=1 uf=0 of=0
ts_us=2000  thread=1  event=INPUT_UNDERFLOW_DETECTED  uf_count=1
ts_us=2100  thread=1  event=INPUT_UNDERFLOW_DETECTED  uf_count=2
ts_us=3000  thread=1  event=COMPUTE_WORK  tiles_done=2 uf=2 of=0
ts_us=4000  thread=1  event=OUTPUT_OVERFLOW_DETECTED  of_count=1
ts_us=4100  thread=1  event=OUTPUT_OVERFLOW_DETECTED  of_count=2
ts_us=5000  thread=1  event=COMPUTE_WORK  tiles_done=3 uf=2 of=2
ts_us=6000  thread=1  event=INPUT_UNDERFLOW_DETECTED  uf_count=3
...
```

### Analysis
- **Both underflow and overflow events present:** Pipeline is unbalanced both ways
- **Alternating bottlenecks:** Sometimes stalled waiting for input, sometimes stalled on full output
- **Lower overall efficiency:** Compute thread constantly switching between two bottlenecks
- **Interpretation:** Reader and writer speeds don't match; compute is at mercy of both

### Optimization Opportunity
```
Current: underflow=450, overflow=720
Insight: Both bottlenecks present → neither can be fixed alone
Option 1: Increase reader AND writer speed
Option 2: Increase ring depths to absorb variability
Option 3: Rebalance compute time to match reader/writer
```

---

## Example 5: Memory-Heavy Workload (DRAM_READ)

### Generation
```bash
./matmul --tile-elems 256 --tiles 100 --workload dram_read \
         --trace results/dram_read.trace
```

### Expected Output
```
tiles=100 tile_elems=256
tiles_read=100 tiles_done=100 tiles_written=100
input_underflow=0
output_overflow=45
checksum=65412.123
```

### Trace Pattern
```
ts_us=1000  thread=1  event=COMPUTE_WORK  tiles_done=1 uf=0 of=0
ts_us=3000  thread=1  event=COMPUTE_WORK  tiles_done=2 uf=0 of=0    ⚠️ 2µs per tile
ts_us=5000  thread=1  event=COMPUTE_WORK  tiles_done=3 uf=0 of=0    (vs 1µs for MAC)
ts_us=6500  thread=1  event=OUTPUT_OVERFLOW_DETECTED  of_count=1
...
ts_us=250000  thread=1  event=COMPUTE_WORK  tiles_done=100 uf=0 of=45
```

### Analysis
- **Longer compute time (2µs vs 1µs):** Extra memory reads slow compute
- **Consistent timing:** No underflow events (reader fast enough)
- **Some overflow events (45):** Writer still slightly slower
- **Interpretation:** DRAM_READ workload is compute-limited by memory access

### Comparison Table
```
Workload     │ Time/Tile │ Total Time │ Underflow │ Overflow │ Bottleneck
─────────────┼───────────┼────────────┼───────────┼──────────┼────────────
MAC          │ 1.0 µs    │ 100 µs     │ 0         │ 5        │ Writer
ALU          │ 1.2 µs    │ 120 µs     │ 0         │ 12       │ Writer
BRANCH       │ 1.05 µs   │ 105 µs     │ 0         │ 8        │ Writer
DRAM_READ    │ 2.0 µs    │ 200 µs     │ 0         │ 45       │ Reader + Writer
DRAM_WRITE   │ 1.0 µs    │ 100 µs     │ 0         │ 6        │ Writer
```

---

## Example 6: Extracting Insights from Trace Files

### Quick Statistics
```bash
# Count each event type
grep -c "COMPUTE_WORK" results/balanced.trace
grep -c "INPUT_UNDERFLOW" results/balanced.trace
grep -c "OUTPUT_OVERFLOW" results/balanced.trace

# Find max timestamp
tail -1 results/balanced.trace | cut -d' ' -f1

# Average compute time per tile
awk '/COMPUTE_WORK/ {
    if (prev) print $1 - prev; 
    prev=$1
}' results/balanced.trace | awk '{sum+=$1; n++} END {print sum/n}'
```

### Parse Bottleneck Intensity
```bash
# Get underflow and overflow final counts
awk '/COMPUTE_WORK/ {
    match($0, /uf=([^ ]+)/, a); uf=a[1]
    match($0, /of=([^ ]+)/, b); of=b[1]
} END {
    print "Final underflow count:", uf
    print "Final overflow count:", of
    print "Total stalls:", uf+of
}' results/cascading.trace
```

### Timeline Analysis
```bash
# Generate CSV: timestamp, event, uf_count, of_count
awk '{
    match($0, /ts_us=([^ ]+)/, ts);
    match($0, /event=([^ ]+)/, ev);
    match($0, /uf_count=([^ ]+)/, uf);
    match($0, /of_count=([^ ]+)/, of);
    if (uf[1] == "") uf[1] = prev_uf; else prev_uf = uf[1];
    if (of[1] == "") of[1] = prev_of; else prev_of = of[1];
    print ts[1] "," ev[1] "," uf[1] "," of[1]
}' results/bottleneck.trace > analysis.csv
```

---

## Adapter Integration Checklist

When writing a trace adapter to consume these raw events:

- [ ] Parse `ts_us=<timestamp>` → microsecond clock
- [ ] Parse `event=<EVENT>` → event type (COMPUTE_WORK, UNDERFLOW, OVERFLOW)
- [ ] Extract key-value pairs → `tiles_done=N`, `uf_count=N`, `of_count=N`
- [ ] Correlate underflow events → Compute thread stalled on input ring
- [ ] Correlate overflow events → Compute thread stalled on output ring
- [ ] Calculate stall intervals → `timestamp_of_overflow - timestamp_of_previous_compute_work`
- [ ] Populate SIT residency flags → Thread state (compute, underflow, overflow)
- [ ] Build timeline → Residency histogram per thread per microsecond bucket
- [ ] Validate → Sum of underflow stalls + overflow stalls < total time

**Pseudo-code:**
```python
for line in trace_file:
    ts, thread, event, *fields = parse_line(line)
    
    if event == "COMPUTE_WORK":
        residency[ts] = "COMPUTE"    # Thread making progress
        prev_compute_ts = ts
    
    elif event == "INPUT_UNDERFLOW_DETECTED":
        residency[ts] = "STALLED_INPUT"  # Thread waiting
    
    elif event == "OUTPUT_OVERFLOW_DETECTED":
        residency[ts] = "STALLED_OUTPUT"  # Thread blocked
    
    # Build histogram
    histogram[ts // bucket_size] += 1

# SIT engine can now report:
# - Compute residency %
# - Input stall residency %
# - Output stall residency %
# - Timeline for visualization
```

---

## Performance Insights from Traces

### Metric: Underflow Ratio
```
underflow_ratio = input_underflow_count / compute_iterations
```
- 0% = Reader fast enough
- 10%+ = Reader is bottleneck
- 50%+ = Reader catastrophically slow

### Metric: Overflow Ratio
```
overflow_ratio = output_overflow_count / compute_iterations
```
- 0% = Writer fast enough
- 10%+ = Writer is bottleneck
- 50%+ = Writer catastrophically slow

### Metric: Pipeline Efficiency
```
efficiency = 1 - (underflow_count + overflow_count) / (compute_iterations × 1000)
```
- >95% = Well-balanced
- 80-95% = Some bottleneck
- <80% = Severe bottleneck

### Metric: Compute Throughput
```
throughput = tiles_done / (max_timestamp_us / 1_000_000)  [tiles/sec]
```
- Compare across workloads and bottleneck scenarios
- DRAM_READ should show ~2× lower throughput than MAC

---

## Files

- `results/balanced.trace` - No bottlenecks
- `results/underflow.trace` - Reader too slow
- `results/overflow.trace` - Writer too slow
- `results/cascading.trace` - Both slow
- `results/*/` - Results directory for custom traces

