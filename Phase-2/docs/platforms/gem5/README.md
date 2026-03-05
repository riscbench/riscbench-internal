# Phase-2 gem5 Documentation and Runbook

This document explains what the gem5 docs cover and how to use them for implementation and validation.

## What gem5 Contributes in Phase-2

- Microarchitectural timing factors (cycle-modeled) backend for stall/residency behavior.
- Independent adapter path to test contract portability beyond Spike/QEMU.
- System-style validation for cross-target SIT consistency checks.

## Platform Factor Summary (gem5)

- Workload/orchestration factors: workload-driven waits, barriers, and residency-OFF intervals.
- Runtime/OS factors: runtime/system noise when present in the execution setup.
- Microarchitectural timing factors (cycle-modeled):
  - Cache hierarchy latency / miss penalties
  - Branch misprediction penalties
  - Pipeline stalls / contention
  - Memory system pressure (DRAM / NoC modeled)
- Measurement overhead: simulator instrumentation and profiling overhead.

Methodological note: Spike and QEMU do not model microarchitectural timing; gem5 and hardware platforms may.

## Code Paths Covered by gem5 Docs

- Runner dispatch: `Phase-2/riscvbench.py` (`main()` gem5 branch)
- Adapter: `Phase-2/adapters/gem5_adapter.py`
  - `Gem5PlatformAdapter._iter_events()` (exec mode)
  - `Gem5PlatformAdapter._collect_core_timeline()`
  - `build_state_intervals()`
  - `build_residency_intervals()`
  - `export_baseline_csvs()`
- gem5 config helper: `Phase-2/configs/gem5_se_periodic_stats.py`
- Contract validators: `Phase-2/ingest/ingest_api.py`
- Shared engine: `Phase-2/sit_engine_phase1.py`

## How To Run gem5

```bash
cd Phase-2
python3 riscvbench.py \
  --target gem5 \
  --workload alu \
  --workload_size small \
  --time_us 256 \
  --expected-work-rate 1.0 \
  --gem5-bin /absolute/path/to/gem5.opt \
  --gem5-cc riscv64-linux-gnu-gcc \
  --gem5-root /absolute/path/to/gem5
```

Expected artifacts in `runs/gem5/alu/small/`:

- `inputs/state_intervals.csv`
- `inputs/residency_intervals.csv`
- `run_windows.csv`
- `run_summary.json`
- `adapter_meta.json`

## Required Validation Gates

```bash
python3 tests/check_adapter_fixtures.py --fixtures gem5
python3 tests/check_invariants.py --windows runs/gem5/alu/small/run_windows.csv
python3 tests/check_determinism.py --targets gem5 --workload alu --workload-size small --gem5-bin /absolute/path/to/gem5.opt --gem5-cc riscv64-linux-gnu-gcc --gem5-root /absolute/path/to/gem5
bash tools/run_gem5_property_suite.sh
```

## gem5 Deliverable Files and What They Explain

- [deliverables/01_gem5_README.tex](deliverables/01_gem5_README.tex)
  - Scope role and reader guidance for gem5-related work.

- [deliverables/02_gem5_Adapter.tex](deliverables/02_gem5_Adapter.tex)
  - Adapter normalization behavior and function-level flow.

- [deliverables/03_gem5_Adapter_Contract.tex](deliverables/03_gem5_Adapter_Contract.tex)
  - Contract compliance and anti-leakage boundaries.

- [deliverables/04_gem5_Golden_Microkernel_Traces.tex](deliverables/04_gem5_Golden_Microkernel_Traces.tex)
  - Golden trace creation and reproducibility process.

- [deliverables/05_gem5_Golden_Output_Artifacts.tex](deliverables/05_gem5_Golden_Output_Artifacts.tex)
  - Replay output expectations and deterministic artifact requirements.

- [deliverables/07_gem5_Parameter_Sweep_Runner.tex](deliverables/07_gem5_Parameter_Sweep_Runner.tex)
  - Sweep execution path and metadata policy.

- [deliverables/08_gem5_Dataset_Governance.tex](deliverables/08_gem5_Dataset_Governance.tex)
  - Dataset governance, provenance, and versioning expectations.

- [deliverables/09_gem5_CI_Integration.tex](deliverables/09_gem5_CI_Integration.tex)
  - CI checks and deterministic failure behavior.
