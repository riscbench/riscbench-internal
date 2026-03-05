# Gem5 Graph Evaluation Table

Date: 2026-03-04

## 1) Sweep/Graph Data Sources

| Graph bundle | Pinned folder | Graph files | Cases | Workloads evaluated | workload_size | time_us | Flag modes |
|---|---|---|---:|---|---|---:|---|
| Gem5 reduced matrix (stats adapter) | `Phase-2/sweeps/pinned/gem5_reduced_matrix_20260304` | `elapsed_vs_x.svg`, `sit_median_vs_x.svg`, `sit_p95_vs_x.svg`, `common_sit_median_by_workload_size.svg`, `pass_fail.svg` | 20 | `fm_loopback`, `fm_mm`, `fm_read`, `fm_write`, `matmul` | `test` | 256.0 | `none`, `branch_mispredict`, `cache_pressure`, `both` |
| Gem5 reduced matrix (exec adapter, recommended for marker-faithful semantics) | `Phase-2/sweeps/pinned/gem5_exec_reduced_matrix_20260304_v1` | `common_sit_median_by_workload.svg`, `common_sit_median_by_workload_compact.svg`, `common_sit_median_by_workload_size.svg`, `pass_fail.svg` | 16 | `fm_loopback`, `fm_mm`, `fm_read`, `fm_write` | `test` | 256.0 | `none`, `branch_mispredict`, `cache_pressure`, `both` |

Primary merged metrics files used for plotting:
- `Phase-2/sweeps/pinned/gem5_reduced_matrix_20260304/plots/sweep_results_with_metrics.csv`
- `Phase-2/sweeps/pinned/gem5_exec_reduced_matrix_20260304_v1/plots/sweep_results_with_metrics.csv`

## 2) Technical Run Spec (Gem5)

| Parameter | Value used for these graph bundles | Source |
|---|---|---|
| target | `gem5` | sweep configs |
| gem5 binary | `/home/dev_srinidhi/opt/gem5/build/RISCV/gem5.opt` | sweep configs |
| gem5 root | `/home/dev_srinidhi/opt/gem5` | sweep configs |
| gem5 config | `/home/dev_srinidhi/opt/gem5/configs/deprecated/example/se.py` | sweep configs |
| compiler (`gem5_cc`) | `riscv64-linux-gnu-gcc` | sweep configs |
| cpu model | `TimingSimpleCPU` | `riscvbench.py` default (`--gem5-cpu-type`) |
| memory size | `512MB` | `riscvbench.py` default (`--gem5-mem-size`) |
| caches option | `--caches` enabled | gem5 launch path in `riscvbench.py` |
| expected work rate | `1.0` | sweep configs |
| `inst_us` | `1.0` | sweep configs |
| `resident_pc_ge` | `0x80000000` | sweep configs |
| adapter mode (stats bundle) | `stats` | `sweep_config_gem5_matrix_practical.json` |
| stats period (stats bundle) | `8.0 us` (`--gem5-stats-period-us`) | `sweep_config_gem5_matrix_practical.json` |
| stats thresholds (stats bundle) | `ipc_active_thresh=0.24`, `stall_miss_thresh=0.05`, `l1_resident_thresh=0.8`, `mem_reqs_per_inst_thresh=0.08`, `idle_inst_thresh=0.0` | `riscvbench.py` defaults + `gem5_adapter.py` defaults |
| adapter mode (exec bundle) | `exec` | `sweep_config_gem5_matrix_practical_exec.json` |

## 3) Workload Size Values (Technical "size" spec)

From `Phase-2/riscvbench.py` `SIZE_PRESETS`:

| workload_size | ITER | DIM | PAGES | ACTIVE_BOOST |
|---|---:|---:|---:|---:|
| test | 256 | 16 | 2 | 1 |
| tiny | 2000 | 64 | 4 | 2 |
| small | 3000 | 96 | 8 | 3 |
| med | 4000 | 128 | 16 | 4 |
| large | 5000 | 256 | 32 | 5 |

For the pinned graph bundles above, only `workload_size=test` was evaluated.

## 4) Flag/Mode Semantics Used in Graph Grouping

| flag_mode | branch_mispredict | cache_pressure |
|---|---|---|
| none | False | False |
| branch_mispredict | True | False |
| cache_pressure | False | True |
| both | True | True |

