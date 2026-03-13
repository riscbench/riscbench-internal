# Phase-0 CPU Baseline and Tenstorrent Trace Context

Phase-0 is the baseline workload and trace-analysis layer that used to live at the repository root. It now holds the original CPU workload sources, sample trace artifacts, and the baseline documentation set in one place.

## Scope

- workload sources: [`matmul.c`](matmul.c), [`matmul_multicore.c`](matmul_multicore.c)
- helper CLI wrapper: [`riscvbench`](riscvbench)
- baseline parser: [`adapters/cpu_adapter.py`](adapters/cpu_adapter.py)
- sample outputs: [`results/`](results/)
- baseline documentation set: [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md), [`WORKLOAD_ANALYSIS.md`](WORKLOAD_ANALYSIS.md), [`TRACE_ANALYSIS_EXAMPLES.md`](TRACE_ANALYSIS_EXAMPLES.md), [`MULTICORE_DATASET.md`](MULTICORE_DATASET.md), [`RISCVBENCH_USAGE.md`](RISCVBENCH_USAGE.md), [`INDEX.md`](INDEX.md), [`DOCUMENTATION_SUMMARY.md`](DOCUMENTATION_SUMMARY.md)

## Tenstorrent and Phase-0 Trace Provenance

Phase-0 parity is anchored to the Tenstorrent Wormhole baseline workflow carried forward into Phase-1:

- converter: [`../Phase-1/phase0_trace_to_sit.py`](../Phase-1/phase0_trace_to_sit.py)
- pinned Wormhole-derived sample trace: [`../Phase-1/datasets/traces/trace_F_phase0_wormhole_sample.csv`](../Phase-1/datasets/traces/trace_F_phase0_wormhole_sample.csv)
- strict parity gate: [`../Phase-1/tests/check_phase0_parity.py`](../Phase-1/tests/check_phase0_parity.py)
- golden runner: [`../Phase-1/tests/run_golden_suite.py`](../Phase-1/tests/run_golden_suite.py)
- cross-phase validation commands: [`../docs/ALL_TARGETS_VALIDATION_COMMANDS.md`](../docs/ALL_TARGETS_VALIDATION_COMMANDS.md)

When local Tenstorrent raw trace bundles are present, the newer platform-side documentation and generated reports live under `../Phase-2/datasets/` and `../Phase-2/tt_doc_runs/`.

## Important Docs

- quick start: [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md)
- workload behavior and performance notes: [`WORKLOAD_ANALYSIS.md`](WORKLOAD_ANALYSIS.md)
- raw trace interpretation: [`TRACE_ANALYSIS_EXAMPLES.md`](TRACE_ANALYSIS_EXAMPLES.md)
- multicore dataset notes: [`MULTICORE_DATASET.md`](MULTICORE_DATASET.md)
- CLI usage: [`RISCVBENCH_USAGE.md`](RISCVBENCH_USAGE.md)
- navigation summary: [`INDEX.md`](INDEX.md), [`DOCUMENTATION_SUMMARY.md`](DOCUMENTATION_SUMMARY.md)

## Usage Examples

Build and run from inside `Phase-0/`:

```bash
gcc -O2 -g -pthread matmul.c -o matmul
./matmul --tile-elems 1024 --tiles 10000 --trace results/output.trace
```

Use the Phase-1-backed CLI wrapper from inside `Phase-0/`:

```bash
./riscvbench --target cpu --workload matmul --workload_size small --time_us 256
```

## Integration with SIT Engine

Phase-0 produces the baseline raw traces and parity context that feed forward into the later phases:

- Phase-1 normalizes and validates the Phase-0 parity sample against the Wormhole-derived baseline.
- Phase-2 adapters and platform suites reuse the same SIT semantics and validation shape on top of new targets.

## Troubleshooting

- If `./riscvbench` fails, make sure `python3` is installed and [`../Phase-1/riscvbench.py`](../Phase-1/riscvbench.py) is available.
- If trace files are missing, create or reuse the local `results/` directory under `Phase-0/`.
- For parity-specific issues, start with [`../Phase-1/tests/check_phase0_parity.py`](../Phase-1/tests/check_phase0_parity.py).

## Contributing & Extending

- change workload mechanics in [`matmul.c`](matmul.c) or [`matmul_multicore.c`](matmul_multicore.c)
- update parser behavior in [`adapters/cpu_adapter.py`](adapters/cpu_adapter.py)
- keep user-facing guidance aligned in the moved Phase-0 markdown docs
