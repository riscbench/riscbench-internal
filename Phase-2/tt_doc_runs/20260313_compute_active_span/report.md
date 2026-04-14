# Tenstorrent Wormhole Documentation Suite

- Dataset root: `/home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2/datasets/Tenstorrent_test_raw_files-main`
- Window size: `256.0` us
- TT residency model: `active_span`
- Generated: `2026-03-13T05:44:50.721403Z`

## Cases

| Case | Family | Proxy | Console Status | SIT Median | Stall Avg | Active Avg | Plot 1 | Plot 2 | Plot 3 |
|---|---|---|---|---:|---:|---:|---|---|---|
| tt_custom_sfpi_add | sfpu | sfpu_proxy | test_passed | 0.909678 | 9.03% | 90.97% | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__plot3_sit_window_profile.svg) |
| tt_eltwise_binary | eltwise | eltwise_proxy | test_passed | 0.160225 | 83.98% | 16.02% | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_binary/plots/tt_eltwise_binary__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_binary/plots/tt_eltwise_binary__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_binary/plots/tt_eltwise_binary__plot3_sit_window_profile.svg) |
| tt_eltwise_sfpu | sfpu | sfpu_proxy | test_passed | 0.948130 | 5.19% | 94.81% | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__plot3_sit_window_profile.svg) |
| tt_matmul_multi | matmul | matmul | PCC=0.99988395 | 0.878765 | 14.05% | 85.95% | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_multi/plots/tt_matmul_multi__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_multi/plots/tt_matmul_multi__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_multi/plots/tt_matmul_multi__plot3_sit_window_profile.svg) |
| tt_matmul_single | matmul | matmul | PCC=0.98069453 | 0.851522 | 14.85% | 85.15% | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_single/plots/tt_matmul_single__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_single/plots/tt_matmul_single__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_single/plots/tt_matmul_single__plot3_sit_window_profile.svg) |
| tt_sfpu_chain | sfpu | sfpu_proxy | PCC=0.9998643 | 1.000000 | 0.00% | 100.00% | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_sfpu_chain/plots/tt_sfpu_chain__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_sfpu_chain/plots/tt_sfpu_chain__plot2_window_breakdown_stacked.svg) | [svg](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_sfpu_chain/plots/tt_sfpu_chain__plot3_sit_window_profile.svg) |

## Heatmaps

- `tt_custom_sfpi_add`: [active](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__heatmap_sit_metric.svg)
- `tt_eltwise_binary`: [active](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_binary/plots/tt_eltwise_binary__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_binary/plots/tt_eltwise_binary__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_binary/plots/tt_eltwise_binary__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_binary/plots/tt_eltwise_binary__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_binary/plots/tt_eltwise_binary__heatmap_sit_metric.svg)
- `tt_eltwise_sfpu`: [active](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__heatmap_sit_metric.svg)
- `tt_matmul_multi`: [active](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_multi/plots/tt_matmul_multi__heatmap_sit_metric.svg)
- `tt_matmul_single`: [active](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_single/plots/tt_matmul_single__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_single/plots/tt_matmul_single__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_single/plots/tt_matmul_single__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_single/plots/tt_matmul_single__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_matmul_single/plots/tt_matmul_single__heatmap_sit_metric.svg)
- `tt_sfpu_chain`: [active](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_active_frac.svg) | [stall](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_stall_frac.svg) | [idle](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_idle_frac.svg) | [resident](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_resident_frac_of_window.svg) | [sit](Phase-2/tt_doc_runs/20260313_compute_active_span/cases/tt_sfpu_chain/plots/tt_sfpu_chain__heatmap_sit_metric.svg)

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
