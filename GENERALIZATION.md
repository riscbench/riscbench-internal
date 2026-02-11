# Phase-1 Generalization Notes

This document captures how the Phase-1 SIT pipeline is designed to generalize across targets, traces, and workloads.

## 1) Goal

Phase-1 should avoid being tightly coupled to one simulator or one trace format.
Generalization is achieved by normalizing all sources into a single interval contract before metrics are computed.

## 2) What is generalized

### 2.1 Input source generalization

- Different producers (baseline CSV, CPU traces, Spike traces) are supported through adapters.
- Adapters convert source-specific events into a normalized frame:
  - `start_us`, `end_us`, `core`, `state`, optional `work_done`
- The engine does not require source-specific fields.

### 2.2 Time/window generalization

- Windowing uses fixed-size half-open windows (`[start, end)`).
- Exact-boundary behavior is deterministic to prevent double-counting.
- This allows equivalent behavior across traces with different sampling/event granularities.

### 2.3 Residency generalization

- Residency is optional and treated as a mask.
- If present, all state accounting is clipped to residency intervals.
- If absent, windows are treated as fully resident.

### 2.4 Work-model generalization

SIT has two supported modes:

1. `work_done`-aware mode: normalizes throughput with `expected_work_rate`.
2. Fallback mode (no `work_done`): uses active fraction as proxy.

This preserves usability when traces do not expose explicit unit-of-work counters.

## 3) Design considerations

1. **Separation of concerns**
   - Parsing logic is in adapters.
   - Core math is in `sit_engine_phase1.py`.
   - Output contract is in `schema/v1.py`.

2. **Determinism over convenience**
   - Explicit interval semantics are prioritized to keep golden outputs stable.

3. **Compatibility-first schema versioning**
   - Exported artifacts are versioned (`*_v1`) to avoid breaking downstream consumers.

4. **Validation as contract**
   - Invariants + golden suite are treated as behavioral guardrails, not just smoke tests.

## 4) Assumptions

- Timestamps are in microseconds and well-ordered per interval (`end_us > start_us`).
- State labels map to Phase-1 categories (`active`, `stall`, `idle`).
- Adapter outputs satisfy normalization requirements before engine invocation.
- Expected work rate is meaningful only when `work_done` exists.

## 5) Known limits in current repo

- CI was previously absent; a workflow is now added under `.github/workflows/phase1-ci.yml`.
- Dependency availability affects local reproducibility (`numpy`, `pandas`).
- Phase-1 generalization is contract-driven, but adding new targets still requires adapter implementation.

## 6) How to run Phase-1 docs-aligned flow

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . --no-build-isolation

python cli.py ingest --trace datasets/traces/trace_A_single_residency.csv --out runs/A
python cli.py classify --in runs/A --window-us 256 --residency datasets/residency/partial.csv
python cli.py export --in runs/A --schema v1
python tests/run_golden_suite.py --outdir golden_out
```
