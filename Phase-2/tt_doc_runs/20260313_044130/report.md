# Tenstorrent Wormhole Documentation Suite

- Dataset root: `/home/dev_srinidhi/sit-cpu-baseline/sit-cpu-baseline/Phase-2/datasets/Tenstorrent_test_raw_files-main`
- Window size: `256.0` us
- Generated: `2026-03-13T04:41:46.199081Z`

## Cases

| Case | Family | Proxy | Console Status | SIT Median | Stall Avg | Active Avg | Plot 1 | Plot 2 |
|---|---|---|---|---:|---:|---:|---|---|
| tt_custom_sfpi_add | sfpu | sfpu_proxy | test_passed | 0.891666 | 10.83% | 89.17% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_custom_sfpi_add/plots/tt_custom_sfpi_add__plot2_window_breakdown_stacked.svg) |
| tt_eltwise_binary | eltwise | eltwise_proxy | test_passed | 0.156747 | 84.33% | 15.67% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_eltwise_binary/plots/tt_eltwise_binary__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_eltwise_binary/plots/tt_eltwise_binary__plot2_window_breakdown_stacked.svg) |
| tt_eltwise_sfpu | sfpu | sfpu_proxy | test_passed | 0.938330 | 6.17% | 93.83% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_eltwise_sfpu/plots/tt_eltwise_sfpu__plot2_window_breakdown_stacked.svg) |
| tt_loopback | loopback | fm_loopback | test_passed | 0.000000 | 100.00% | 0.00% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_loopback/plots/tt_loopback__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_loopback/plots/tt_loopback__plot2_window_breakdown_stacked.svg) |
| tt_matmul_multi | matmul | matmul | PCC=0.99988395 | 0.838851 | 22.23% | 77.77% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_matmul_multi/plots/tt_matmul_multi__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_matmul_multi/plots/tt_matmul_multi__plot2_window_breakdown_stacked.svg) |
| tt_matmul_single | matmul | matmul | PCC=0.98069453 | 0.000000 | 98.69% | 1.31% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_matmul_single/plots/tt_matmul_single__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_matmul_single/plots/tt_matmul_single__plot2_window_breakdown_stacked.svg) |
| tt_noc_transfer | streaming | streaming_stall_control | 2026-03-12 23:45:39.278 | info     |             UMD | Closing devices in cluster (cluster.cpp:980) | 0.000000 | 100.00% | 0.00% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_noc_transfer/plots/tt_noc_transfer__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_noc_transfer/plots/tt_noc_transfer__plot2_window_breakdown_stacked.svg) |
| tt_sfpu_chain | sfpu | sfpu_proxy | PCC=0.9998643 | 0.959897 | 4.01% | 95.99% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_sfpu_chain/plots/tt_sfpu_chain__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_sfpu_chain/plots/tt_sfpu_chain__plot2_window_breakdown_stacked.svg) |
| tt_vecadd | streaming | streaming_proxy | results_match_expected | 0.042860 | 95.28% | 4.72% | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_vecadd/plots/tt_vecadd__plot1_sit_vs_time.svg) | [svg](Phase-2/tt_doc_runs/20260313_044130/cases/tt_vecadd/plots/tt_vecadd__plot2_window_breakdown_stacked.svg) |

## Skipped

- `phase0_golden`: missing profile_log_device.csv
- `tt_custom_sfpi_smoothstep`: missing profile_log_device.csv

## Main Artifacts

- `sweep_results.csv`: TT case manifest for aggregate visualization
- `tt_doc_summary.csv`: documentation summary table with metrics and plot paths
- `plots/common_sit_median_by_workload.svg`: RISCVBench-style case summary plot
- `plots/tt_sit_median_by_case.svg`: TT case bar chart
- `cases/<case>/plots/*`: per-case aggregate window diagnostics
