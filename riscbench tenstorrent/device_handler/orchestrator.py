#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BUNDLE_ROOT = Path(__file__).resolve().parent.parent
if str(_BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUNDLE_ROOT))

from device_handler.simulator_toolchain_manager import ToolchainSettings, prepare_backend_toolchain
from sit_classifier.workload_calibration import read_tt_profile_chip_freq_mhz, resolve_size_active_boost

VALID_TARGETS = {"cpu", "spike", "qemu", "gem5", "tt_wormhole"}

FLAG_MAP = {
    "workload": "--workload",
    "workload_size": "--workload_size",
    "time_us": "--time_us",
    "expected_work_rate": "--expected-work-rate",
    "sim_ops_per_zone": "--sim-ops-per-zone",
    "sim_classification_mode": "--sim-classification-mode",
    "no_work_sit_mode": "--no-work-sit-mode",
    "cores": "--cores",
    "isa": "--isa",
    "pk": "--pk",
    "spike_bin": "--spike-bin",
    "spike_cc": "--spike-cc",
    "inst_us": "--inst_us",
    "resident_pc_ge": "--resident_pc_ge",
    "gem5_bin": "--gem5-bin",
    "gem5_root": "--gem5-root",
    "gem5_config": "--gem5-config",
    "gem5_extra_args": "--gem5-extra-args",
    "gem5_cc": "--gem5-cc",
    "gem5_cpu_type": "--gem5-cpu-type",
    "gem5_cpu_types": "--gem5-cpu-types",
    "gem5_mem_size": "--gem5-mem-size",
    "gem5_adapter_mode": "--gem5-adapter-mode",
    "gem5_stats_period_us": "--gem5-stats-period-us",
    "gem5_ipc_active_thresh": "--gem5-ipc-active-thresh",
    "gem5_stall_miss_thresh": "--gem5-stall-miss-thresh",
    "gem5_l1_resident_thresh": "--gem5-l1-resident-thresh",
    "gem5_mem_reqs_per_inst_thresh": "--gem5-mem-reqs-per-inst-thresh",
    "gem5_idle_inst_thresh": "--gem5-idle-inst-thresh",
    "qemu_bin": "--qemu-bin",
    "qemu_cc": "--qemu-cc",
    "qemu_extra_args": "--qemu-extra-args",
    "tt_profile_csv": "--tt-profile-csv",
    "tt_zone_log": "--tt-zone-log",
    "tt_output_mode": "--tt-output-mode",
    "tt_chip_freq_mhz": "--tt-chip-freq-mhz",
    "tt_ops_per_zone": "--tt-ops-per-zone",
    "tt_residency_model": "--tt-residency-model",
}

BOOL_FLAG_MAP = {
    "branch_mispredict": "--branch-mispredict",
    "cache_pressure": "--cache-pressure",
    "inject_sim_phases": "--inject-sim-phases",
    "sim_trace_only": "--sim-trace-only",
    "skip_post_processing": "--skip-post-processing",
    "practical": "--practical",
    "debug_sit": "--debug-sit",
    "allow_nonzero_exit": "--allow-nonzero-exit",
    "tt_strict_pairing": "--tt-strict-pairing",
    "tt_strict_map_hit": "--tt-strict-map-hit",
}

SHARED_VALUE_ARG_KEYS = frozenset(
    {
        "workload",
        "workload_size",
        "time_us",
        "expected_work_rate",
        "sim_ops_per_zone",
        "sim_classification_mode",
        "no_work_sit_mode",
        "resident_pc_ge",
    }
)

SHARED_BOOL_ARG_KEYS = frozenset(
    {
        "branch_mispredict",
        "cache_pressure",
        "inject_sim_phases",
        "sim_trace_only",
        "skip_post_processing",
        "practical",
        "debug_sit",
    }
)


@dataclass(frozen=True)
class BackendHandler:
    name: str
    category: str
    value_arg_keys: frozenset[str]
    bool_arg_keys: frozenset[str]

    def accepts_value_arg(self, key: str) -> bool:
        return key in self.value_arg_keys

    def accepts_bool_arg(self, key: str) -> bool:
        return key in self.bool_arg_keys


BACKEND_HANDLERS: dict[str, BackendHandler] = {
    "cpu": BackendHandler(
        name="cpu",
        category="simulator",
        value_arg_keys=SHARED_VALUE_ARG_KEYS,
        bool_arg_keys=SHARED_BOOL_ARG_KEYS,
    ),
    "spike": BackendHandler(
        name="spike",
        category="simulator",
        value_arg_keys=SHARED_VALUE_ARG_KEYS | frozenset({"isa", "pk", "spike_bin", "spike_cc", "inst_us"}),
        bool_arg_keys=SHARED_BOOL_ARG_KEYS,
    ),
    "qemu": BackendHandler(
        name="qemu",
        category="simulator",
        value_arg_keys=SHARED_VALUE_ARG_KEYS | frozenset({"qemu_bin", "qemu_cc", "qemu_extra_args", "inst_us"}),
        bool_arg_keys=SHARED_BOOL_ARG_KEYS | frozenset({"allow_nonzero_exit"}),
    ),
    "gem5": BackendHandler(
        name="gem5",
        category="simulator",
        value_arg_keys=SHARED_VALUE_ARG_KEYS
        | frozenset(
            {
                "cores",
                "inst_us",
                "gem5_bin",
                "gem5_root",
                "gem5_config",
                "gem5_extra_args",
                "gem5_cc",
                "gem5_cpu_type",
                "gem5_cpu_types",
                "gem5_mem_size",
                "gem5_adapter_mode",
                "gem5_stats_period_us",
                "gem5_ipc_active_thresh",
                "gem5_stall_miss_thresh",
                "gem5_l1_resident_thresh",
                "gem5_mem_reqs_per_inst_thresh",
                "gem5_idle_inst_thresh",
            }
        ),
        bool_arg_keys=SHARED_BOOL_ARG_KEYS,
    ),
    "tt_wormhole": BackendHandler(
        name="tt_wormhole",
        category="device",
        value_arg_keys=SHARED_VALUE_ARG_KEYS
        | frozenset(
            {
                "tt_profile_csv",
                "tt_zone_log",
                "tt_output_mode",
                "tt_chip_freq_mhz",
                "tt_ops_per_zone",
                "tt_residency_model",
            }
        ),
        bool_arg_keys=SHARED_BOOL_ARG_KEYS | frozenset({"tt_strict_pairing", "tt_strict_map_hit"}),
    ),
}

PATH_ARG_KEYS = {
    "pk",
    "spike_bin",
    "spike_cc",
    "gem5_bin",
    "gem5_root",
    "gem5_config",
    "tt_profile_csv",
    "tt_zone_log",
}

DEFAULT_METRICS = [
    "sit_median",
    "sit_p95",
    "observed_flops_per_us_median",
    "overall_observed_flops_per_us",
    "observed_flops_total",
    "observed_work_rate_median",
    "overall_observed_work_rate",
    "observed_work_total",
    "residency_active_avg",
    "residency_idle_avg",
    "residency_stall_avg",
    "windows_total",
    "resident_windows_total",
    "overall_window_sit_median",
    "overall_window_sit_p95",
]

