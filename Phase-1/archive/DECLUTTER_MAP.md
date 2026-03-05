# Phase-1 Declutter Map (2026-02-23)

## Active root kept for pipeline
- `cli.py`, `sit_engine_phase1.py`, `riscvbench.py`
- `adapters/`, `ingest/`, `schema/`, `datasets/`, `tests/`, `runs/`

## Archived from active root
- `golden_out/` -> `archive/reference_outputs/golden_out_2026-02-23/`
- `traces/` -> `archive/reference_traces/traces_legacy_2026-02-23/`
- `riscvbench.egg-info/` -> `archive/non_pipeline_artifacts/packaging_metadata/riscvbench.egg-info/`
- `sit_engine.egg-info/` -> `archive/non_pipeline_artifacts/packaging_metadata/sit_engine.egg-info/`

## Reorganized (root -> structured folders)
- `GENERALIZATION.md` -> `docs/guides/GENERALIZATION.md`
- `PHASE1_PHASE2_STATUS.md` -> `docs/status/PHASE1_PHASE2_STATUS.md`
- `Commands.txt` -> `docs/runbooks/Commands.txt`
- `matmul.c` -> `workloads/matmul.c`
- `matmul_multicore.c` -> `workloads/matmul_multicore.c`

## Archived demo runs
- `runs/A/` -> `archive/experimental_runs/2026-02-23/A/`
- `runs/demoA/` -> `archive/experimental_runs/2026-02-23/demoA/`
- `runs/spike/` -> `archive/experimental_runs/2026-02-23/spike/`
- `runs/cpu/alu/` -> `archive/experimental_runs/2026-02-23/alu/`
- `runs/alu/` -> `archive/experimental_runs/2026-02-23/alu_from_runs_root/`

## Restore examples
- `mv Phase-1/archive/reference_outputs/golden_out_2026-02-23 Phase-1/golden_out`
- `mv Phase-1/archive/reference_traces/traces_legacy_2026-02-23 Phase-1/traces`
- `mv Phase-1/archive/experimental_runs/2026-02-23/A Phase-1/runs/A`
- `mv Phase-1/archive/experimental_runs/2026-02-23/demoA Phase-1/runs/demoA`
- `mv Phase-1/docs/guides/GENERALIZATION.md Phase-1/GENERALIZATION.md`
- `mv Phase-1/docs/status/PHASE1_PHASE2_STATUS.md Phase-1/PHASE1_PHASE2_STATUS.md`
- `mv Phase-1/docs/runbooks/Commands.txt Phase-1/Commands.txt`
- `mv Phase-1/workloads/matmul.c Phase-1/matmul.c`
- `mv Phase-1/workloads/matmul_multicore.c Phase-1/matmul_multicore.c`
