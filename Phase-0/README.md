# Phase-0 Tenstorrent Prototype and Wormhole Adapter

Phase-0 is the Tenstorrent/Wormhole phase of the repo. It includes the original `Prototype-Tenstorrent` programs and the newer Wormhole trace-ingestion adapter/docs used to map TT profiler output into the normalized SIT contract.

## Core Files

- prototype tree: [`Prototype-Tenstorrent/`](Prototype-Tenstorrent)
- adapter: [`adapters/tt_wormhole_adapter.py`](adapters/tt_wormhole_adapter.py)
- documentation-suite runner: [`tools/run_tt_wormhole_doc_suite.py`](tools/run_tt_wormhole_doc_suite.py)
- trace notes: [`TENSTORRENT_TRACES.md`](TENSTORRENT_TRACES.md)

## Prototype-Tenstorrent

This is the exact prototype subtree restored from `internal/main`:

- [`Prototype-Tenstorrent/README.txt`](Prototype-Tenstorrent/README.txt)
- `fm_loopback/`
- `fm_mm/`
- `fm_read/`
- `fm_write/`
- [`Prototype-Tenstorrent/looper.py`](Prototype-Tenstorrent/looper.py)
- [`Prototype-Tenstorrent/Bucketized performance generator.py`](Prototype-Tenstorrent/Bucketized%20performance%20generator.py)

## What Phase-0 Owns

- parsing `profile_log_device.csv` plus `zone_src_locations.log`
- pairing `ZONE_START` / `ZONE_END` events into intervals
- converting TT cycle timestamps into normalized microsecond intervals
- exporting engine-ready state and residency tables for the later SIT stages
- documenting how Wormhole traces map into the Phase-1/Phase-2 pipeline

## Tenstorrent and Wormhole Context

The Phase-0 baseline is anchored to the Tenstorrent Wormhole profiler workflow that later phases reuse for parity and validation:

- converter carried into Phase-1: [`../Phase-1/phase0_trace_to_sit.py`](../Phase-1/phase0_trace_to_sit.py)
- pinned Wormhole-derived sample trace: [`../Phase-1/datasets/traces/trace_F_phase0_wormhole_sample.csv`](../Phase-1/datasets/traces/trace_F_phase0_wormhole_sample.csv)
- strict parity gate: [`../Phase-1/tests/check_phase0_parity.py`](../Phase-1/tests/check_phase0_parity.py)
- cross-phase validation commands: [`../docs/ALL_TARGETS_VALIDATION_COMMANDS.md`](../docs/ALL_TARGETS_VALIDATION_COMMANDS.md)

## Local TT Doc Suite

When local TT raw-file bundles are present, the doc-suite runner can summarize them through the shared Phase-2 engine path. The current local workspace examples live under `../Phase-2/datasets/` and `../Phase-2/tt_doc_runs/` when available.

## Legacy CPU Baseline Material

The older CPU baseline workload docs and sample artifacts are still kept in this phase folder for reference:

- [`matmul.c`](matmul.c), [`matmul_multicore.c`](matmul_multicore.c)
- [`adapters/cpu_adapter.py`](adapters/cpu_adapter.py)
- [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md), [`WORKLOAD_ANALYSIS.md`](WORKLOAD_ANALYSIS.md), [`TRACE_ANALYSIS_EXAMPLES.md`](TRACE_ANALYSIS_EXAMPLES.md), [`MULTICORE_DATASET.md`](MULTICORE_DATASET.md), [`RISCVBENCH_USAGE.md`](RISCVBENCH_USAGE.md)

## Integration with SIT Engine

- `Prototype-Tenstorrent/` is the program-side prototype source tree.
- Phase-0 normalizes Wormhole trace structure and semantics.
- Phase-1 enforces parity and invariant checks against the Wormhole-derived baseline.
- Phase-2 reuses the same engine path for cross-platform SIT reporting.