DEFAULT_AUTO_SIM_ORDER = ["qemu", "spike", "gem5"]
TT_CALIBRATED_SIMULATORS = frozenset(DEFAULT_AUTO_SIM_ORDER)
DEFAULT_GEM5_STATS_TT_ARGS = {
    "no_work_sit_mode": "window_active",
    "gem5_ipc_active_thresh": 0.05,
    "gem5_stall_miss_thresh": 0.20,
    "gem5_l1_resident_thresh": 0.25,
    "gem5_mem_reqs_per_inst_thresh": 0.50,
    "gem5_idle_inst_thresh": 1.0,
}
REAL_TARGET_ALIASES = {
    "tenstorrent": "tt_wormhole",
    "tt_wormhole": "tt_wormhole",
    "real": "tt_wormhole",
    "sim": "simulator",
    "simulator": "simulator",
    "backend": "simulator",
}

DEFAULT_TT_TO_SIM_WORKLOAD_MAP: dict[str, Any] = {
    "tt_loopback": "fm_loopback",
    "tt_matmul_single": "matmul",
    "tt_matmul_multi": "matmul_multicore",
    "tt_vecadd": "vecadd",
    "tt_eltwise_binary": "eltwise_binary",
    "tt_eltwise_sfpu": "eltwise_sfpu",
    "tt_custom_sfpi_add": "custom_sfpi_add",
    "tt_custom_sfpi_smoothstep": "custom_sfpi_smoothstep",
}
TT_DATASET_DIR = Path("datasets") / "Tenstorrent_test_raw_files-main"
TT_TILE_SWEEP_RE = re.compile(r"^(?:tt_)?(\d+)tile$", re.IGNORECASE)
TT_MATMUL_SWEEP_RE = re.compile(
    r"^(?:tt_)?m(\d+)_n(\d+)_k(\d+)$",
    re.IGNORECASE,
)


def get_backend_handler(target_name: str) -> BackendHandler:
    handler = BACKEND_HANDLERS.get(str(target_name).strip())
    if handler is None:
        raise SystemExit(f"unsupported target: {target_name}")
    return handler


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_label(text: str) -> str:
    buf: list[str] = []
    for ch in str(text).lower():
        if ch.isalnum() or ch in {"-", "_"}:
            buf.append(ch)
        else:
            buf.append("_")
    cleaned = "".join(buf).strip("_")
    return cleaned or "run"


def has_tool(tool_or_path: str) -> bool:
    if not tool_or_path:
        return False
    if shutil.which(tool_or_path):
        return True
    return Path(tool_or_path).expanduser().exists()


def maybe_resolve_path(value: Any, base_dir: Path) -> Any:
    if not isinstance(value, str):
        return value
    raw = value.strip()
    if not raw:
        return value
    if raw.startswith("~") or raw.startswith(".") or "/" in raw:
        return str((base_dir / raw).expanduser().resolve()) if not Path(raw).is_absolute() else str(Path(raw).expanduser().resolve())
    return value


def should_autofill_tt_input(value: Any) -> bool:
    raw = str(value or "").strip()
    return raw == "" or raw.startswith("/absolute/path/to/")


def dataset_suffix_candidates(workload_size: str) -> list[str]:
    raw = str(workload_size or "").strip()
    if not raw:
        return []

    lowered = raw.lower()
    if lowered in {"test", "default", "base"}:
        return []

    out: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        item = str(value).strip()
        if not item or item in seen:
            return
        seen.add(item)
        out.append(item)

    match = TT_TILE_SWEEP_RE.match(lowered)
    if match:
        add(f"tiles{int(match.group(1))}")

    match = TT_MATMUL_SWEEP_RE.match(lowered)
    if match:
        m_dim, n_dim, k_dim = (int(match.group(i)) for i in range(1, 4))
        add(f"M{m_dim}_N{n_dim}_K{k_dim}")

    # Allow callers to pass the raw dataset suffix directly.
    add(raw)
    if lowered.startswith("tt_"):
        add(raw[3:])

    return out


def resolve_bundled_tt_inputs(bundle_root: Path, workload: str, workload_size: str | None = None) -> dict[str, str]:
    dataset_root = bundle_root / TT_DATASET_DIR
    workload_name = str(workload).strip()
    candidate_dirs: list[Path] = []
    for suffix in dataset_suffix_candidates(str(workload_size or "")):
        candidate_dirs.append(dataset_root / f"{workload_name}_{suffix}")
    candidate_dirs.append(dataset_root / workload_name)

    resolved: dict[str, str] = {}
    seen_dirs: set[Path] = set()
    for dataset_dir in candidate_dirs:
        if dataset_dir in seen_dirs or not dataset_dir.exists():
            continue
        seen_dirs.add(dataset_dir)
        profiler_dir = dataset_dir / "profiler_logs"
        if not profiler_dir.exists():
            continue
        profile_csv = profiler_dir / "profile_log_device.csv"
        if profile_csv.exists():
            resolved["tt_profile_csv"] = str(profile_csv.resolve())
        for candidate in ("zone_src_locations.log", "new_zone_src_locations.log"):
            zone_log = profiler_dir / candidate
            if zone_log.exists():
                resolved["tt_zone_log"] = str(zone_log.resolve())
                break
        if resolved.get("tt_profile_csv") and resolved.get("tt_zone_log"):
            return resolved
    return resolved


def apply_bundled_tt_inputs(cfg: dict[str, Any], bundle_root: Path) -> dict[str, Any]:
    updated = dict(cfg)
    shared_args = dict(updated.get("shared_args", updated.get("shared", {})))
    targets = []
    for target in list(updated.get("targets", [])):
        target_copy = dict(target)
        if str(target_copy.get("name", "")).strip() != "tt_wormhole":
            targets.append(target_copy)
            continue

        args_obj = dict(target_copy.get("args", {}))
        workload = str(args_obj.get("workload", "")).strip()
        workload_size = str(
            args_obj.get("workload_size")
            or shared_args.get("workload_size")
            or ""
        ).strip()
        if workload:
            bundled_inputs = resolve_bundled_tt_inputs(
                bundle_root,
                workload,
                workload_size,
            )
            if bundled_inputs and should_autofill_tt_input(args_obj.get("tt_profile_csv")):
                args_obj["tt_profile_csv"] = bundled_inputs.get("tt_profile_csv", args_obj.get("tt_profile_csv", ""))
            if bundled_inputs and should_autofill_tt_input(args_obj.get("tt_zone_log")):
                args_obj["tt_zone_log"] = bundled_inputs.get("tt_zone_log", args_obj.get("tt_zone_log", ""))
        target_copy["args"] = args_obj
        targets.append(target_copy)

    updated["targets"] = targets
    return updated


