# Phase-0 Tenstorrent Baseline

This page is the shared Phase-0 reference for Tenstorrent Wormhole trace ingestion, calibration, and evaluation. It mirrors the Phase-0 README but keeps the commands and the baseline figure under `docs/` for easier reuse in reports.

## Scope

- input profiler files: `profile_log_device.csv` plus `zone_src_locations.log`
- Phase-0 prototype summary: `Phase-0/README.md`
- Phase-1 parity conversion path: `Phase-1/phase0_trace_to_sit.py`
- runner entrypoint: `Phase-2/riscvbench.py`
- local raw bundles: `Phase-2/datasets/Tenstorrent_test_raw_files-main/`

## Median-Calibrated Expected Work Rates

Use the `median` column when you want `sit_median` to land near `1.0` for the current trace bundle. Use `p95` when you want stronger windows to approach `1.0` while weaker windows stay below it.

| Workload | Dataset | Window (us) | Residency | `ops_per_zone` | `expected_work_rate` median ops/us | `expected_work_rate` p95 ops/us |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| `matmul_single` | `tt_matmul_single` | 8 | `active_span` | 65536 | 269515 | 1340065 |
| `matmul_multi` | `tt_matmul_multi` | 8 | `active_span` | 65536 | 75274 | 596025 |
| `vecadd` | `tt_vecadd` | 32 | `kernel_envelope` | 1024 | 1444 | 2583 |
| `sfpu_chain` | `tt_sfpu_chain` | 8 | `active_span` | 3072 | 2266 | 2266 |
| `eltwise_sfpu` | `tt_eltwise_sfpu` | 8 | `active_span` | 1024 | 4136 | 5979 |
| `eltwise_binary` | `tt_eltwise_binary` | 8 | `active_span` | 1024 | 4800 | 5248 |

Notes:

- `matmul_multi` is calibrated to the current per-core summary path, not chip-level aggregate throughput.
- `vecadd` stays an `ops` proxy row here; it is not a bandwidth-normalized `GB/s` measurement.

## Commands

Run these from the repo root:

```bash
source Phase-2/.venv-phase2/bin/activate

python3 Phase-2/riscvbench.py \
  --target tt_wormhole \
  --workload matmul_single \
  --workload_size test \
  --tt-profile-csv Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_matmul_single/profiler_logs/profile_log_device.csv \
  --tt-zone-log Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_matmul_single/profiler_logs/zone_src_locations.log \
  --tt-output-mode tile \
  --tt-residency-model active_span \
  --tt-ops-per-zone 65536 \
  --tt-strict-pairing \
  --tt-strict-map-hit \
  --time_us 8 \
  --expected-work-rate 269515

python3 Phase-2/riscvbench.py \
  --target tt_wormhole \
  --workload matmul_multi \
  --workload_size test \
  --tt-profile-csv Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_matmul_multi/profiler_logs/profile_log_device.csv \
  --tt-zone-log Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_matmul_multi/profiler_logs/zone_src_locations.log \
  --tt-output-mode tile \
  --tt-residency-model active_span \
  --tt-ops-per-zone 65536 \
  --tt-strict-pairing \
  --tt-strict-map-hit \
  --time_us 8 \
  --expected-work-rate 75274

python3 Phase-2/riscvbench.py \
  --target tt_wormhole \
  --workload vecadd \
  --workload_size test \
  --tt-profile-csv Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_vecadd/profiler_logs/profile_log_device.csv \
  --tt-zone-log Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_vecadd/profiler_logs/zone_src_locations.log \
  --tt-output-mode tile \
  --tt-residency-model kernel_envelope \
  --tt-ops-per-zone 1024 \
  --tt-strict-pairing \
  --tt-strict-map-hit \
  --time_us 32 \
  --expected-work-rate 1444

python3 Phase-2/riscvbench.py \
  --target tt_wormhole \
  --workload sfpu_chain \
  --workload_size test \
  --tt-profile-csv Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_sfpu_chain/profiler_logs/profile_log_device.csv \
  --tt-zone-log Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_sfpu_chain/profiler_logs/zone_src_locations.log \
  --tt-output-mode tile \
  --tt-residency-model active_span \
  --tt-ops-per-zone 3072 \
  --tt-strict-pairing \
  --tt-strict-map-hit \
  --time_us 8 \
  --expected-work-rate 2266

python3 Phase-2/riscvbench.py \
  --target tt_wormhole \
  --workload eltwise_sfpu \
  --workload_size test \
  --tt-profile-csv Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_eltwise_sfpu/profiler_logs/profile_log_device.csv \
  --tt-zone-log Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_eltwise_sfpu/profiler_logs/zone_src_locations.log \
  --tt-output-mode tile \
  --tt-residency-model active_span \
  --tt-ops-per-zone 1024 \
  --tt-strict-pairing \
  --tt-strict-map-hit \
  --time_us 8 \
  --expected-work-rate 4136

python3 Phase-2/riscvbench.py \
  --target tt_wormhole \
  --workload eltwise_binary \
  --workload_size test \
  --tt-profile-csv Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_eltwise_binary/profiler_logs/profile_log_device.csv \
  --tt-zone-log Phase-2/datasets/Tenstorrent_test_raw_files-main/tt_eltwise_binary/profiler_logs/zone_src_locations.log \
  --tt-output-mode tile \
  --tt-residency-model active_span \
  --tt-ops-per-zone 1024 \
  --tt-strict-pairing \
  --tt-strict-map-hit \
  --time_us 8 \
  --expected-work-rate 4800
```

