# All Targets Validation Command List

This is a single copy-paste runbook for:
- Phase-0 (Tenstorrent) parity validation
- CPU baseline runs
- Spike runs
- QEMU runs
- Golden suite and invariant checks

`riscvbench` runs are shown as CLI commands (no `python ...riscvbench.py` form).

## 0) Preconditions

Install `riscvbench` CLI (one time):

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline

pip3 install --user -e Phase-2
export PATH="$HOME/.local/bin:$PATH"
hash -r

which riscvbench
riscvbench --help
```

Important:
- `Phase-1` and `Phase-2` both expose a CLI named `riscvbench`.
- If you install both, whichever is installed last is what `riscvbench` points to.
- For target runs in this runbook, keep Phase-2 installed last.

Tool prerequisites by target:
- `cpu`: `gcc`
- `spike`: `spike`, `riscv64-unknown-elf-gcc`, valid `pk`
- `qemu`: `qemu-riscv64`, `riscv64-linux-gnu-gcc`

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline
command -v gcc
command -v spike || true
command -v riscv64-unknown-elf-gcc || true
command -v qemu-riscv64 || true
command -v riscv64-linux-gnu-gcc || true
riscvbench --help
```

For Spike runs, set your `pk` path:

```bash
export PK=/home/dev_srinidhi/riscv-isa-sim/riscv-pk/build/pk
```

## 1) Phase-0 (Tenstorrent) strict parity validation

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-1

python3 tests/run_golden_suite.py --outdir /tmp/phase1_golden_tt

python3 tests/check_phase0_parity.py \
  --windows /tmp/phase1_golden_tt/trace_F_phase0_wormhole_sample__base_windows.csv \
  --summary /tmp/phase1_golden_tt/trace_F_phase0_wormhole_sample__base_summary.json \
  --expected tests/fixtures/phase0_parity_expected.json
```

For the current Phase-0 Tenstorrent calibration table, TT ingest commands, plot commands, and baseline figure, see [`PHASE0_TENSTORRENT_BASELINE.md`](PHASE0_TENSTORRENT_BASELINE.md).

## 2) CPU baseline runs (RISCVBench CLI)

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

riscvbench --target cpu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0
riscvbench --target cpu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --branch-mispredict
riscvbench --target cpu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --cache-pressure
riscvbench --target cpu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --branch-mispredict --cache-pressure
```

## 3) Spike runs (RISCVBench CLI)

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

riscvbench --target spike --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --pk "$PK"
riscvbench --target spike --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --pk "$PK" --branch-mispredict
riscvbench --target spike --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --pk "$PK" --cache-pressure
riscvbench --target spike --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --pk "$PK" --branch-mispredict --cache-pressure
```

## 4) QEMU runs (RISCVBench CLI)

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

riscvbench --target qemu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --allow-nonzero-exit
riscvbench --target qemu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --branch-mispredict --allow-nonzero-exit
riscvbench --target qemu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --cache-pressure --allow-nonzero-exit
riscvbench --target qemu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --branch-mispredict --cache-pressure --allow-nonzero-exit
```

## 5) Golden matrix pipelines (validation + plots)

### Spike golden matrix

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

python3 tests/run_spike_golden_pipeline.py \
  --pk "$PK" \
  --workloads fm_loopback fm_mm fm_read fm_write matmul \
  --all-sizes \
  --emulated-flags none branch_mispredict cache_pressure both \
  --time-us 256 \
  --window-us 256 \
  --common-mode base \
  --outdir /tmp/golden_out_spike_matrix
```

### QEMU golden matrix

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

python3 tests/run_qemu_golden_pipeline.py \
  --workloads fm_loopback fm_mm fm_read fm_write matmul \
  --all-sizes \
  --emulated-flags none branch_mispredict cache_pressure both \
  --time-us 256 \
  --window-us 256 \
  --common-mode base \
  --allow-nonzero-exit \
  --outdir /tmp/golden_out_qemu_matrix
```

## 6) Replay golden suite from generated manifests

### Replay Spike manifest

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

python3 tests/run_golden_suite.py \
  --manifest /tmp/golden_out_spike_matrix/spike_manifest.json \
  --outdir /tmp/golden_out_spike_replay \
  --window-us 256
```

### Replay QEMU manifest

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

python3 tests/run_golden_suite.py \
  --manifest /tmp/golden_out_qemu_matrix/qemu_manifest.json \
  --outdir /tmp/golden_out_qemu_replay \
  --window-us 256
```

## 7) Invariant checks on target outputs

Run this pattern on any generated `*_windows.csv`:

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

python3 tests/check_invariants.py \
  --windows runs/spike/fm_mm/small/windows.csv \
  --mode base \
  --window-us 256

python3 tests/check_invariants.py \
  --windows runs/qemu/fm_mm/small/windows.csv \
  --mode base \
  --window-us 256

python3 tests/check_invariants.py \
  --windows runs/cpu/fm_mm/small/windows.csv \
  --mode base \
  --window-us 256
```

## 8) Optional one-command cross-target smoke

```bash
cd /home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2

python3 run_cross_target_suite.py \
  --targets cpu spike qemu \
  --workloads fm_loopback fm_mm fm_read fm_write matmul \
  --workload-size small \
  --time-us 256 \
  --expected-work-rate 1.0 \
  --pk "$PK" \
  --allow-nonzero-exit
```