def normalize_args(args_obj: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in args_obj.items():
        if key in PATH_ARG_KEYS:
            normalized[key] = maybe_resolve_path(value, base_dir)
        else:
            normalized[key] = value
    return normalized


def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged.update(override)
    return merged


def parse_simulator_list(spec: str) -> list[str]:
    sims = [tok.strip() for tok in str(spec).split(",") if tok.strip()]
    invalid = [sim for sim in sims if sim not in DEFAULT_AUTO_SIM_ORDER]
    if invalid:
        raise SystemExit(
            "Unsupported simulator(s) in --simulators: "
            + ", ".join(invalid)
            + ". Valid values are: "
            + ", ".join(DEFAULT_AUTO_SIM_ORDER)
        )
    return sims or list(DEFAULT_AUTO_SIM_ORDER)


def build_env(shared_env: dict[str, Any], target_env: dict[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    for source in (shared_env, target_env):
        for key, value in source.items():
            env[str(key)] = str(value)
    return env


def determine_reference_label(targets: list[dict[str, Any]], explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for target in targets:
        if not bool(target.get("enabled", True)):
            continue
        if get_backend_handler(str(target.get("name", "")).strip()).category == "device":
            return str(target.get("label", "")).strip() or "tt_wormhole"
    for target in targets:
        if bool(target.get("enabled", True)):
            return str(target.get("label", "")).strip() or str(target.get("name", "")).strip()
    return None


def resolve_simulator_workload(
    tt_workload: str,
    backend_name: str,
    tt_target: dict[str, Any],
    cfg: dict[str, Any],
) -> str | None:
    tt_args = dict(tt_target.get("args", {}))
    direct_override = str(tt_args.get("simulator_workload", "")).strip()
    if direct_override:
        return direct_override

    per_backend_override = tt_args.get("simulator_workloads", {})
    if isinstance(per_backend_override, dict):
        value = str(per_backend_override.get(backend_name, "")).strip()
        if value:
            return value

    mapping = dict(DEFAULT_TT_TO_SIM_WORKLOAD_MAP)
    mapping.update(dict(cfg.get("tt_to_simulator_workload_map", {})))
    mapped = mapping.get(tt_workload)
    if isinstance(mapped, str):
        value = mapped.strip()
        return value or None
    if isinstance(mapped, dict):
        per_backend = str(mapped.get(backend_name, "")).strip()
        if per_backend:
            return per_backend
        fallback = str(mapped.get("default", "")).strip()
        return fallback or None
    return None


def build_cli_mode_config(args: argparse.Namespace, bundle_root: Path) -> dict[str, Any]:
    requested_target = str(args.target).strip()
    real_target = REAL_TARGET_ALIASES.get(requested_target, requested_target)
    simulator_names = parse_simulator_list(args.simulators)
    tt_profile_csv = str(args.tt_profile_csv or os.environ.get("TT_PROFILE_CSV", "")).strip()
    tt_zone_log = str(args.tt_zone_log or os.environ.get("TT_ZONE_LOG", "")).strip()
    bundled_inputs = resolve_bundled_tt_inputs(bundle_root, str(args.workload))
    if should_autofill_tt_input(tt_profile_csv):
        tt_profile_csv = bundled_inputs.get("tt_profile_csv", tt_profile_csv)
    if should_autofill_tt_input(tt_zone_log):
        tt_zone_log = bundled_inputs.get("tt_zone_log", tt_zone_log)

    cfg: dict[str, Any] = {
        "comparison_label": str(args.comparison_label or f"{sanitize_label(args.workload)}_vs_riscv_backends"),
        "logical_workload": str(args.workload),
        "reference_label": "tenstorrent_hw" if real_target == "tt_wormhole" else None,
        "python": sys.executable,
        "auto_run_simulators_for_tt": real_target == "tt_wormhole",
        "auto_simulator_targets": simulator_names,
        "tt_to_simulator_workload_map": dict(DEFAULT_TT_TO_SIM_WORKLOAD_MAP),
        "shared_args": {
            "workload_size": str(args.workload_size),
            "time_us": float(args.time_us),
            "resident_pc_ge": str(args.resident_pc_ge),
        },
        "shared_env": {},
        "targets": [],
        "simulator_templates": {},
        "simulator_toolchain": {
            "auto_install": bool(args.auto_install_simulator_tools),
            "root_dir": str(args.simulator_toolchain_root or (bundle_root / ".toolchains")),
        },
    }

    if args.expected_work_rate is not None:
        cfg["shared_args"]["expected_work_rate"] = float(args.expected_work_rate)
    if args.sim_ops_per_zone is not None:
        cfg["shared_args"]["sim_ops_per_zone"] = int(args.sim_ops_per_zone)
    if args.sim_classification_mode:
        cfg["shared_args"]["sim_classification_mode"] = str(args.sim_classification_mode)
    if getattr(args, "no_work_sit_mode", None):
        cfg["shared_args"]["no_work_sit_mode"] = str(args.no_work_sit_mode)
    if args.sim_trace_only:
        cfg["shared_args"]["sim_trace_only"] = True
    if args.branch_mispredict:
        cfg["shared_args"]["branch_mispredict"] = True
    if args.cache_pressure:
        cfg["shared_args"]["cache_pressure"] = True
    if args.inject_sim_phases:
        cfg["shared_args"]["inject_sim_phases"] = True
    if getattr(args, "inst_us", None) is not None:
        cfg["shared_args"]["inst_us"] = float(args.inst_us)
    if getattr(args, "cores", None) is not None:
        cfg["shared_args"]["cores"] = int(args.cores)
    if getattr(args, "skip_post_processing", False):
        cfg["shared_args"]["skip_post_processing"] = True
    if getattr(args, "practical", False):
        cfg["shared_args"]["practical"] = True
    if getattr(args, "debug_sit", False):
        cfg["shared_args"]["debug_sit"] = True

    if real_target == "tt_wormhole":
        _tt_args: dict[str, Any] = {
            "workload": str(args.workload),
            "tt_profile_csv": tt_profile_csv,
            "tt_zone_log": tt_zone_log,
            "tt_output_mode": str(args.tt_output_mode),
            "tt_residency_model": str(args.tt_residency_model),
        }
        if getattr(args, "tt_chip_freq_mhz", None) is not None:
            _tt_args["tt_chip_freq_mhz"] = int(args.tt_chip_freq_mhz)
        if getattr(args, "tt_ops_per_zone", None) is not None:
            _tt_args["tt_ops_per_zone"] = float(args.tt_ops_per_zone)
        if getattr(args, "tt_strict_pairing", None) is not None:
            _tt_args["tt_strict_pairing"] = bool(args.tt_strict_pairing)
        if getattr(args, "tt_strict_map_hit", None) is not None:
            _tt_args["tt_strict_map_hit"] = bool(args.tt_strict_map_hit)
        cfg["targets"] = [
            {
                "name": "tt_wormhole",
                "label": "tenstorrent_hw",
                "enabled": True,
                "pre_run_cmd": str(args.pre_run_cmd or ""),
                "pre_run_cwd": str(args.pre_run_cwd or bundle_root),
                "env": {},
                "args": _tt_args,
            }
        ]
    elif real_target == "simulator":
        cfg["comparison_label"] = str(args.comparison_label or f"{sanitize_label(args.workload)}_simulator_suite")
    elif real_target in BACKEND_HANDLERS and get_backend_handler(real_target).category == "simulator":
        simulator_names = [real_target]
        cfg["auto_simulator_targets"] = simulator_names
        cfg["comparison_label"] = str(args.comparison_label or f"{sanitize_label(args.workload)}_{sanitize_label(real_target)}")
    else:
        raise SystemExit(
            "Use --target tenstorrent, --target simulator, or a simulator backend "
            "like qemu, spike, gem5, or cpu."
        )

    if "qemu" in simulator_names:
        _qemu_args: dict[str, Any] = {
            "qemu_bin": str(args.qemu_bin or os.environ.get("QEMU_BIN", "qemu-riscv64")),
            "qemu_cc": str(args.qemu_cc or os.environ.get("QEMU_CC", "riscv64-linux-gnu-gcc")),
            "allow_nonzero_exit": bool(args.allow_nonzero_exit),
        }
        if str(getattr(args, "qemu_extra_args", "") or "").strip():
            _qemu_args["qemu_extra_args"] = str(args.qemu_extra_args)
        cfg["simulator_templates"]["qemu"] = {
            "enabled": True,
            "label": "qemu_backend",
            "args": _qemu_args,
        }

    if "spike" in simulator_names:
        cfg["simulator_templates"]["spike"] = {
            "enabled": True,
            "label": "spike_backend",
            "args": {
                "spike_bin": str(args.spike_bin or os.environ.get("SPIKE_BIN", "spike")),
                "spike_cc": str(args.spike_cc or os.environ.get("SPIKE_CC", "riscv64-unknown-elf-gcc")),
                "pk": str(args.pk or os.environ.get("PK", "")),
                "isa": str(args.isa),
            },
        }

    if "gem5" in simulator_names:
        gem5_args = {
            "gem5_bin": str(args.gem5_bin or os.environ.get("GEM5_BIN", "gem5.opt")),
            "gem5_cc": str(args.gem5_cc or os.environ.get("GEM5_CC", "riscv64-linux-gnu-gcc")),
            "gem5_root": str(args.gem5_root or os.environ.get("GEM5_ROOT", "")),
            "gem5_cpu_type": str(args.gem5_cpu_type),
            "gem5_adapter_mode": str(args.gem5_adapter_mode),
        }
        if args.gem5_ipc_active_thresh is not None:
            gem5_args["gem5_ipc_active_thresh"] = float(args.gem5_ipc_active_thresh)
        if args.gem5_stall_miss_thresh is not None:
            gem5_args["gem5_stall_miss_thresh"] = float(args.gem5_stall_miss_thresh)
        if args.gem5_l1_resident_thresh is not None:
            gem5_args["gem5_l1_resident_thresh"] = float(args.gem5_l1_resident_thresh)
        if args.gem5_mem_reqs_per_inst_thresh is not None:
            gem5_args["gem5_mem_reqs_per_inst_thresh"] = float(args.gem5_mem_reqs_per_inst_thresh)
        if args.gem5_idle_inst_thresh is not None:
            gem5_args["gem5_idle_inst_thresh"] = float(args.gem5_idle_inst_thresh)
        if str(args.gem5_adapter_mode) == "stats":
            gem5_args.update(DEFAULT_GEM5_STATS_TT_ARGS)
            if args.gem5_ipc_active_thresh is not None:
                gem5_args["gem5_ipc_active_thresh"] = float(args.gem5_ipc_active_thresh)
            if args.gem5_stall_miss_thresh is not None:
                gem5_args["gem5_stall_miss_thresh"] = float(args.gem5_stall_miss_thresh)
            if args.gem5_l1_resident_thresh is not None:
                gem5_args["gem5_l1_resident_thresh"] = float(args.gem5_l1_resident_thresh)
            if args.gem5_mem_reqs_per_inst_thresh is not None:
                gem5_args["gem5_mem_reqs_per_inst_thresh"] = float(args.gem5_mem_reqs_per_inst_thresh)
            if args.gem5_idle_inst_thresh is not None:
                gem5_args["gem5_idle_inst_thresh"] = float(args.gem5_idle_inst_thresh)
        if getattr(args, "gem5_config", None):
            gem5_args["gem5_config"] = str(args.gem5_config)
        if str(getattr(args, "gem5_extra_args", "") or "").strip():
            gem5_args["gem5_extra_args"] = str(args.gem5_extra_args)
        if str(getattr(args, "gem5_cpu_types", "") or "").strip():
            gem5_args["gem5_cpu_types"] = str(args.gem5_cpu_types)
        if str(getattr(args, "gem5_mem_size", "") or "").strip():
            gem5_args["gem5_mem_size"] = str(args.gem5_mem_size)
        if getattr(args, "gem5_stats_period_us", None) is not None:
            gem5_args["gem5_stats_period_us"] = float(args.gem5_stats_period_us)
        cfg["simulator_templates"]["gem5"] = {
            "enabled": True,
            "label": "gem5_backend",
            "args": gem5_args,
        }

    if real_target != "tt_wormhole":
        cfg["auto_run_simulators_for_tt"] = False
        simulator_targets: list[dict[str, Any]] = []
        synthetic_tt_target = {"args": {"workload": str(args.workload)}}
        for backend_name in simulator_names:
            template = dict(cfg["simulator_templates"].get(backend_name, {}))
            if not template:
                continue
            sim_workload = resolve_simulator_workload(str(args.workload), backend_name, synthetic_tt_target, cfg) or str(args.workload)
            template_args = normalize_args(dict(template.get("args", {})), bundle_root)
            template_args["workload"] = sim_workload
            simulator_targets.append(
                {
                    "name": backend_name,
                    "label": str(template.get("label", "")).strip() or f"{backend_name}_backend",
                    "enabled": bool(template.get("enabled", True)),
                    "env": dict(template.get("env", {})),
                    "args": template_args,
                }
            )
        cfg["targets"] = simulator_targets

    return cfg


def expand_auto_simulator_targets(cfg: dict[str, Any], targets: list[dict[str, Any]], base_dir: Path) -> list[dict[str, Any]]:
    if not bool(cfg.get("auto_run_simulators_for_tt", False)):
        return list(targets)

    simulator_order = list(cfg.get("auto_simulator_targets", DEFAULT_AUTO_SIM_ORDER))
    simulator_templates = dict(cfg.get("simulator_templates", {}))
    if not simulator_order:
        return list(targets)

    expanded: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for target in targets:
        expanded.append(target)
        label = str(target.get("label", "")).strip() or str(target.get("name", "")).strip()
        seen_pairs.add((str(target.get("name", "")).strip(), label))

        if not bool(target.get("enabled", True)):
            continue
        if str(target.get("name", "")).strip() != "tt_wormhole":
            continue

        tt_args = normalize_args(dict(target.get("args", {})), base_dir)
        tt_workload = str(tt_args.get("workload", "")).strip()
        if not tt_workload:
            continue

        for backend_name in simulator_order:
            template = dict(simulator_templates.get(backend_name, {}))
            if not template:
                continue
            if not bool(template.get("enabled", True)):
                continue

            sim_workload = resolve_simulator_workload(tt_workload, backend_name, target, cfg)
            if not sim_workload:
                continue

            auto_label = str(template.get("label", "")).strip() or f"{label}__{backend_name}"
            pair = (backend_name, auto_label)
            if pair in seen_pairs:
                continue

            template_args = normalize_args(dict(template.get("args", {})), base_dir)
            auto_args = merge_dicts(template_args, {"workload": sim_workload})

            # Derive inst_us from TT chip frequency so simulator time scale matches
            # TT's cycle-based time: inst_us = 1 / chip_freq_mhz (assumes IPC≈1).
            if "inst_us" not in template_args:
                chip_freq_mhz = float(
                    tt_args.get("tt_chip_freq_mhz")
                    or cfg.get("shared_args", {}).get("tt_chip_freq_mhz")
                    or read_tt_profile_chip_freq_mhz(tt_args.get("tt_profile_csv"))
                    or 0.0
                )
                if chip_freq_mhz > 0.0:
                    auto_args["inst_us"] = round(1.0 / chip_freq_mhz, 9)

            auto_target = {
                "name": backend_name,
                "label": auto_label,
                "enabled": True,
                "env": dict(template.get("env", {})),
                "args": auto_args,
                "auto_generated_from_tt": label,
                # Orchestrator-level TT calibration inheritance is intentionally
                # limited to TT reference fan-out into qemu/spike/gem5.
                "tt_reference_calibration": backend_name in TT_CALIBRATED_SIMULATORS,
            }
            expanded.append(auto_target)
            seen_pairs.add(pair)

    return expanded


def has_enabled_tt_reference_target(targets: list[dict[str, Any]]) -> bool:
    for target in targets:
        if not bool(target.get("enabled", True)):
            continue
        if str(target.get("name", "")).strip() == "tt_wormhole":
            return True
    return False


def should_apply_tt_reference_calibration(
    target: dict[str, Any],
    handler: BackendHandler,
    tt_reference_present: bool,
) -> bool:
    # Keep TT-derived calibration tightly scoped:
    # - only when a Tenstorrent hardware reference target is part of the run
    # - only for qemu/spike/gem5 comparison backends
    # - only for targets explicitly marked as TT-calibrated by the orchestrator/config
    if not tt_reference_present:
        return False
    if handler.name not in TT_CALIBRATED_SIMULATORS:
        return False
    return bool(target.get("tt_reference_calibration", False))


def static_prereq_errors(target_name: str, merged_args: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    handler = get_backend_handler(target_name)

    if handler.name == "cpu":
        if not has_tool("gcc"):
            errs.append("gcc")
        return errs

    if handler.name == "spike":
        spike_bin = str(merged_args.get("spike_bin", "spike")).strip()
        spike_cc = str(merged_args.get("spike_cc", "riscv64-unknown-elf-gcc")).strip()
        if not has_tool(spike_bin):
            errs.append(f"spike binary not found: {spike_bin}")
        if not has_tool(spike_cc):
            errs.append(f"spike cc not found: {spike_cc}")
        pk_path = str(merged_args.get("pk", "")).strip()
        if not pk_path:
            errs.append("--pk")
        elif not Path(pk_path).expanduser().exists():
            errs.append(f"pk path not found: {pk_path}")
        return errs

    if handler.name == "qemu":
        qemu_bin = str(merged_args.get("qemu_bin", "qemu-riscv64")).strip()
        qemu_cc = str(merged_args.get("qemu_cc", "riscv64-linux-gnu-gcc")).strip()
        if not has_tool(qemu_bin):
            errs.append(f"qemu binary not found: {qemu_bin}")
        if not has_tool(qemu_cc):
            errs.append(f"qemu cc not found: {qemu_cc}")
        return errs

    if handler.name == "gem5":
        gem5_bin = str(merged_args.get("gem5_bin", "gem5.opt")).strip()
        gem5_cc = str(merged_args.get("gem5_cc", "riscv64-linux-gnu-gcc")).strip()
        if not has_tool(gem5_bin):
            errs.append(f"gem5 binary not found: {gem5_bin}")
        if not has_tool(gem5_cc):
            errs.append(f"gem5 cc not found: {gem5_cc}")
        return errs

    return errs


def runtime_input_errors(target_name: str, merged_args: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    handler = get_backend_handler(target_name)
    if handler.category != "device":
        return errs
    profile_csv = str(merged_args.get("tt_profile_csv", "")).strip()
    zone_log = str(merged_args.get("tt_zone_log", "")).strip()
    if not profile_csv:
        errs.append("--tt-profile-csv")
    elif not Path(profile_csv).expanduser().exists():
        errs.append(f"tt profile csv not found: {profile_csv}")
    if not zone_log:
        errs.append("--tt-zone-log")
    elif not Path(zone_log).expanduser().exists():
        errs.append(f"tt zone log not found: {zone_log}")
    return errs


def run_logged_command(
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    dry_run: bool,
    show_command: bool,
) -> int:
    line = " ".join(cmd)
    if show_command:
        print(f"$ {line}")
    if dry_run:
        log_path.write_text(f"[dry-run]\n{line}\n", encoding="utf-8")
        return 0
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_path.write_text(proc.stdout or "", encoding="utf-8")
    return proc.returncode


def run_shell_command(
    command: str,
    cwd: Path,
    env: dict[str, str],
    log_path: Path,
    dry_run: bool,
    show_command: bool,
) -> int:
    if show_command:
        print(f"$ {command}")
    if dry_run:
        log_path.write_text(f"[dry-run]\n{command}\n", encoding="utf-8")
        return 0
    proc = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_path.write_text(proc.stdout or "", encoding="utf-8")
    return proc.returncode


def build_riscvbench_command(
    bundle_root: Path,
    python_exec: str,
    target_name: str,
    merged_args: dict[str, Any],
) -> list[str]:
    handler = get_backend_handler(target_name)
    cmd = [python_exec, str(bundle_root / "device_handler" / "backend_runner.py"), "--target", target_name]
    for key, value in merged_args.items():
        if key in {"target", "label", "enabled"}:
            continue
        if key in BOOL_FLAG_MAP:
            if not handler.accepts_bool_arg(key):
                continue
            if bool(value):
                cmd.append(BOOL_FLAG_MAP[key])
            continue
        flag = FLAG_MAP.get(key)
        if flag is None:
            continue
        if not handler.accepts_value_arg(key):
            continue
        if value is None:
            continue
        value_s = str(value).strip()
        if not value_s:
            continue
        cmd.extend([flag, value_s])
    return cmd


def locate_latest_summary(bundle_root: Path, target_name: str, workload: str, started_at: float) -> Path | None:
    if not workload:
        return None
    base = bundle_root / "runs" / target_name / workload
    if not base.exists():
        return None

    candidates: list[tuple[bool, int, float, Path]] = []
    for name, priority in (("run_summary.json", 1), ("summary.json", 0)):
        for path in base.rglob(name):
            stat = path.stat()
            candidates.append((stat.st_mtime >= started_at - 1.0, priority, stat.st_mtime, path))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][3]


def write_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_wide_row(
    comparison_label: str,
    logical_workload: str,
    reference_label: str | None,
    metrics: list[str],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    wide: dict[str, Any] = {
        "comparison_label": comparison_label,
        "logical_workload": logical_workload,
        "reference_label": reference_label,
    }
    keep_keys = [
        "status",
        "target",
        "workload",
        "workload_size",
        "adapter_name",
        "run_dir",
        "summary_path",
    ] + metrics
    delta_keys = [f"{metric}_delta_vs_reference" for metric in metrics]
    for row in rows:
        prefix = sanitize_label(str(row.get("label", row.get("target", "run"))))
        for key in keep_keys + delta_keys:
            if key in row:
                wide[f"{prefix}__{key}"] = row[key]
    return wide


def add_reference_deltas(rows: list[dict[str, Any]], metrics: list[str], reference_label: str | None) -> None:
    if not reference_label:
        return
    ref = None
    for row in rows:
        if str(row.get("label", "")) == reference_label and str(row.get("status", "")) == "ok":
            ref = row
            break
    if ref is None:
        return

    for row in rows:
        if str(row.get("status", "")) != "ok":
            continue
        for metric in metrics:
            cur = row.get(metric)
            base = ref.get(metric)
            key = f"{metric}_delta_vs_reference"
            if isinstance(cur, (int, float)) and isinstance(base, (int, float)):
                row[key] = cur - base


def format_summary_metric(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return "-"


def print_results_summary(rows: list[dict[str, Any]], reference_label: str | None) -> None:
    if not rows:
        return

    print("\nResults summary")
    for row in rows:
        label = str(row.get("label", row.get("target", "run")))
        target = str(row.get("target", ""))
        status = str(row.get("status", ""))
        workload = str(row.get("workload", ""))

        if status == "ok":
            summary = (
                f"- {label} [{target}] {workload}: "
                f"sit={format_summary_metric(row.get('sit_median'))}, "
                f"p95={format_summary_metric(row.get('sit_p95'))}, "
                f"obs_flops/us={format_summary_metric(row.get('overall_observed_flops_per_us', row.get('overall_observed_work_rate')))}, "
                f"active={format_summary_metric(row.get('residency_active_avg'))}, "
                f"idle={format_summary_metric(row.get('residency_idle_avg'))}, "
                f"stall={format_summary_metric(row.get('residency_stall_avg'))}, "
                f"windows={format_summary_metric(row.get('windows_total'))}"
            )
            if reference_label and label != reference_label and "sit_median_delta_vs_reference" in row:
                summary += f", delta_vs_{reference_label}={format_summary_metric(row.get('sit_median_delta_vs_reference'))}"
            print(summary)
            continue

        error = str(row.get("error", "")).strip()
        suffix = f": {error}" if error else ""
        print(f"- {label} [{target}] {workload}: {status}{suffix}")


def resolve_output_dir(bundle_root: Path, config_base_dir: Path, cfg: dict[str, Any]) -> Path:
    explicit = str(cfg.get("output_dir", "")).strip()
    if explicit:
        out_dir = Path(explicit)
        if not out_dir.is_absolute():
            out_dir = config_base_dir / out_dir
        return out_dir.resolve()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return (bundle_root / "results" / stamp).resolve()


def find_bundle_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Single orchestration entrypoint for TT hardware ingest plus RISC-V simulator backends."
    )
    ap.add_argument("--config", default=None, help="Path to orchestration JSON config")
    ap.add_argument("--workload", default=None, help="Logical TT workload label for direct CLI mode")
    ap.add_argument(
        "--target",
        default=None,
        help="Direct CLI target: tenstorrent, simulator, or a specific backend like qemu/spike/gem5/cpu",
    )
    ap.add_argument("--workload-size", dest="workload_size", default="test")
    ap.add_argument("--time-us", dest="time_us", type=float, default=256.0)
    ap.add_argument(
        "--expected-work-rate",
        dest="expected_work_rate",
        type=float,
        default=None,
        help="Optional fixed expected work rate. If omitted, simulator runs inherit the TT reference calibration when available.",
    )
    ap.add_argument("--sim-ops-per-zone", dest="sim_ops_per_zone", type=int, default=None)
    ap.add_argument("--sim-classification-mode", dest="sim_classification_mode", default="strict", choices=["strict", "compute_biased"])
    ap.add_argument("--sim-trace-only", dest="sim_trace_only", action="store_true")
    ap.add_argument("--no-work-sit-mode", dest="no_work_sit_mode", default=None, choices=["global_active", "window_active"])
    ap.add_argument("--branch-mispredict", action="store_true")
    ap.add_argument("--cache-pressure", action="store_true")
    ap.add_argument("--inject-sim-phases", action="store_true")
    ap.add_argument("--inst-us", dest="inst_us", type=float, default=None, help="Instruction duration in microseconds (spike/qemu/gem5). Overrides the backend default of 1.0 us/inst.")
    ap.add_argument("--cores", type=int, default=None, help="Number of cores to simulate (gem5 only).")
    ap.add_argument("--skip-post-processing", dest="skip_post_processing", action="store_true", help="Skip post-processing and SIT computation after the simulator run.")
    ap.add_argument("--practical", action="store_true", help="Enable practical SIT mode (suppresses synthetic phase injection).")
    ap.add_argument("--debug-sit", dest="debug_sit", action="store_true", help="Emit verbose per-window SIT debug output.")
    ap.add_argument("--resident-pc-ge", dest="resident_pc_ge", default="0x80000000")
    ap.add_argument("--simulators", default="qemu,spike,gem5", help="Comma-separated simulator list for direct CLI mode")
    ap.add_argument("--comparison-label", default=None, help="Optional report label for direct CLI mode")
    ap.add_argument("--tt-profile-csv", dest="tt_profile_csv", default=None)
    ap.add_argument("--tt-zone-log", dest="tt_zone_log", default=None)
    ap.add_argument("--tt-output-mode", dest="tt_output_mode", default="tile")
    ap.add_argument("--tt-residency-model", dest="tt_residency_model", default="kernel_envelope")
    ap.add_argument("--tt-chip-freq-mhz", dest="tt_chip_freq_mhz", type=int, default=None, help="Override Tenstorrent chip frequency in MHz.")
    ap.add_argument("--tt-ops-per-zone", dest="tt_ops_per_zone", type=float, default=None, help="Work-done units per explicit throughput zone for tt_wormhole (default 1024).")
    ap.add_argument("--tt-strict-pairing", dest="tt_strict_pairing", action="store_true", help="tt_wormhole: fail on unmatched ZONE_START/END events.")
    ap.add_argument("--tt-no-strict-pairing", dest="tt_strict_pairing", action="store_false", help="tt_wormhole: allow unmatched ZONE_START/END events.")
    ap.add_argument("--tt-strict-map-hit", dest="tt_strict_map_hit", action="store_true", help="tt_wormhole: fail on zone-map misses.")
    ap.add_argument("--tt-no-strict-map-hit", dest="tt_strict_map_hit", action="store_false", help="tt_wormhole: allow zone-map misses.")
    ap.add_argument("--pre-run-cmd", dest="pre_run_cmd", default="")
    ap.add_argument("--pre-run-cwd", dest="pre_run_cwd", default="")
    ap.add_argument("--qemu-bin", dest="qemu_bin", default=None)
    ap.add_argument("--qemu-cc", dest="qemu_cc", default=None)
    ap.add_argument("--allow-nonzero-exit", action="store_true")
    ap.add_argument("--qemu-extra-args", dest="qemu_extra_args", default="", help="Extra arguments forwarded to qemu before the program path.")
    ap.add_argument("--spike-bin", dest="spike_bin", default=None)
    ap.add_argument("--spike-cc", dest="spike_cc", default=None)
    ap.add_argument("--pk", default=None)
    ap.add_argument("--isa", default="RV64GC")
    ap.add_argument("--gem5-bin", dest="gem5_bin", default=None)
    ap.add_argument("--gem5-root", dest="gem5_root", default=None)
    ap.add_argument("--gem5-cc", dest="gem5_cc", default=None)
    ap.add_argument("--gem5-cpu-type", dest="gem5_cpu_type", default="TimingSimpleCPU")
    ap.add_argument(
        "--gem5-adapter-mode",
        dest="gem5_adapter_mode",
        default="exec",
        choices=["stats", "exec"],
    )
    ap.add_argument("--gem5-ipc-active-thresh", dest="gem5_ipc_active_thresh", type=float, default=None)
    ap.add_argument("--gem5-stall-miss-thresh", dest="gem5_stall_miss_thresh", type=float, default=None)
    ap.add_argument("--gem5-l1-resident-thresh", dest="gem5_l1_resident_thresh", type=float, default=None)
    ap.add_argument("--gem5-mem-reqs-per-inst-thresh", dest="gem5_mem_reqs_per_inst_thresh", type=float, default=None)
    ap.add_argument("--gem5-idle-inst-thresh", dest="gem5_idle_inst_thresh", type=float, default=None)
    ap.add_argument("--gem5-config", dest="gem5_config", default=None, help="Path to an alternate gem5 se.py config script.")
    ap.add_argument("--gem5-extra-args", dest="gem5_extra_args", default="", help="Extra arguments appended to the gem5 command after se.py.")
    ap.add_argument("--gem5-cpu-types", dest="gem5_cpu_types", default="", help="Comma-separated per-core gem5 CPU types, e.g. TimingSimpleCPU,MinorCPU.")
    ap.add_argument("--gem5-mem-size", dest="gem5_mem_size", default="512MB", help="gem5 simulated memory size (e.g. 512MB, 1GB).")
    ap.add_argument("--gem5-stats-period-us", dest="gem5_stats_period_us", type=float, default=None, help="gem5 periodic stats dump interval in microseconds (stats adapter mode).")
    ap.add_argument("--dry-run", action="store_true", help="Print commands and write dry-run logs without executing")
    ap.add_argument("--check-only", action="store_true", help="Validate dependencies and config without running workloads")
    ap.add_argument("--show-commands", action="store_true", help="Echo backend commands to stdout while running")
    ap.add_argument(
        "--skip-missing-tools",
        action="store_true",
        help="Mark targets with missing tools as skipped instead of failing the whole run",
    )
    ap.add_argument(
        "--auto-install-simulator-tools",
        action="store_true",
        help="Attempt to install missing qemu/spike/gem5 simulator toolchains before running enabled backends.",
    )
    ap.add_argument(
        "--simulator-toolchain-root",
        default=None,
        help="Local root used by the simulator toolchain manager for installed backend simulators.",
    )
    ap.add_argument("--auto-install-tools", dest="auto_install_simulator_tools", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--toolchain-root", dest="simulator_toolchain_root", default=None, help=argparse.SUPPRESS)
    ap.set_defaults(tt_strict_pairing=None, tt_strict_map_hit=None)
    args = ap.parse_args()

    bundle_root = find_bundle_root()
    if args.config:
        config_path = Path(args.config).expanduser().resolve()
        config_dir = config_path.parent
        cfg = load_json(config_path)
        config_source = str(config_path)
    else:
        if not args.workload or not args.target:
            raise SystemExit(
                "Pass either --config <file> or direct CLI arguments like "
                "--workload <tt_workload> --target tenstorrent --workload-size <size> --time-us <value>."
            )
        config_path = None
        config_dir = bundle_root
        cfg = build_cli_mode_config(args, bundle_root)
        config_source = "<cli-args>"

    cfg = apply_bundled_tt_inputs(cfg, bundle_root)

    comparison_label = str(cfg.get("comparison_label", "tt_riscv_compare")).strip() or "tt_riscv_compare"
    logical_workload = str(cfg.get("logical_workload", "")).strip()
    raw_targets = list(cfg.get("targets", []))
    targets = expand_auto_simulator_targets(cfg, raw_targets, config_dir)
    reference_label = determine_reference_label(targets, str(cfg.get("reference_label", "")).strip() or None)
    metrics = list(cfg.get("metrics", DEFAULT_METRICS)) or list(DEFAULT_METRICS)
    python_exec = str(cfg.get("python", sys.executable)).strip() or sys.executable
    shared_args = normalize_args(dict(cfg.get("shared_args", cfg.get("shared", {}))), config_dir)
    shared_expected_work_rate_locked = shared_args.get("expected_work_rate") is not None
    shared_sim_ops_per_zone_locked = shared_args.get("sim_ops_per_zone") is not None
    shared_env = dict(cfg.get("shared_env", {}))
    toolchain_cfg = dict(cfg.get("simulator_toolchain", cfg.get("toolchain", {})))
    toolchain_root_raw = str(toolchain_cfg.get("root_dir", args.simulator_toolchain_root or (bundle_root / ".toolchains"))).strip()
    toolchain_root = Path(toolchain_root_raw)
    if not toolchain_root.is_absolute():
        toolchain_root = (config_dir / toolchain_root).resolve()
    toolchain_settings = ToolchainSettings(
        root_dir=toolchain_root,
        auto_install=bool(toolchain_cfg.get("auto_install", args.auto_install_simulator_tools)),
        dry_run=bool(args.dry_run),
        show_commands=bool(args.show_commands),
        gem5_ref=str(toolchain_cfg.get("gem5_ref", "")),
        spike_ref=str(toolchain_cfg.get("spike_ref", "")),
        pk_ref=str(toolchain_cfg.get("pk_ref", "")),
    )
    auto_expected_work_rate_from_tt: float | None = None
    auto_sim_ops_per_zone_from_tt: int | None = None

    if not targets:
        raise SystemExit("Config must include at least one target in 'targets'.")

    out_dir = resolve_output_dir(bundle_root, config_dir, cfg)
    logs_dir = out_dir / "logs"
    summaries_dir = out_dir / "summaries"
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.snapshot.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    report_rows: list[dict[str, Any]] = []
    results_json: list[dict[str, Any]] = []
    failures = 0

    enabled_targets = [t for t in targets if bool(t.get("enabled", True))]
    total = len(enabled_targets)
    tt_reference_present = has_enabled_tt_reference_target(enabled_targets)

    for idx, target in enumerate(enabled_targets, start=1):
        target_name = str(target.get("name", "")).strip()
        handler = get_backend_handler(target_name)
        label = str(target.get("label", "")).strip() or target_name
        apply_tt_reference_calibration = should_apply_tt_reference_calibration(
            target,
            handler,
            tt_reference_present,
        )
        target_args = normalize_args(dict(target.get("args", {})), config_dir)
        merged_args: dict[str, Any] = {}
        merged_args.update(shared_args)
        merged_args.update(target_args)
        toolchain_result = prepare_backend_toolchain(target_name, merged_args, toolchain_settings)
        merged_args = dict(toolchain_result.resolved_args)
        gem5_stats_mode = (
            target_name == "gem5"
            and str(merged_args.get("gem5_adapter_mode", "exec")).strip() == "stats"
        )
        if (
            apply_tt_reference_calibration
            and not gem5_stats_mode
            and not shared_expected_work_rate_locked
            and auto_expected_work_rate_from_tt is not None
            and merged_args.get("expected_work_rate") is None
        ):
            merged_args["expected_work_rate"] = auto_expected_work_rate_from_tt
        if (
            apply_tt_reference_calibration
            and not gem5_stats_mode
            and not shared_sim_ops_per_zone_locked
            and auto_sim_ops_per_zone_from_tt is not None
            and merged_args.get("sim_ops_per_zone") is None
        ):
            merged_args["sim_ops_per_zone"] = auto_sim_ops_per_zone_from_tt
        if gem5_stats_mode:
            merged_args["expected_work_rate"] = None
            merged_args["sim_ops_per_zone"] = None
            if merged_args.get("no_work_sit_mode") is None:
                merged_args["no_work_sit_mode"] = "window_active"
        target_env = dict(target.get("env", {}))
        env = build_env(shared_env, target_env)
        row: dict[str, Any] = {
            "comparison_label": comparison_label,
            "logical_workload": logical_workload,
            "reference_label": reference_label,
            "case_id": idx,
            "label": label,
            "target": target_name,
            "target_category": handler.category,
            "workload": str(merged_args.get("workload", "")).strip(),
            "workload_size": str(merged_args.get("workload_size", "")).strip(),
            "status": "pending",
            "tt_reference_calibration_applied": apply_tt_reference_calibration,
        }
        if "auto_generated_from_tt" in target:
            row["auto_generated_from_tt"] = str(target.get("auto_generated_from_tt", ""))
        if toolchain_result.install_actions:
            row["toolchain_install_actions"] = " | ".join(toolchain_result.install_actions)
        row["simulator_toolchain_root"] = str(toolchain_settings.root_dir)

        if toolchain_result.errors:
            simulator_soft_skip = handler.category == "simulator" and (args.skip_missing_tools or args.check_only)
            row["status"] = "skipped" if simulator_soft_skip else "failed"
            row["error"] = ", ".join(toolchain_result.errors)
            report_rows.append(row)
            results_json.append({"row": row, "summary": None})
            if row["status"] == "failed":
                failures += 1
            continue

        static_errors = static_prereq_errors(target_name, merged_args)
        if static_errors:
            simulator_soft_skip = handler.category == "simulator" and (args.skip_missing_tools or args.check_only)
            row["status"] = "skipped" if simulator_soft_skip else "failed"
            row["error"] = ", ".join(static_errors)
            report_rows.append(row)
            results_json.append({"row": row, "summary": None})
            if row["status"] == "failed":
                failures += 1
            continue

        pre_run_cmd = str(target.get("pre_run_cmd", "")).strip()
        pre_run_cwd = maybe_resolve_path(target.get("pre_run_cwd", str(config_dir)), config_dir)
        pre_run_cwd_path = Path(str(pre_run_cwd)).expanduser().resolve()

        if args.check_only:
            if handler.category != "device" or not pre_run_cmd:
                runtime_errors = runtime_input_errors(target_name, merged_args)
                if runtime_errors:
                    row["status"] = "failed"
                    row["error"] = ", ".join(runtime_errors)
                    failures += 1
                else:
                    row["status"] = "ready"
            else:
                row["status"] = "ready_after_pre_run"
            report_rows.append(row)
            results_json.append({"row": row, "summary": None})
            continue

        print(f"[{idx}/{total}] target={label} backend={target_name}")

        if pre_run_cmd:
            pre_log = logs_dir / f"{sanitize_label(label)}__pre_run.log"
            rc = run_shell_command(pre_run_cmd, pre_run_cwd_path, env, pre_log, args.dry_run, args.show_commands)
            if rc != 0:
                row["status"] = "failed"
                row["error"] = f"pre_run_cmd failed rc={rc}"
                row["pre_run_log"] = str(pre_log)
                report_rows.append(row)
                results_json.append({"row": row, "summary": None})
                failures += 1
                continue
            row["pre_run_log"] = str(pre_log)

        runtime_errors = [] if args.dry_run else runtime_input_errors(target_name, merged_args)
        if runtime_errors:
            row["status"] = "failed"
            row["error"] = ", ".join(runtime_errors)
            report_rows.append(row)
            results_json.append({"row": row, "summary": None})
            failures += 1
            continue

        run_log = logs_dir / f"{sanitize_label(label)}.log"
        cmd = build_riscvbench_command(bundle_root, python_exec, target_name, merged_args)
        row["command"] = " ".join(cmd)
        row["log_path"] = str(run_log)
        started_at = time.time()
        rc = run_logged_command(cmd, bundle_root, env, run_log, args.dry_run, args.show_commands)
        if rc != 0:
            row["status"] = "failed"
            row["error"] = f"riscvbench failed rc={rc}"
            report_rows.append(row)
            results_json.append({"row": row, "summary": None})
            failures += 1
            continue

        if args.dry_run:
            row["status"] = "dry_run"
            report_rows.append(row)
            results_json.append({"row": row, "summary": None})
            continue

        summary_path = locate_latest_summary(bundle_root, target_name, str(merged_args.get("workload", "")).strip(), started_at)
        if summary_path is None:
            row["status"] = "failed"
            row["error"] = "could not locate summary.json or run_summary.json after successful run"
            report_rows.append(row)
            results_json.append({"row": row, "summary": None})
            failures += 1
            continue

        summary_copy = summaries_dir / f"{sanitize_label(label)}.json"
        shutil.copyfile(summary_path, summary_copy)
        summary = load_json(summary_copy)

        row["status"] = "ok"
        row["run_dir"] = str(summary_path.parent)
        row["summary_path"] = str(summary_copy)
        row["adapter_name"] = str(summary.get("adapter_meta", {}).get("adapter_name", ""))
        row["tool_version"] = str(summary.get("adapter_meta", {}).get("tool_version", ""))
        if handler.category == "device":
            row["tt_profile_csv"] = str(merged_args.get("tt_profile_csv", ""))
            row["tt_zone_log"] = str(merged_args.get("tt_zone_log", ""))
        for metric in metrics:
            row[metric] = summary.get(metric)

        if target_name == "tt_wormhole" and not shared_expected_work_rate_locked:
            derived_expected_work_rate = summary.get("expected_work_rate")
            try:
                derived_expected_work_rate = float(derived_expected_work_rate)
            except (TypeError, ValueError):
                derived_expected_work_rate = None
            if derived_expected_work_rate is not None and derived_expected_work_rate > 0.0:
                auto_expected_work_rate_from_tt = derived_expected_work_rate
        if target_name == "tt_wormhole" and not shared_sim_ops_per_zone_locked:
            observed_work_total = summary.get("observed_work_total")
            active_boost = resolve_size_active_boost(str(merged_args.get("workload_size", "")))
            try:
                observed_work_total = float(observed_work_total)
            except (TypeError, ValueError):
                observed_work_total = None
            if observed_work_total is not None and observed_work_total > 0.0 and active_boost:
                auto_sim_ops_per_zone_from_tt = int(round(observed_work_total / float(active_boost)))

        report_rows.append(row)
        results_json.append({"row": row, "summary": summary})

    add_reference_deltas(report_rows, metrics, reference_label)

    rows_csv = out_dir / "comparison_rows.csv"
    wide_csv = out_dir / "comparison_wide.csv"
    report_json = out_dir / "comparison.json"
    write_rows_csv(rows_csv, report_rows)
    write_rows_csv(wide_csv, [build_wide_row(comparison_label, logical_workload, reference_label, metrics, report_rows)])
    report_json.write_text(
        json.dumps(
            {
                "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "bundle_root": str(bundle_root),
                "config_path": config_source,
                "comparison_label": comparison_label,
                "logical_workload": logical_workload,
                "reference_label": reference_label,
                "results": results_json,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nOutputs written to {out_dir}")
    print(f"- rows: {rows_csv}")
    print(f"- wide: {wide_csv}")
    print(f"- json: {report_json}")
    print_results_summary(report_rows, reference_label)

    if failures:
        print(f"- completed with {failures} failure(s)")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
