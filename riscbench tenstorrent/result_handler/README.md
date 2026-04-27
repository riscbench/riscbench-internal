# Result Handler

This layer computes SIT from normalized state and residency intervals.

Main files:

- `cli.py`
- `sit_engine_phase1.py`

Responsibilities:

- load normalized interval CSVs
- compute per-window SIT
- write `run_windows.csv`
- write `run_summary.json`
- feed comparison summaries back to the orchestrator

This layer should stay backend-agnostic. Backend-specific parsing belongs in `sit_classifier/`.