If you want the plots after the TT runs finish:

```bash
for workload in matmul_single matmul_multi vecadd sfpu_chain eltwise_sfpu eltwise_binary; do
  python3 Phase-2/sweeps/plot_spike_window_diagnostics.py \
    --windows-csv "Phase-2/runs/tt_wormhole/${workload}/test/run_windows.csv" \
    --out-dir "Phase-0/results/${workload}_plots" \
    --prefix "${workload}" \
    --platform-label "Tenstorrent ${workload}"

  python3 Phase-2/tools/generate_window_heatmaps.py \
    --windows-csv "Phase-2/runs/tt_wormhole/${workload}/test/run_windows.csv" \
    --out-dir "Phase-0/results/${workload}_plots" \
    --prefix "${workload}" \
    --platform-label "Tenstorrent ${workload}"
done
```

## Evaluation Snapshot

These values come from local runs executed on March 13, 2026 with the median-calibrated commands above. The raw `Phase-2/runs/tt_wormhole/...` outputs are local workspace artifacts and are currently gitignored.

| Workload | Preset | `sit_median` | `sit_p95` | `residency_idle` | `residency_stall` | Expectation |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `matmul_single` | `test` | 0.98 | 1.00 | 0.0% | 18.7% | Median-calibrated compute trace; expected to land near `1.0` after `active_span` tail trimming. |
| `matmul_multi` | `test` | 1.00 | 1.00 | 0.0% | 13.2% | Median-calibrated multicore trace; current summary is per-core, not chip aggregate. |
| `vecadd` | `test` | 0.99 | 1.00 | 0.0% | 95.3% | Streaming proxy row; high stall is trace behavior under `kernel_envelope`, not a failed run. |
| `sfpu_chain` | `test` | 1.00 | 1.00 | 0.0% | 0.0% | Short SFPU compute trace; median and p95 are effectively identical at this window size. |
| `eltwise_sfpu` | `test` | 0.99 | 1.00 | 0.0% | 5.2% | Compute-oriented `active_span` trace; expected to cluster near `1.0` with low stall. |
| `eltwise_binary` | `test` | 0.98 | 1.00 | 0.0% | 84.5% | Correct run, but this trace is heavily stall-biased even after median calibration. |

## Baseline Figure

![Tenstorrent baseline summary](Tenstorrent%20baseline.png)
