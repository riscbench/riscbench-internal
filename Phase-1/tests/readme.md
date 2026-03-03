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
