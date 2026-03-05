# QEMU Graph Evaluation Table

Date: 2026-03-04

## 1) Sweep/Graph Data Source

| Graph bundle | Pinned folder | Graph files | Cases | Workloads evaluated | workload_size | time_us | Flag modes |
|---|---|---|---:|---|---|---:|---|
| QEMU reduced matrix (exec flow) | `Phase-2/sweeps/pinned/qemu_exec_reduced_matrix_20260304_v1` | `common_sit_median_by_workload.svg`, `common_sit_median_by_workload_compact.svg`, `common_sit_median_by_workload_size.svg`, `elapsed_vs_x.svg`, `sit_median_vs_x.svg`, `sit_p95_vs_x.svg`, `pass_fail.svg` | 16 | `fm_loopback`, `fm_mm`, `fm_read`, `fm_write` | `test` | 256.0 | `none`, `branch_mispredict`, `cache_pressure`, `both` |

Primary merged metrics file used for plotting:
- `Phase-2/sweeps/pinned/qemu_exec_reduced_matrix_20260304_v1/plots/sweep_results_with_metrics.csv`

## 2) Technical Run Spec (QEMU)

| Parameter | Value used for this graph bundle |
|---|---|
| target | `qemu` |
| qemu binary | `qemu-riscv64` |
| compiler (`qemu_cc`) | `riscv64-linux-gnu-gcc` |
| expected work rate | `1.0` |
| `inst_us` | `1.0` |
| `resident_pc_ge` | `0x80000000` |
| `allow_nonzero_exit` | enabled |

## 3) Property Checks Executed with This Bundle

| Property | Result | Evidence |
|---|---|---|
| Adapter parser fixture stability (QEMU) | PASS | `tests/check_adapter_fixtures.py --fixtures qemu` |
| Monotonic emulated-flag behavior | PASS | `plots/monotonic_report.csv` |
| No-work SIT fallback path (`global_active` vs `window_active`) | PASS | `plots/no_work_sit_mode_report.csv` |
| Golden suite replay over all traces+masks (both no-work modes) | PASS | `golden_window_active/`, `golden_global_active/` |

Detailed command log and summary:
- `Phase-2/sweeps/pinned/qemu_exec_reduced_matrix_20260304_v1/EVIDENCE.md`
