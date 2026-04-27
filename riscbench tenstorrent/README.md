# Riscbench Tenstorrent Bundle

This folder is a minimal standalone copy of the runtime pieces from `Phase-2`, plus a single orchestration entrypoint for:

- Tenstorrent/Wormhole profiler ingest through `tt_wormhole`
- Spike
- QEMU
- gem5

The goal is one config file and one command that can produce a combined SIT comparison report for the same logical workload.

High-level architecture references:

- `ARCHITECTURE.md`
- `WORKFLOW_ARCHITECTURE.md`
- `NEW_SIMULATOR_TEMPLATE.md`

Simulator workloads in this bundle run as baseline cases by default:

- no injected idle phases
- no injected stall phases
- workload-native branch/cache-conditioned stall behavior is still honored when you explicitly pass `--branch-mispredict` or `--cache-pressure`
- use `--inject-sim-phases` only when you want the older synthetic idle/stall phase injection back

The bundle now auto-calibrates TT-style work defaults when it has enough information:

- `tt_ops_per_zone` defaults from the workload proxy table when known
- `sim_ops_per_zone` defaults from that same table for simulator backends
- if you do not pass `--expected-work-rate`, the TT run derives it from `total_work_done / total_resident_us`
- auto-generated simulator runs inherit that TT-derived `expected_work_rate` automatically

The orchestrator can also manage simulator toolchains when you opt in:

- it resolves installed paths for `qemu`, `spike`, `pk`, and `gem5`
- it can attempt simulator toolchain installation through `device_handler/simulator_toolchain_manager.py`
- it feeds resolved binary paths into the backend runner automatically

In direct CLI mode, simulator targets now default to install-on-missing behavior:

- if a requested simulator backend is not found on the host, the wrapper will try to install it under `.toolchains/`
- this applies both to `--target tenstorrent` auto-fanout runs and simulator-only direct CLI runs
- current install plans assume an apt-based Linux environment for system packages

## Automatic Simulator Fan-Out

If you enable a `tt_wormhole` target and set `auto_run_simulators_for_tt` to `true`, the bundle will automatically generate simulator runs for the chosen Tenstorrent workload.

That means you can choose:

- one TT hardware workload
- one set of simulator templates

and the runner will expand that into:

- `tt_wormhole`
- `qemu`
- `spike`
- `gem5`

without listing each simulator as a separate target entry.

If simulator tools are missing, you can let the orchestrator try to set them up:

```bash
python3 device_handler/orchestrator.py \
  --workload tt_eltwise_binary \
  --target tenstorrent \
  --workload-size tt_128tile \
  --time-us 256 \
  --auto-install-simulator-tools \
  --simulator-toolchain-root .toolchains
```

The TT workload is translated into the simulator workload through `tt_to_simulator_workload_map`. The example config already includes the common mappings such as:

- `tt_matmul_multi` -> `matmul_multicore`
- `tt_matmul_single` -> `matmul`
- `tt_loopback` -> `fm_loopback`
- `tt_vecadd` -> `vecadd`
- `tt_eltwise_binary` -> `eltwise_binary`
- `tt_eltwise_sfpu` -> `eltwise_sfpu`

## Bundled TT Datasets

The bundle includes the Tenstorrent raw profiler dataset copied from `Phase-2/datasets/Tenstorrent_test_raw_files-main`.

For bundled TT workloads such as `tt_matmul_multi`, `tt_matmul_single`, `tt_loopback`, `tt_vecadd`, `tt_eltwise_binary`, `tt_eltwise_sfpu`, and `tt_custom_sfpi_add`, the orchestrator will automatically use:

- `datasets/Tenstorrent_test_raw_files-main/<workload>/profiler_logs/profile_log_device.csv`
- `datasets/Tenstorrent_test_raw_files-main/<workload>/profiler_logs/zone_src_locations.log`

when `tt_profile_csv` and `tt_zone_log` are left blank or still set to placeholder paths.

Sweep-specific bundled TT datasets are also resolved automatically from `workload_size` when present. Examples:

