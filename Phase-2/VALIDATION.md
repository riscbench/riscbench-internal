# Phase-2 Validation Guide

This is the contributor-facing validation checklist for Phase-2 changes.
Use it before opening or merging a PR.

## Primary Validation Path

Run the platform property suites from `Phase-2/`:

```bash
bash tools/run_spike_property_suite.sh
bash tools/run_qemu_property_suite.sh
bash tools/run_gem5_property_suite.sh
```

Each suite writes a timestamped output directory under `sweeps/results/`.

## Required Artifacts Per Suite Run

For each generated results directory, verify these files exist:

- `sweep_results.csv`
- `sweep_manifest.json`
- `summary.json`
- `plots/monotonic_report.csv`
- `plots/no_work_sit_mode_report.csv`
- `plots/window_time/window_time_generation_report.csv`

For failures, inspect:

- `case_*.log`
- `traces/trace_*.csv`
- `summaries/summary_*.json`

## Secondary Gates

Run adapter parser stability checks:

```bash
python3 tests/check_adapter_fixtures.py --fixtures spike qemu gem5
```

Run deterministic replay check (tool-availability aware):

```bash
python3 tests/check_determinism.py --targets spike qemu gem5 --skip-missing-tools
```

Run cross-target smoke replay:

```bash
python3 run_cross_target_suite.py \
  --workloads fm_loopback fm_mm \
  --workload-size test \
  --time-us 256 \
  --expected-work-rate 1.0 \
  --skip-missing-tools
```

## Done-When Checklist

- All three property suites return exit code `0`.
- `monotonic_report.csv` shows no failed rows for validated variants.
- `no_work_sit_mode_report.csv` confirms the expected global-vs-window SIT behavior.
- Adapter fixtures pass for all requested adapters.
- Determinism check passes for available targets.
- Cross-target smoke run produces valid artifacts and no invariant regressions.

## Key References

- `docs/platforms/KEY_REFERENCES_AND_ALL_CHECKS.md`
- `docs/platforms/spike/README.md`
- `docs/platforms/qemu/README.md`
- `docs/platforms/gem5/README.md`
