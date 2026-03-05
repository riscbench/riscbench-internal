# Phase-2 Platform Key References and All-Checks Entry

Use this page as the single entrypoint for:
- platform runbooks,
- practical sweep configs,
- pinned metrics references,
- and the commands that run platform validation checks.

## Use Inside a Virtualenv (`riscvbench`)

Run from `Phase-2/`:

```bash
python3 -m venv .venv-phase2
source .venv-phase2/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
riscvbench --help
```

Quick sanity run:

```bash
source .venv-phase2/bin/activate
riscvbench --target qemu --workload fm_mm --workload_size test --time_us 256 --expected-work-rate 1.0 --allow-nonzero-exit
```

## Run All Platform Checks

Run from `Phase-2/`:

```bash
# 1) QEMU property suite (sweep + visualize + monotonic + no-work checks + window-time plots)
bash tools/run_qemu_property_suite.sh

# 2) gem5 property suite (sweep + visualize + monotonic + no-work checks + window-time plots)
bash tools/run_gem5_property_suite.sh

# 3) Spike property suite (sweep + visualize + monotonic + no-work checks + window-time plots)
bash tools/run_spike_property_suite.sh

# 4) Optional Spike golden pipeline (generation + invariants + monotonic + common outputs)
python3 tests/run_spike_golden_pipeline.py \
  --pk /absolute/path/to/pk \
  --workloads fm_loopback fm_mm fm_sparse fm_read fm_write \
  --workload-size test \
  --emulated-flags none branch_mispredict cache_pressure both \
  --time-us 256 \
  --window-us 256 \
  --common-mode base \
  --outdir golden_out_spike_matrix_checks
```

## Key References

- gem5 platform runbook:
  - [gem5/README.md](gem5/README.md)
- qemu platform runbook:
  - [qemu/README.md](qemu/README.md)
- spike platform runbook:
  - [spike/README.md](spike/README.md)

- gem5 practical sweep config:
  - [../../sweeps/sweep_config_gem5_matrix_practical_exec.json](../../sweeps/sweep_config_gem5_matrix_practical_exec.json)
- qemu practical sweep config:
  - [../../sweeps/sweep_config_qemu_matrix_practical.json](../../sweeps/sweep_config_qemu_matrix_practical.json)
- spike practical sweep config:
  - [../../sweeps/sweep_config_spike_matrix_practical.json](../../sweeps/sweep_config_spike_matrix_practical.json)

- gem5 pinned metrics CSV:
  - [../../sweeps/pinned/gem5_exec_reduced_matrix_20260305_v2/plots/sweep_results_with_metrics.csv](../../sweeps/pinned/gem5_exec_reduced_matrix_20260305_v2/plots/sweep_results_with_metrics.csv)
- qemu pinned metrics CSV:
  - [../../sweeps/pinned/qemu_exec_reduced_matrix_20260305_v1/plots/sweep_results_with_metrics.csv](../../sweeps/pinned/qemu_exec_reduced_matrix_20260305_v1/plots/sweep_results_with_metrics.csv)
- spike pinned metrics CSV:
  - [../../sweeps/pinned/spike_exec_reduced_matrix_20260305_v1/plots/sweep_results_with_metrics.csv](../../sweeps/pinned/spike_exec_reduced_matrix_20260305_v1/plots/sweep_results_with_metrics.csv)

- monotonic threshold logic:
  - [../../tests/check_flag_monotonicity.py](../../tests/check_flag_monotonicity.py)
- no-work SIT fallback behavior:
  - [../../sit_engine_phase1.py](../../sit_engine_phase1.py)

- QEMU property suite:
  - [../../tools/run_qemu_property_suite.sh](../../tools/run_qemu_property_suite.sh)
- gem5 property suite:
  - [../../tools/run_gem5_property_suite.sh](../../tools/run_gem5_property_suite.sh)
- Spike property suite:
  - [../../tools/run_spike_property_suite.sh](../../tools/run_spike_property_suite.sh)
- Spike golden pipeline:
  - [../../tests/run_spike_golden_pipeline.py](../../tests/run_spike_golden_pipeline.py)

