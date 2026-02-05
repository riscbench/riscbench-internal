# RISCBench Phase-1: SIT Engine (toy, hardware-agnostic)

This repository contains a Phase-1 implementation of a Sustained Instantaneous Throughput (SIT) engine with:
- normalized trace ingestion API (adapter contract)
- baseline adapter (reference ingestion path)
- windowing + boundary-correct overlap logic
- optional residency gating (no accumulation outside residency)
- stable output schema v1 (validated)
- validation suite + golden runner

## Quickstart

### 1) Run engine directly (Phase-1 baseline)
No residency:
```bash
python sit_engine_phase1.py --trace datasets/traces/trace_A_single_residency.csv --window-us 256 --out-prefix out/A_base
```

With residency gating:
```bash
python sit_engine_phase1.py --trace datasets/traces/trace_A_single_residency.csv --residency datasets/residency/partial.csv --window-us 256 --out-prefix out/A_partial
```

Outputs:
- `<prefix>_windows.csv`
- `<prefix>_summary.json`

### 2) Run via CLI pipeline (ingest → classify → export)
```bash
python cli.py ingest --trace datasets/traces/trace_A_single_residency.csv --out runs/A
python cli.py classify --in runs/A --window-us 256 --residency datasets/residency/partial.csv
python cli.py export --in runs/A --schema v1
```

Artifacts:
- `runs/A/manifest.json`
- `runs/A/windows.csv`
- `runs/A/summary.json`
- `runs/A/export/windows_v1.csv`
- `runs/A/export/summary_v1.json`

## Validation (golden suite)

Run invariants on a single output:
```bash
python tests/check_invariants.py --windows out/A_partial_windows.csv --mode partial --window-us 256
```

Run all traces/masks listed in `datasets/manifest.json`:
```bash
python tests/run_golden_suite.py --outdir golden_out
```

## Deliverable mapping (Phase-1)

### 1. SIT Engine core
- `sit_engine_phase1.py` (engine logic; consumes normalized events via adapter)

### 2. Time and windowing
- `split_interval_into_windows()` in `sit_engine_phase1.py` (ε boundary correctness)

### 3. Residency model
- residency gating + `resident_us` normalization in `sit_engine_phase1.py`

### 4. Trace ingestion API
- `ingest/ingest_api.py` (normalized schema + validators + TraceAdapter contract)

### 5. Baseline adapter
- `adapters/baseline_adapter.py` (CSV reference adapter; validates via ingest API)

### 6. Output schema v1
- `schemas/v1.py` (schema version + windows/summary validators)
- enforced by the engine prior to export

### 7. Validation suite
- `tests/check_invariants.py` (semantic invariants)
- `tests/run_golden_suite.py` (runner over datasets/manifest.json)

### 8. Reference datasets
- `datasets/traces/` (golden traces)
- `datasets/residency/` (mask files)
- `datasets/manifest.json` (pinned dataset bundle)

### 9. CLI pipeline
- `cli.py` (ingest → classify → export)

## Spike + CPU workloads (riscvbench.py)

You can generate Spike traces and run them through the same Phase-1 ingest/classify/export
pipeline. Shared workloads for both CPU and Spike include `alu`, `branch`, `memory`, `memread`,
`memwrite`, `memcpy`, and `hello`. Both targets support `matmul` and `matmul_multicore` as
long as the `matmul_multicore.c` source is available. For a Spike matmul workload:

```bash
python riscvbench.py \
  --target spike \
  --workload matmul \
  --workload_size small \
  --time_us 256 \
  --pk /path/to/riscv-pk/build/pk
```

This will emit outputs under `runs/spike/matmul/<size>/` including `summary.json` and
`windows.csv` for analysis. The generated Spike residency intervals include a `resident=1`
marker to match the CPU-style residency CSV schema. The CPU target supports `matmul` and
`matmul_multicore` with detailed traces, and also supports the shared simple workloads
by emitting a single active interval based on wall time.

## Notes
- `riscvbench` requires Python 3.9+ (see `pyproject.toml`). If you use a venv, make sure it is created with Python 3.9+ and upgrade `pip` before installing editable builds:
  ```bash
  python3.9 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip setuptools wheel
  pip install -e .
  ```
- `riscvbench` supports `--cores` (alias for `--compute-threads`) and `--events-max` (cap events for both Spike and CPU parsing). Use `riscvbench --help` after reinstalling to confirm the flags.
- If `riscvbench --help` still shows old flags after reinstalling, verify which module is being loaded and reinstall in the same venv:
  ```bash
  which riscvbench
  python -c "import riscvbench,inspect; print(riscvbench.__file__)"
  pip uninstall -y riscvbench
  pip install -e .
  hash -r
  ```
- Editable installs rely on the `-e` flag. A command like `pip install e .` installs a package literally named `e` and does not install this repo.
- Baseline adapter uses CSV only as a Phase-1 deterministic reference.
- Future phases can add new adapters without changing the engine contract.


### Practical cross-target workloads (Spike + CPU with similar parsed event counts)
If you want practical runs on **both Spike and CPU** with a shared parser cap and similar event
counts, use `run_cross_target_suite.py`.

Defaults now include:
- workloads: `branch`, `memory`, `memread`, `memwrite`, `memcpy`, `matmul`, `matmul_multicore`
- `--events-max 47000`
- `--match-mode similar` with `--similarity-pct 0.05` (5% tolerance)

```bash
python run_cross_target_suite.py \
  --pk /path/to/riscv-pk/build/pk \
  --workload-size small \
  --time-us 256
```

If you want strict equality (exact same count and exact `events-max`), use:

```bash
python run_cross_target_suite.py \
  --pk /path/to/riscv-pk/build/pk \
  --workload-size small \
  --time-us 256 \
  --events-max 47000 \
  --match-mode exact
```

Important: for `matmul_multicore`, Spike still uses a single-core `matmul` fallback to generate
instruction traces (not true pthread multicore execution). This workload is included for practical
comparison and event-volume alignment, not architectural multicore equivalence.

### Making SIT less likely to clamp at 1.0
For CPU workloads, introduce queue pressure and tighten normalization so windows are not always
perfectly active:

```bash
python riscvbench.py \
  --target cpu \
  --workload matmul_multicore \
  --workload_size small \
  --time_us 256 \
  --cores 4 \
  --events-max 2000 \
  --underflow --overflow \
  --reader-sleep-ns 2000 \
  --writer-sleep-ns 5000 \
  --expected-work-rate 1.15
```

### SIT normalization + debug
SIT is computed per resident window. If the input trace includes `work_done` (e.g., tiles completed), the engine normalizes
per-window work rate against `--expected-work-rate` (default `1.0` work/us). Otherwise it falls back to the active fraction
within resident time. Use `--debug-sit` (or `riscvbench --debug-sit`) to print raw components such as `resident_us`,
`idle_us`, `stall_us`, work totals, expected work rate, and min/mean/max of raw vs clamped SIT values.
