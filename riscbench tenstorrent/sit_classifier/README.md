# SIT Classifier

This layer converts backend-specific raw traces into normalized SIT intervals.

Main files:

- `ingest_api.py`
- `adapters/tt_wormhole_adapter.py`
- `adapters/qemu_adapter.py`
- `adapters/spike_adapter.py`
- `adapters/gem5_adapter.py`
- `adapters/cpu_adapter.py`
- `adapters/adapter_template.py`

Responsibilities:

- parse backend/device trace formats
- classify events into `ACTIVE`, `STALL`, and `IDLE`
- emit `state_intervals.csv`
- emit `residency_intervals.csv`

All new backend adapters should be added under `adapters/`.
