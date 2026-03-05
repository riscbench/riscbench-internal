# Phase-2 Changelog

## 2026-03-04

### Additions
- Added `tools/run_gem5_property_suite.sh` to run gem5 exec reduced-matrix Phase-2 checks in one command (sweep, plots, monotonic flag checks, and no-work SIT mode validation).
- Added `--results-dir` and trace-driven (`--trace` / `--traces-dir`) re-check modes to the gem5 property suite script.

## 2026-02-25

### Behavior changes
- QEMU adapter time base now advances on dynamic `Trace ...` execution events (TB runtime), not static disassembly lines.
- QEMU non-zero exits are now fatal by default; opt out with `--allow-nonzero-exit`.
- Cross-target smoke runner now supports selectable `--targets` (`spike`, `cpu`, `qemu`, `gem5`) and `--skip-missing-tools`.
- Adapter metadata is now emitted to `runs/<target>/<workload>/<size>/adapter_meta.json`.
- Key adapter metadata is embedded under `adapter_meta` in `summary.json` and `run_summary.json`.
- Added parser-stability fixture checks for QEMU and Spike adapters.
- Added deterministic golden replay checker comparing SHA256 bytes across two reruns.

### Reproduce
- Fixture parser stability:
  - `python3 Phase-2/tests/check_adapter_fixtures.py`
- Determinism:
  - `python3 Phase-2/tests/check_determinism.py --targets spike qemu --pk /path/to/pk`
- Cross-target smoke:
  - `python3 Phase-2/run_cross_target_suite.py --targets spike cpu qemu --pk /path/to/pk`
- QEMU run with permissive exit handling:
  - `python3 Phase-2/riscvbench.py --target qemu --workload fm_mm --workload_size small --time_us 256 --expected-work-rate 1.0 --allow-nonzero-exit`
