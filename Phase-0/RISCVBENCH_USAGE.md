# riscvbench CLI Usage

## Basic Command
```bash
riscvbench --target <cpu|spike> --workload <matmul|matmul_multicore> --workload_size <tiny|small|med|large> --time_us <window_size>
```

## Common Examples

### Single-core balanced workload
```bash
riscvbench --target cpu --workload matmul --workload_size small --time_us 256
```
Expected: sit_median ~0.5, residency_stall ~0%

### Multi-core (4 threads) balanced workload
```bash
riscvbench --target cpu --workload matmul_multicore --workload_size small --time_us 256 --compute-threads 4
```
Expected: sit_median higher due to parallelism, residency_idle ~30-40%

### Input underflow (slow reader)
```bash
riscvbench --target cpu --workload matmul --workload_size small --time_us 256 --underflow
```
Expected: sit_median ~0.04, residency_stall ~75%

### Output overflow (slow writer)
```bash
riscvbench --target cpu --workload matmul --workload_size small --time_us 256 --overflow
```
Expected: sit_median ~0.10, residency_stall ~70%

### Multi-core with underflow bottleneck
```bash
riscvbench --target cpu --workload matmul_multicore --workload_size med --time_us 256 --compute-threads 4 --underflow
```
Shows how multiple cores contend on shared input ring.

### Larger workload
```bash
riscvbench --target cpu --workload matmul --workload_size large --time_us 512
```

## Output Location
Results saved to:
```
Phase-1/runs/cpu/matmul{_multicore}/{size}/export/summary_v1.json
Phase-1/runs/cpu/matmul{_multicore}/{size}/windows.csv
```

View metrics:
```bash
cat Phase-1/runs/cpu/matmul/small/export/summary_v1.json | python3 -m json.tool | grep -E "sit_|residency_"
```

## Parameters

| Flag | Values | Default | Purpose |
|------|--------|---------|---------|
| `--target` | cpu, spike | required | Target platform |
| `--workload` | matmul, matmul_multicore | required | Workload type |
| `--workload_size` | tiny, small, med, large | required | Workload scale |
| `--time_us` | integer | required | SIT window size (microseconds) |
| `--compute-threads` | integer | 1 | Number of parallel compute threads (matmul_multicore only) |
| `--underflow` | - | off | Force input bottleneck (slow reader) |
| `--overflow` | - | off | Force output bottleneck (slow writer) |
| `--tile-elems` | integer | 1024 | Matmul tile size |
| `--tiles` | integer | auto | Number of tiles (auto-scaled by workload_size) |
| `--reader-sleep-ns` | integer | 0 | Reader delay (ns) |
| `--writer-sleep-ns` | integer | 0 | Writer delay (ns) |

## Output Metrics

- **sit_median**: Sustained throughput (0-1, higher is better)
- **sit_p95**: 95th percentile throughput  
- **residency_active**: Percent doing useful work
- **residency_idle**: Percent spinning/yielding (overhead)
- **residency_stall**: Percent blocked waiting (bottleneck indicator)

## Multi-Core Dataset Scaling

Matmul normally processes tiles sequentially via single compute thread. Matmul_multicore allows parallel compute with:
- 2 threads: ~2× throughput, more underflow/overflow contention on ring
- 4 threads: ~3-4× throughput depending on ring depths
- Larger ring depths needed: `--in-depth N` and `--out-depth N` scale with thread count