- `tt_eltwise_sfpu` + `tt_32tile` -> `datasets/Tenstorrent_test_raw_files-main/tt_eltwise_sfpu_tiles32`
- `tt_eltwise_binary` + `tt_128tile` -> `datasets/Tenstorrent_test_raw_files-main/tt_eltwise_binary_tiles128`
- `tt_matmul_single` + `tt_m640_n640_k640` -> `datasets/Tenstorrent_test_raw_files-main/tt_matmul_single_M640_N640_K640`
- `tt_matmul_multi` + `tt_m1280_n1280_k1280` -> `datasets/Tenstorrent_test_raw_files-main/tt_matmul_multi_M1280_N1280_K1280`

## Important Boundary

- `spike`, `qemu`, and `gem5` are generic RISC-V backends.
- They are useful comparison backends for a Tenstorrent-aligned workload contract.
- They are not full Tenstorrent microarchitectural simulators.
- The Tenstorrent side uses profiler logs and the `tt_wormhole` adapter.
- The simulator side now defaults to baseline workloads rather than synthetic idle/stall sensitivity cases.

## Switch Categories

- `device`: `tt_wormhole` / `tenstorrent`
- `simulator`: `gem5`, `qemu`, `spike`, `cpu`

The orchestrator groups switches before invoking `device_handler/backend_runner.py`:

- Shared switches: workload selection, window sizing, SIT normalization/classification, and synthetic phase toggles
- Simulator-only switches: `gem5_*`, `qemu_*`, `pk`, `isa`, `cores`, `inst_us`
- Tenstorrent device-only switches: `tt_profile_csv`, `tt_zone_log`, `tt_output_mode`, `tt_chip_freq_mhz`, `tt_ops_per_zone`, `tt_residency_model`, `tt_strict_*`

This keeps the Tenstorrent device handler connected to the orchestrator while preventing device-only switches from leaking into simulator runs.

### Platform Switch Table

All platforms inherit the shared switches below:

- `workload`, `workload_size`, `time_us`, `expected_work_rate`, `sim_ops_per_zone`, `sim_classification_mode`, `no_work_sit_mode`
- `branch_mispredict`, `cache_pressure`, `inject_sim_phases`, `sim_trace_only`

| Platform | Category | Platform-specific switches |
|---|---|---|
| `tt_wormhole` / `tenstorrent` | `device` | `tt_profile_csv`, `tt_zone_log`, `tt_output_mode`, `tt_chip_freq_mhz`, `tt_ops_per_zone`, `tt_residency_model`, `tt_strict_pairing`, `tt_strict_map_hit` |
| `gem5` | `simulator` | `cores`, `inst_us`, `gem5_bin`, `gem5_root`, `gem5_config`, `gem5_extra_args`, `gem5_cc`, `gem5_cpu_type`, `gem5_cpu_types`, `gem5_mem_size`, `gem5_adapter_mode`, `gem5_stats_period_us`, `gem5_ipc_active_thresh`, `gem5_stall_miss_thresh`, `gem5_l1_resident_thresh`, `gem5_mem_reqs_per_inst_thresh`, `gem5_idle_inst_thresh` |
| `qemu` | `simulator` | `inst_us`, `qemu_bin`, `qemu_cc`, `qemu_extra_args`, `allow_nonzero_exit` |
| `spike` | `simulator` | `spike_bin`, `spike_cc`, `isa`, `pk`, `inst_us` |
| `cpu` | `simulator` | No extra platform-only switches beyond the shared set |

## Calibration Table

The orchestration flow uses a small built-in workload calibration table to derive:

- `tt_ops_per_zone`
- `sim_ops_per_zone`
- expected total work
- expected work rate

This orchestrator-level TT calibration is intentionally limited to `qemu`, `spike`, and `gem5` when they are launched as Tenstorrent comparison backends from a `tt_wormhole` reference run. It is not applied as a generic cross-platform calibration layer for unrelated targets.

### Workload Calibration

