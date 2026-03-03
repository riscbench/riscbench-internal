# RISCBench Phase-1 SIT Engine

Phase-1 implements a hardware-agnostic SIT pipeline:
- normalized ingestion contract: `ingest/ingest_api.py`
- adapters: `adapters/`
- core engine: `sit_engine_phase1.py`
- staged CLI: `cli.py` (`ingest -> classify -> export`)
- versioned schema export: `schema/v1.py`
- semantic checks: `tests/check_invariants.py`, `tests/run_golden_suite.py`

## Deliverable status (checked on 2026-02-24)

| Deliverable | Status | Evidence |
|---|---|---|
| SIT Engine Core | Done | Engine is hardware-agnostic and residency-gated in `sit_engine_phase1.py`; strict Phase-0 parity is enforced by `tests/check_phase0_parity.py` on `datasets/traces/trace_F_phase0_wormhole_sample.csv` via the golden suite. |
| Time and Windowing | Done | Fixed-window half-open slicing with exact-boundary epsilon in `split_interval_into_windows`; boundary/partial overlap checks in `tests/check_invariants.py` (`exact_boundary`, `partial`). |
| Residency Model | Done | Residency merge/intersection (`merge_intervals`, `intersect_with_mask`) and gated accumulation in engine; non-resident metrics remain excluded/NaN as validated by invariants. |
| Trace Ingestion API | Done | Contract + validators in `ingest/ingest_api.py`; engine only consumes adapter-normalized intervals. |
| Baseline Adapter | Done | `adapters/baseline_adapter.py` wired through CLI and engine; end-to-end ingest/classify/export replay is deterministic for equivalent inputs. |
| Output Schema v1 | Done | Versioned validators in `schema/v1.py`; export writes `windows_v1.csv` + `summary_v1.json` and best-effort `windows_v1.parquet`. |
| Validation Suite | Done | Golden runner + invariants in `tests/`; CI runs golden suite in `.github/workflows/phase1-ci.yml`. |
| Reference Datasets | Done | Pinned bundle and manifest in `datasets/manifest.json`, including dataset version, engine linkage, residency masks, and Phase-0 provenance block. |
| CLI Pipeline | Done | `cli.py` provides `ingest`, `classify`, `export`; run artifacts are manifest-driven. |
| Documentation | Done | Main docs in this README, `docs/phase1_technical_document.tex`, and `docs/guides/GENERALIZATION.md`. |
| CI Hooks | Done | PR/push workflow executes Phase-1 validation (`phase1-ci.yml`); semantic drift in golden checks fails CI. |

## Quick run

```bash
cd Phase-1

python3 cli.py ingest --trace datasets/traces/trace_A_single_residency.csv --out runs/A
python3 cli.py classify --in runs/A --window-us 256 --residency datasets/residency/partial.csv
python3 cli.py export --in runs/A --schema v1

python3 tests/run_golden_suite.py --outdir /tmp/phase1_golden_out
```

## Artifacts

```text
runs/<run_id>/
  manifest.json
  trace.csv
  residency.csv                # optional
  windows.csv
  summary.json
  export/
    windows_v1.csv
    summary_v1.json
    windows_v1.parquet         # optional (parquet backend installed)
```

## Important docs

- Technical spec: `docs/phase1_technical_document.tex`
- Generalization note: `docs/guides/GENERALIZATION.md`
- Deliverables matrix: `docs/phase1_deliverables_matrix.tex`
- Validation deep dive: `docs/VALIDATION_PHASE1.md`
- Dataset contract: `docs/REFERENCE_DATASETS_PHASE1.md`