## Exact Branch/Cache Matrix (gem5, Spike, QEMU)

### Platform Matrix (Pinned Bundles)

| Platform | Practical config | Pinned metrics CSV (used for table/graphs) | Workloads | workload_size | time_us | `branch_mispredict` values | `cache_pressure` values | Cases |
|---|---|---|---|---|---:|---|---|---:|
| QEMU | `sweeps/sweep_config_qemu_matrix_practical.json` | `sweeps/pinned/qemu_exec_reduced_matrix_20260305_v1/plots/sweep_results_with_metrics.csv` | `fm_loopback,fm_mm,fm_sparse,fm_read,fm_write` | `test` | 256.0 | `False, True` | `False, True` | 20 |
| Spike | `sweeps/sweep_config_spike_matrix_practical.json` | `sweeps/pinned/spike_exec_reduced_matrix_20260305_v1/plots/sweep_results_with_metrics.csv` | `fm_loopback,fm_mm,fm_sparse,fm_read,fm_write` | `test` | 256.0 | `False, True` | `False, True` | 20 |
| gem5 | `sweeps/sweep_config_gem5_matrix_practical_exec.json` | `sweeps/pinned/gem5_exec_reduced_matrix_20260305_v2/plots/sweep_results_with_metrics.csv` | `fm_loopback,fm_mm,fm_sparse,fm_read,fm_write,matmul` | `test` | 256.0 | `False, True` | `False, True` | 24 |

### Exact Stall/Mispredict Gradients Used by Flags

Shared flag semantics are injected in `riscvbench.py::_inject_unified_workload_phases()` for all three platforms.

For `workload_size=test` (`ITER=256`): `unit = max(ITER/6, 64) = 64`.

| Flag mode | Condition | Injected idle/stall iterations | Exact value at `test` |
|---|---|---|---:|
| `none` | `branch=0, cache=0` | `idle = 6 * unit` | 384 idle |
| `branch_mispredict` | `branch=1, cache=0` | `stall += 8 * unit` | +512 stall |
| `cache_pressure` | `branch=0, cache=1` | `stall += 16 * unit` | +1024 stall |
| `both` | `branch=1, cache=1` | `stall += 8*unit + 16*unit + 96*unit` | +7680 stall |

`branch_mispredict` also flips compute-path branch patterns (`BRANCH_MISPREDICT_ENABLED=1`) in templates where present.

### Workload-Level Stall Loops (test size, exact values)

These are the template stall-loop iterations before the shared injected gradients above.

| Workload | Branch template stall | Cache template stall | Both-template extra stall | Branch total (`template + 512`) | Cache total (`template + 1024`) | Both total (`branch + cache + both_extra + 7680`) |
|---|---:|---:|---:|---:|---:|---:|
| `fm_loopback` | 512 (`ITER*2`) | 1024 (`ITER*4`) | 2048 (`ITER*8`) | 1024 | 2048 | 11264 |
| `fm_mm` | 512 (`N*N*2`) | 1024 (`N*N*N/4`) | 256 (`N*N`) | 1024 | 2048 | 9472 |
| `fm_sparse` | 512 (`N*NNZ_PER_ROW*4`) | 1024 (`N*NNZ_PER_ROW*8`) | 2048 (`N*NNZ_PER_ROW*16`) | 1024 | 2048 | 11264 |
| `fm_read` | 0 | 32 (`ITER/8`) | 0 | 512 | 1056 | 7712 |
| `fm_write` | 0 | 32 (`ITER/8`) | 0 | 512 | 1056 | 7712 |

### Monotonic Check Thresholds (Property Suites)

From `tools/run_{qemu,spike,gem5}_property_suite.sh` via `tests/check_flag_monotonicity.py`:

| Platform | `--min-sit-drop` | `--min-stall-rise` | `--max-idle-rise` |
|---|---:|---:|---:|
| QEMU | 0.02 | 0.02 | 0.20 |
| Spike | 0.015 | 0.02 | 0.20 |
| gem5 | 0.02 | 0.02 | 0.20 |