| Workload | Canonical workload | Auto `ops_per_zone` |
|---|---|---:|
| `tt_vecadd` | `vecadd` | `1024` |
| `tt_eltwise_binary` | `eltwise_binary` | `1024` |
| `eltwise_binary_mul` | `eltwise_binary_mul` | `1024` |
| `tt_eltwise_sfpu` | `eltwise_sfpu` | `1024` |
| `tt_custom_sfpi_add` | `custom_sfpi_add` | `1024` |
| `tt_custom_sfpi_smoothstep` | `custom_sfpi_smoothstep` | `6144` |
| `tt_sfpu_chain` | `sfpu_chain` | `3072` |
| `tt_matmul_single` | `matmul_single` | `65536` |
| `tt_matmul_multi` | `matmul_multi` | `65536` |
| `matmul` | `matmul` | `65536` |
| `matmul_multicore` | `matmul_multicore` | `65536` |
| `matmul_shared` | `matmul_shared` | `65536` |

### Size Calibration

| Workload size | `ACTIVE_BOOST` |
|---|---:|
| `tt_tile` | `1` |
| `tt_1tile` | `1` |
| `tt_4tile` | `4` |
| `tt_32tile` | `32` |
| `tt_64tile` | `64` |
| `tt_128tile` | `128` |
| `tt_256tile` | `256` |
| `tt_1024tile` | `1024` |

For matmul-style sizes such as `tt_m640_n640_k640`, the bundle derives `ACTIVE_BOOST` from:

```text
tiles_M × tiles_N × tiles_K
where each tile is 32
```

### Derived Values

| Quantity | Formula |
|---|---|
| TT total expected work | `ACTIVE_BOOST × tt_ops_per_zone` |
| TT expected work rate | `(ACTIVE_BOOST × tt_ops_per_zone) / total_resident_us` |
| Default simulator total work | `ACTIVE_BOOST × sim_ops_per_zone` |
| Auto simulator expected work rate | `(ACTIVE_BOOST × sim_ops_per_zone) / time_us` |
| TT-derived simulator `sim_ops_per_zone` | `observed_work_total / ACTIVE_BOOST` |

Example for `tt_eltwise_binary` with `tt_128tile`:

| Field | Value |
|---|---:|
| `tt_ops_per_zone` | `1024` |
| `ACTIVE_BOOST` | `128` |
| TT expected total work | `131072` |
| TT expected work rate | `131072 / total_resident_us` |

### Simulator Toolchain Manager

The simulator side now includes a separate helper module:

- `device_handler/simulator_toolchain_manager.py`

It is responsible for:

- resolving binary paths for `qemu`, `spike`, `pk`, and `gem5`
- optionally installing missing simulator dependencies
- returning resolved paths to `device_handler/orchestrator.py`

Relevant wrapper options:

- `--auto-install-simulator-tools`
- `--simulator-toolchain-root`

Optional config block:

```json
{
  "simulator_toolchain": {
    "auto_install": true,
    "root_dir": ".toolchains",
    "gem5_ref": "",
    "spike_ref": "",
    "pk_ref": ""
  }
}
```

`gem5_ref`, `spike_ref`, and `pk_ref` are optional git refs if you want the simulator installer to pin a specific checkout.

## Folder Layout

- `device_handler/`: orchestrator, backend runner, simulator toolchain manager
- `sit_classifier/`: platform adapters and normalization logic
- `result_handler/`: SIT engine and result/export logic
- `ARCHITECTURE.md`: layer-by-layer structure map
- `WORKFLOW_ARCHITECTURE.md`: overall folder map and workflow diagram
- `NEW_SIMULATOR_TEMPLATE.md`: checklist for future simulator integration
- public Python entrypoints now live directly under `device_handler/` and `result_handler/`
- `run.sh`: convenience wrapper
- `bootstrap.sh`: local Python environment setup
- `configs/`: example orchestration config
- `dependencies/`: Python and system dependency notes
- `results/`: generated reports
- shared runtime assets: `schema/`, `configs/`, `datasets/`, `dependencies/`

## Quick Start

```bash
cd "riscbench tenstorrent"
bash bootstrap.sh
riscbench --workload tt_matmul_multi --target tenstorrent --workload-size test --time-us 256 --check-only
riscbench --workload tt_matmul_multi --target tenstorrent --workload-size test --time-us 256 --dry-run --skip-missing-tools
riscbench --workload tt_matmul_multi --target tenstorrent --workload-size test --time-us 256
```

That direct CLI path is the intended short form.

