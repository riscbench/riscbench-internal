# Bundle Architecture

This bundle is organized into three layers that match the intended execution flow.

See also:

- `WORKFLOW_ARCHITECTURE.md`

## Device Handler

Path:

- `device_handler/`

Responsibilities:

- orchestration entrypoint
- platform selection
- workload injection
- environment setup
- simulator toolchain resolution
- backend invocation

Main files:

- `device_handler/orchestrator.py`
- `device_handler/backend_runner.py`
- `device_handler/simulator_toolchain_manager.py`
- `device_handler/README.md`

## SIT Classifier

Path:

- `sit_classifier/`

Responsibilities:

- parse platform-specific raw traces
- map events into `active` / `stall` / `idle`
- emit normalized interval CSVs

Main files:

- `sit_classifier/adapters/`
- `sit_classifier/ingest_api.py`
- `sit_classifier/workload_calibration.py`
- `sit_classifier/README.md`

## Result Handler

Path:

- `result_handler/`

Responsibilities:

- consume normalized interval CSVs
- run SIT computation
- emit windows, summaries, and exported artifacts

Main files:

- `result_handler/sit_engine_phase1.py`
- `result_handler/cli.py`
- `result_handler/README.md`

## Data Flow

1. Device handler chooses a target and prepares inputs.
2. SIT classifier converts backend/device traces into:
   - `state_intervals.csv`
   - `residency_intervals.csv`
3. Result handler computes:
   - `run_windows.csv`
   - `run_summary.json`
   - exported summaries

For the full folder tree and diagram view, use `WORKFLOW_ARCHITECTURE.md`.

## Extension Rules

- New hardware/device logic belongs under `device_handler/`.
- New simulator adapters belong under `sit_classifier/adapters/`.
- New SIT/report logic belongs under `result_handler/`.
- Runtime Python code should live under the three layer folders rather than at the repo root.
