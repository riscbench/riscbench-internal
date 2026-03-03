# Phase-2 Spike Documentation and Runbook

This document explains exactly what the Spike docs contain and how to use them to implement or validate Spike-related Phase-2 changes.

## What Spike Contributes in Phase-2

- Reference adapter path for marker-driven residency behavior.
- High-event trace source used for parser and invariant validation.
- Primary target used in many golden-trace workflows.

## Code Paths Covered by Spike Docs

- Runner dispatch: `Phase-2/riscvbench.py` (`main()` spike branch)
- Adapter: `Phase-2/adapters/spike_adapter.py`
  - `SpikePlatformAdapter._iter_events()`
  - `SpikePlatformAdapter._collect_core_timeline()`
  - `build_state_intervals()`
  - `build_residency_intervals()`
  - `export_baseline_csvs()`
- Contract validators: `Phase-2/ingest/ingest_api.py`
  - `validate_state_df()`
  - `validate_resid_df()`
- Shared engine: `Phase-2/sit_engine_phase1.py` (`main()`)

## How To Run Spike

```bash
cd Phase-2
python3 riscvbench.py \
  --target spike \
  --workload alu \
  --workload_size small \
  --time_us 256 \
  --expected-work-rate 1.0 \
  --pk /absolute/path/to/pk
```

Expected artifacts in `runs/spike/alu/small/`:

- `inputs/state_intervals.csv`
- `inputs/residency_intervals.csv`
- `run_windows.csv`
- `run_summary.json`
- `adapter_meta.json`

## Required Validation Gates

```bash
python3 tests/check_invariants.py --windows runs/spike/alu/small/run_windows.csv
python3 tests/check_adapter_fixtures.py
python3 tests/check_determinism.py --targets spike --workload alu --workload-size small --pk /absolute/path/to/pk
```

## Spike Deliverable Files and What They Explain

- [deliverables/01_Spike_README.tex](deliverables/01_Spike_README.tex)
  - Why README is a control-plane deliverable and how it maps to implementation entrypoints.

- [deliverables/02_Spike_Adapter.tex](deliverables/02_Spike_Adapter.tex)
  - Adapter behavior, parser-to-contract conversion, and function-level flow.

- [deliverables/03_Spike_Adapter_Contract.tex](deliverables/03_Spike_Adapter_Contract.tex)
  - Boundary rules: what adapter may do vs what engine must own.

- [deliverables/04_Spike_Golden_Microkernel_Traces.tex](deliverables/04_Spike_Golden_Microkernel_Traces.tex)
  - Golden trace generation and reproducibility constraints.

- [deliverables/05_Spike_Golden_Output_Artifacts.tex](deliverables/05_Spike_Golden_Output_Artifacts.tex)
  - Expected replay outputs and deterministic artifact checks.

- [deliverables/07_Spike_Parameter_Sweep_Runner.tex](deliverables/07_Spike_Parameter_Sweep_Runner.tex)
  - Sweep matrix execution and metadata handling.

- [deliverables/08_Spike_Dataset_Governance.tex](deliverables/08_Spike_Dataset_Governance.tex)
  - Dataset provenance/versioning process and change-control expectations.

- [deliverables/09_Spike_CI_Integration.tex](deliverables/09_Spike_CI_Integration.tex)
  - CI gate strategy and deterministic regression behavior.