If you do not have Tenstorrent hardware on the machine, run simulator-only orchestration instead:

```bash
riscbench --workload tt_eltwise_binary --target simulator --simulators qemu,spike,gem5 --workload-size tt_128tile --time-us 256
riscbench --workload tt_eltwise_binary --target qemu --workload-size tt_128tile --time-us 256
```

In simulator-only mode, TT-style workload names are mapped to the backend workload automatically, for example `tt_eltwise_binary` becomes `eltwise_binary`.

If you want workload-native perturbations without synthetic phase injection, you can pass the flags directly:

```bash
riscbench --workload tt_vecadd --target tenstorrent --workload-size tt_64tile --branch-mispredict
riscbench --workload tt_vecadd --target tenstorrent --workload-size tt_64tile --cache-pressure
```

Use config mode only if you want more control:

```bash
cp configs/orchestration.example.json configs/my_run.json
./run.sh configs/my_run.json --check-only
```

To run the full bundled TT hardware sweep matrix and emit one metrics table row per case:

```bash
cd "riscbench tenstorrent"
python3 device_handler/orchestrator.py --config configs/tt_hw_sweeps_all.json
```

That config covers 21 TT cases:

- `tt_matmul_single`: `M320`, `M640`, `M960`, `M1280`
- `tt_matmul_multi`: `M320`, `M640`, `M960`, `M1280`
- `tt_sfpu_chain`: fixed run
- `tt_eltwise_sfpu`: `32`, `64`, `128` tiles
- `tt_eltwise_binary`: `32`, `64`, `128` tiles
- `tt_custom_sfpi_add`: `32`, `64`, `128` tiles
- `tt_custom_sfpi_smoothstep`: `32`, `64`, `128` tiles

The resulting `comparison_rows.csv` is the easiest per-run metrics table. It includes:

- `sit_median`, `sit_p95`
- `observed_flops_per_us_median`, `overall_observed_flops_per_us`, `observed_flops_total`
- `expected_work_rate`
- `residency_active_avg`, `residency_idle_avg`, `residency_stall_avg`
- `windows_total`, `resident_windows_total`
- `overall_window_sit_median`, `overall_window_sit_p95`

## Tenstorrent Hardware Mode

The Tenstorrent path has two supported modes:

1. Existing profiler logs:
   - point `tt_profile_csv` and `tt_zone_log` at already-generated files

2. Automatic hardware kickoff before ingest:
   - set `pre_run_cmd` for the `tt_wormhole` target
   - that command should run your TT workflow and leave behind the profiler files
   - after that, the bundle ingests them and computes the SIT summary

This lets one orchestration run gather:

- `tt_wormhole` SIT
- `spike` SIT
- `qemu` SIT
- `gem5` SIT

For `spike`, `qemu`, and `gem5`, use `--sim-trace-only` when you want raw
timeline-based SIT from the classified residency trace and do not want any
synthetic `work_done` markers or expected-work-rate normalization.

If you want the TT selection to drive the other backends automatically, keep only the `tt_wormhole` entry under `targets` and configure the simulator defaults under `simulator_templates`.

## One-Time Environment Setup For Short CLI

To keep the command short, set your backend paths once in the shell:

```bash
export QEMU_BIN=qemu-riscv64
export QEMU_CC=riscv64-linux-gnu-gcc
export PK=/absolute/path/to/pk
export GEM5_BIN=/absolute/path/to/gem5.opt
export GEM5_ROOT=/absolute/path/to/gem5
export GEM5_CC=riscv64-linux-gnu-gcc
```

You only need `TT_PROFILE_CSV` and `TT_ZONE_LOG` when you want to override the bundled dataset or point at freshly captured Tenstorrent hardware logs.

Then the short command stays close to the original RISCBench style:

```bash
riscbench --workload tt_matmul_multi --target tenstorrent --workload-size test --time-us 256
```

## Outputs

Each run writes a timestamped folder in `results/` with:

- `comparison_rows.csv`
- `comparison_wide.csv`
- `comparison.json`
- `logs/`
- `summaries/`

The row-wise CSV is easiest for debugging. The wide CSV is easiest for side-by-side comparison against the Tenstorrent reference row.
