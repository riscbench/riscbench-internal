# Phase-2 QEMU Documentation and Runbook

This document explains what the QEMU docs cover and how to use them for implementation and validation.

## What QEMU Contributes in Phase-2

- Fast secondary backend for adapter-contract verification.
- Determinism and parser-stability validation on a non-Spike trace source.
- Functional/emulation signal source (not cycle-accurate hardware timing).

## Code Paths Covered by QEMU Docs

- Runner dispatch: `Phase-2/riscvbench.py` (`main()` qemu branch)
- Adapter: `Phase-2/adapters/qemu_adapter.py`
  - `QemuPlatformAdapter._iter_events()`
  - `QemuPlatformAdapter._collect_core_timeline()`
  - `build_state_intervals()`
  - `build_residency_intervals()`
  - `export_baseline_csvs()`
- Contract validators: `Phase-2/ingest/ingest_api.py`
- Shared engine: `Phase-2/sit_engine_phase1.py`

## How To Run QEMU

```bash
cd Phase-2
python3 riscvbench.py \
  --target qemu \
  --workload alu \
  --workload_size small \
  --time_us 256 \
  --expected-work-rate 1.0 \
  --qemu-bin qemu-riscv64 \
  --qemu-cc riscv64-linux-gnu-gcc
```

If the workload exits non-zero but generated a valid trace, use:

```bash
--allow-nonzero-exit
```

Expected artifacts in `runs/qemu/alu/small/`:

- `inputs/state_intervals.csv`
- `inputs/residency_intervals.csv`
- `run_windows.csv`
- `run_summary.json`
- `adapter_meta.json`

## Required Validation Gates

```bash
python3 tests/check_invariants.py --windows runs/qemu/alu/small/run_windows.csv
python3 tests/check_adapter_fixtures.py
python3 tests/check_qemu_exit_policy.py
python3 tests/check_determinism.py --targets qemu --workload alu --workload-size small --allow-nonzero-exit
```

## QEMU Sweep Runner + Common SIT Visualization

Run a QEMU size/flag sweep (same matrix style as Spike):

```bash
cd Phase-2
python3 sweeps/run_param_sweep.py --config sweeps/sweep_config_qemu_example.json
```

Then visualize sweep outputs and emit a line chart like the common SIT plot:

```bash
python3 sweeps/visualize_sweep_results.py \
  --results-dir sweeps/results/<timestamp> \
  --x-field workload_size \
  --group-field flag_mode
```

Primary output:

- `sweeps/results/<timestamp>/plots/common_sit_median_by_workload_size.svg`

## QEMU Deliverable Files and What They Explain

- [deliverables/01_QEMU_README.tex](deliverables/01_QEMU_README.tex)
  - Scope and control-plane documentation role for QEMU work.

- [deliverables/02_QEMU_Adapter.tex](deliverables/02_QEMU_Adapter.tex)
  - Parser normalization behavior and function-level design flow.

- [deliverables/03_QEMU_Adapter_Contract.tex](deliverables/03_QEMU_Adapter_Contract.tex)
  - Contract conformance expectations and anti-leakage boundaries.

- [deliverables/04_QEMU_Golden_Microkernel_Traces.tex](deliverables/04_QEMU_Golden_Microkernel_Traces.tex)
  - Golden trace generation flow and reproducibility requirements.

- [deliverables/05_QEMU_Golden_Output_Artifacts.tex](deliverables/05_QEMU_Golden_Output_Artifacts.tex)
  - Deterministic outputs and replay artifact expectations.

- [deliverables/07_QEMU_Parameter_Sweep_Runner.tex](deliverables/07_QEMU_Parameter_Sweep_Runner.tex)
  - Sweep execution mechanics and metadata boundaries.

- [deliverables/08_QEMU_Dataset_Governance.tex](deliverables/08_QEMU_Dataset_Governance.tex)
  - Dataset change governance and provenance requirements.

- [deliverables/09_QEMU_CI_Integration.tex](deliverables/09_QEMU_CI_Integration.tex)
  - CI gates, replay requirements, and regression handling.