Spike suite defaults can be overridden with:
- `SPIKE_MONOTONIC_MIN_SIT_DROP`
- `SPIKE_MONOTONIC_MIN_STALL_RISE`
- `SPIKE_MONOTONIC_MAX_IDLE_RISE`

## Additional Cross-Platform Graphs

Generated from pinned metrics with:

```bash
cd Phase-2
python3 tools/generate_platform_comparison_graphs.py \
  --qemu-csv sweeps/pinned/qemu_exec_reduced_matrix_20260305_v1/plots/sweep_results_with_metrics.csv \
  --spike-csv sweeps/pinned/spike_exec_reduced_matrix_20260305_v1/plots/sweep_results_with_metrics.csv \
  --gem5-csv sweeps/pinned/gem5_exec_reduced_matrix_20260305_v2/plots/sweep_results_with_metrics.csv
```

Artifacts:
- summary CSV:
  - [plots/platform_flag_gradient_summary.csv](plots/platform_flag_gradient_summary.csv)
- SIT median vs flag mode:
  - [plots/cross_platform_sit_median_by_flag.svg](plots/cross_platform_sit_median_by_flag.svg)
- residency stall vs flag mode:
  - [plots/cross_platform_residency_stall_by_flag.svg](plots/cross_platform_residency_stall_by_flag.svg)
- SIT drop vs baseline (`none`):
  - [plots/cross_platform_sit_drop_vs_none.svg](plots/cross_platform_sit_drop_vs_none.svg)
- stall rise vs baseline (`none`):
  - [plots/cross_platform_stall_rise_vs_none.svg](plots/cross_platform_stall_rise_vs_none.svg)

Cross-platform comparison in these plots uses the common workload intersection:
`fm_loopback,fm_mm,fm_sparse,fm_read,fm_write` (5 workloads, `workload_size=test`).

### Observed Gradient Means from Pinned Data

| Platform | Flag mode | Mean `sit_median` | Mean `residency_stall (%)` | `sit_drop_vs_none` | `stall_rise_vs_none (%)` |
|---|---|---:|---:|---:|---:|
| QEMU | `none` | 0.903894 | 0.309610 | 0.000000 | 0.000000 |
| QEMU | `branch_mispredict` | 0.794802 | 14.828725 | 0.109092 | 14.519115 |
| QEMU | `cache_pressure` | 0.734522 | 21.659134 | 0.169372 | 21.349524 |
| QEMU | `both` | 0.490948 | 48.568900 | 0.412946 | 48.259290 |
| Spike | `none` | 0.319869 | 30.159224 | 0.000000 | 0.000000 |
| Spike | `branch_mispredict` | 0.212767 | 56.667768 | 0.107102 | 26.508544 |
| Spike | `cache_pressure` | 0.170393 | 66.328932 | 0.149476 | 36.169708 |
| Spike | `both` | 0.072615 | 87.571769 | 0.247255 | 57.412545 |
| gem5 | `none` | 0.551551 | 19.375202 | 0.000000 | 0.000000 |
| gem5 | `branch_mispredict` | 0.366738 | 49.386668 | 0.184813 | 30.011466 |
| gem5 | `cache_pressure` | 0.305939 | 59.075656 | 0.245611 | 39.700454 |
| gem5 | `both` | 0.126469 | 84.135368 | 0.425081 | 64.760166 |

## Platform Narrative (Updated March 5, 2026)

Recomputed with current pinned bundles:
- QEMU: `sweeps/pinned/qemu_exec_reduced_matrix_20260305_v1`
- Spike: `sweeps/pinned/spike_exec_reduced_matrix_20260305_v1`
- gem5: `sweeps/pinned/gem5_exec_reduced_matrix_20260305_v2`

Cross-platform means below use the common workload intersection:
`fm_loopback,fm_mm,fm_sparse,fm_read,fm_write` (`workload_size=test`).

### QEMU
1. What's the purpose of using this platform in my SIT engine  
   Fast functional backend for adapter-contract validation, quick regression sweeps, and low-latency feedback.
