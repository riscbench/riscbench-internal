# Tenstorrent Wormhole Documentation Suite

- Dataset root: `/home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2/datasets/Tenstorrent_test_raw_files-main`
- Window size: `256.0` us
- TT residency model: `kernel_envelope`
- Generated: `2026-03-13T17:01:51.835171Z`

## Cases

| Case | Family | Proxy | Console Status | SIT Median | Stall Avg | Active Avg | Plot 1 | Plot 2 | Plot 3 |
|---|---|---|---|---:|---:|---:|---|---|---|
| tt_matmul_multi | matmul | matmul | PCC=0.99988395 | 0.838851 | 22.23% | 77.77% | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_matmul_multi/plots/tt_matmul_multi__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_matmul_multi/plots/tt_matmul_multi__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_matmul_multi/plots/tt_matmul_multi__plot3_sit_window_profile.svg) |
| tt_sfpu_chain | sfpu | sfpu_proxy | PCC=0.9998643 | 0.959897 | 4.01% | 95.99% | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_sfpu_chain/plots/tt_sfpu_chain__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_sfpu_chain/plots/tt_sfpu_chain__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_sfpu_chain/plots/tt_sfpu_chain__plot3_sit_window_profile.svg) |
| tt_vecadd | streaming | streaming_proxy | results_match_expected | 0.042860 | 95.28% | 4.72% | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_vecadd/plots/tt_vecadd__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_vecadd/plots/tt_vecadd__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_170142/cases/tt_vecadd/plots/tt_vecadd__plot3_sit_window_profile.svg) |

## Heatmaps

- `tt_matmul_multi`: [active](Phase-2/tt_doc_runs/20260313_170142/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_170142/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_170142/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_170142/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_170142/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_sit_metric.svg)
- `tt_sfpu_chain`: [active](Phase-2/tt_doc_runs/20260313_170142/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_170142/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_170142/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_170142/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_170142/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_sit_metric.svg)
- `tt_vecadd`: [active](Phase-2/tt_doc_runs/20260313_170142/cases/tt_vecadd/plots/tt_vecadd__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_170142/cases/tt_vecadd/plots/tt_vecadd__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_170142/cases/tt_vecadd/plots/tt_vecadd__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_170142/cases/tt_vecadd/plots/tt_vecadd__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_170142/cases/tt_vecadd/plots/tt_vecadd__heatmap_sit_metric.svg)

## Skipped

- `phase0_golden`: missing profile_log_device.csv
- `tt_custom_sfpi_smoothstep`: missing profile_log_device.csv

## Main Artifacts

- `sweep_results.csv`: TT case manifest for aggregate visualization
- `tt_doc_summary.csv`: documentation summary table with metrics and plot paths
- `tt_compute_summary.csv`: compute-only TT subset (matmul/sfpu/eltwise)
- `plots/common_sit_median_by_workload.svg`: RISCVBench-style case summary plot
- `plots/tt_sit_median_by_case.svg`: TT case bar chart
- `plots/tt_compute_sit_median_by_case.svg`: compute-only SIT bar chart
- `plots/tt_compute_residency_active_pct_by_case.svg`: compute-only active-residency bar chart
- `plots/tt_compute_residency_stall_pct_by_case.svg`: compute-only stall-residency bar chart
- `cases/<case>/plots/*`: per-case SIT timeline, stacked breakdown, and window-profile diagnostics
- `cases/<case>/plots/*heatmap*.svg`: per-case active/stall/idle/residency/SIT heatmaps