2. How does it evaluate/prepare my workload  
   `riscvbench.py` compiles workloads with `riscv64-linux-gnu-gcc`, runs QEMU with dynamic trace logging (`-d in_asm,exec,nochain`), adapter normalizes state/residency intervals, SIT engine computes windows and summaries.
3. Validation strategy used  
   `tools/run_qemu_property_suite.sh` runs fixture checks, sweep, visualization, monotonic checks (`tests/check_flag_monotonicity.py`), no-work SIT mode checks, and window-time diagnostics plots from generated `*_windows.csv`.
4. Results relevant to the platform  
   Cases: `20/20` pass.  
   Mean SIT by flag: `none 0.903894`, `branch 0.794802`, `cache 0.734522`, `both 0.490948`.  
   Runtime: mean `1.936s`, median `1.980s`, max `2.172s`.  
   Monotonic: `0/5` workload-group failures, `0/15` variant failures.
5. Confidence level of metrics  
   Medium-high for trend consistency and CI gating; lower for microarchitectural realism (functional emulation, non-cycle-accurate timing).
6. Next work / in-progress  
   Keep QEMU as primary fast gate; continue periodic repinning and cross-check against Spike/gem5 drift.

### Spike
1. What's the purpose of using this platform in my SIT engine  
   Reference ISA/marker backend for validating marker semantics and parser correctness.
2. How does it evaluate/prepare my workload  
   `riscvbench.py` compiles workloads with RISC-V ELF toolchain, executes with `spike -l` and `pk`, Spike adapter parses commit-log events and marker transitions, SIT engine classifies windows.
3. Validation strategy used  
   `tools/run_spike_property_suite.sh` runs fixture checks, sweep, visualization, monotonic checks with Spike defaults, no-work SIT mode checks, and window-time diagnostics plots from generated `*_windows.csv`.
4. Results relevant to the platform  
   Cases: `20/20` pass.  
   Mean SIT by flag: `none 0.319869`, `branch 0.212767`, `cache 0.170393`, `both 0.072615`.  
   Runtime: mean `19.457s`, median `19.238s`, max `29.777s`.  
   Monotonic at Spike defaults (`0.015/0.02/0.20`): `0/5` workload-group failures, `0/15` variant failures.
5. Confidence level of metrics  
   Medium-high for marker/reference semantics and ordering behavior under configured thresholds; still functional-ISA (no microarchitectural timing model).
6. Next work / in-progress  
   Preserve current thresholds and keep sparse workload behavior monitored during future repins.

### gem5
1. What's the purpose of using this platform in my SIT engine  
   Timing-aware backend for cache/branch/pipeline/memory contention behavior in SIT.
2. How does it evaluate/prepare my workload  
   `riscvbench.py` compiles workload, runs gem5 in `exec` adapter mode, gem5 adapter normalizes trace to state/residency intervals, SIT engine computes outputs.
3. Validation strategy used  
   `tools/run_gem5_property_suite.sh` runs adapter fixture checks (`tests/check_adapter_fixtures.py --fixtures gem5`) + sweep + visualization + monotonic checks + no-work SIT mode checks + window-time diagnostics plots from generated `*_windows.csv`.
4. Results relevant to the platform  
   Cases: `24/24` pass in the pinned property suite.  
   Mean SIT by flag (common 5-workload view): `none 0.551551`, `branch 0.366738`, `cache 0.305939`, `both 0.126469`.  
   Runtime (common 5-workload view): mean `9.568s`, median `9.599s`, max `20.506s`.  
   Monotonic (`0.02/0.02/0.20`): all workload groups pass.
5. Confidence level of metrics  
   Medium-high for timing-trend realism and monotonic trend stability in the current pinned suite.
6. Next work / in-progress  
   Keep repinned trend checks in CI and extend gem5 fixture coverage beyond the current parser-stability case.

### Common Caveat Across All Three
- Current practical sweeps use `work_done_present=false` with `no_work_sit_mode=global_active`; therefore `sit_p95 == sit_median` in these runs.
- This is stable for aggregate comparison, but less informative for within-run window variability.
