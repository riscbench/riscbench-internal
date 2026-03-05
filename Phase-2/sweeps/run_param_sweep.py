#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List


FLAG_MAP = {
    "target": "--target",
    "workload": "--workload",
    "workload_size": "--workload_size",
    "time_us": "--time_us",
    "expected_work_rate": "--expected-work-rate",
    "pk": "--pk",
    "isa": "--isa",
    "inst_us": "--inst_us",
    "resident_pc_ge": "--resident_pc_ge",
    "gem5_bin": "--gem5-bin",
    "gem5_root": "--gem5-root",
    "gem5_config": "--gem5-config",
    "gem5_extra_args": "--gem5-extra-args",
    "gem5_cc": "--gem5-cc",
    "gem5_cpu_type": "--gem5-cpu-type",
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
}

BOOL_FLAG_MAP = {
    "branch_mispredict": "--branch-mispredict",
    "cache_pressure": "--cache-pressure",
    "debug_sit": "--debug-sit",
    "skip_post_processing": "--skip-post-processing",
    "practical": "--practical",
    "allow_nonzero_exit": "--allow-nonzero-exit",
}


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_cases(matrix: Dict[str, List[Any]]) -> Iterable[Dict[str, Any]]:
    keys = list(matrix.keys())
    values = [matrix[k] for k in keys]
    for combo in itertools.product(*values):
        yield dict(zip(keys, combo))


def to_cmd(repo: Path, python_exec: str, case: Dict[str, Any], shared: Dict[str, Any]) -> List[str]:
    cmd = [python_exec, str(repo / "riscvbench.py")]

    merged: Dict[str, Any] = {}
    merged.update(shared)
    merged.update(case)

    for key, value in merged.items():
        if key in BOOL_FLAG_MAP:
            if bool(value):
                cmd.append(BOOL_FLAG_MAP[key])
            continue

        flag = FLAG_MAP.get(key)
        if flag is None:
            continue
        cmd.extend([flag, str(value)])

    return cmd


def run_case(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def resolve_trace_csv(repo: Path, merged_case: Dict[str, Any]) -> Path | None:
    target = str(merged_case.get("target", "")).strip()
    workload = str(merged_case.get("workload", "")).strip()
    workload_size = str(merged_case.get("workload_size", "")).strip()
    if not target or not workload or not workload_size:
        return None
    trace_csv = repo / "runs" / target / workload / workload_size / "trace.csv"
    if not trace_csv.exists():
        return None
    return trace_csv


def resolve_run_summary_json(repo: Path, merged_case: Dict[str, Any]) -> Path | None:
    target = str(merged_case.get("target", "")).strip()
    workload = str(merged_case.get("workload", "")).strip()
    workload_size = str(merged_case.get("workload_size", "")).strip()
    if not target or not workload or not workload_size:
        return None
    run_dir = repo / "runs" / target / workload / workload_size
    for name in ("run_summary.json", "summary.json"):
        p = run_dir / name
        if p.exists():
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Phase-2 parameter sweeps on riscvbench")
    ap.add_argument("--config", required=True, help="Path to sweep JSON config")
    ap.add_argument("--max-cases", type=int, default=None, help="Optional cap for quick smoke sweeps")
    ap.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    cfg = load_config(Path(args.config))

    python_exec = str(cfg.get("python", sys.executable))
    shared = dict(cfg.get("shared", {}))
    matrix = dict(cfg.get("matrix", {}))
    capture_case_traces = bool(cfg.get("capture_case_traces", False))
    fail_if_missing_trace = bool(cfg.get("fail_if_missing_trace", False))
    emit_manifest = bool(cfg.get("emit_manifest", False))
    residency_masks_root = str(cfg.get("residency_masks_root", "datasets/residency"))
    dataset_version_cfg = str(cfg.get("dataset_version", "")).strip()

    if not matrix:
        print("No matrix in config")
        return 2

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = repo / "sweeps" / "results" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    trace_index_rows: List[Dict[str, Any]] = []
    copied_trace_paths: List[Path] = []
    failures = 0

    cases = list(build_cases(matrix))
    max_cases_cfg = cfg.get("max_cases")
    max_cases = args.max_cases if args.max_cases is not None else max_cases_cfg
    if max_cases is not None:
        cases = cases[: int(max_cases)]

    for idx, case in enumerate(cases, start=1):
        merged_case: Dict[str, Any] = {}
        merged_case.update(shared)
        merged_case.update(case)
        cmd = to_cmd(repo, python_exec, case, shared)
        print(f"[{idx}/{len(cases)}] $ {' '.join(cmd)}")

        start = time.perf_counter()
        result = run_case(cmd, cwd=repo)
        elapsed_s = time.perf_counter() - start

        row = {
            "case_id": idx,
            "returncode": result.returncode,
            "elapsed_s": f"{elapsed_s:.3f}",
            **case,
        }

        if capture_case_traces and result.returncode == 0:
            src_trace = resolve_trace_csv(repo, merged_case)
            trace_id = f"trace_{idx:04d}"
            if src_trace is None:
                row["trace_copy_ok"] = 0
                row["trace_copy_msg"] = "missing runs/<target>/<workload>/<size>/trace.csv"
                if fail_if_missing_trace:
                    failures += 1
            else:
                traces_dir = out_dir / "traces"
                traces_dir.mkdir(parents=True, exist_ok=True)
                dst_trace = traces_dir / f"{trace_id}.csv"
                shutil.copyfile(src_trace, dst_trace)
                copied_trace_paths.append(dst_trace)
                row["trace_copy_ok"] = 1
                row["trace_path"] = str(dst_trace.resolve())
                trace_index_rows.append(
                    {
                        "trace_id": trace_id,
                        "trace_path": str(dst_trace.resolve()),
                        "target": str(merged_case.get("target", "")),
                        "workload": str(merged_case.get("workload", "")),
                        "workload_size": str(merged_case.get("workload_size", "")),
                        "time_us": str(merged_case.get("time_us", "")),
                        "flag_mode": (
                            "both"
                            if bool(merged_case.get("branch_mispredict", False))
                            and bool(merged_case.get("cache_pressure", False))
                            else (
                                "branch_mispredict"
                                if bool(merged_case.get("branch_mispredict", False))
                                else (
                                    "cache_pressure"
                                    if bool(merged_case.get("cache_pressure", False))
                                    else "none"
                                )
                            )
                        ),
                        "branch_mispredict": str(bool(merged_case.get("branch_mispredict", False))),
                        "cache_pressure": str(bool(merged_case.get("cache_pressure", False))),
                    }
                )

            src_summary = resolve_run_summary_json(repo, merged_case)
            if src_summary is None:
                row["summary_copy_ok"] = 0
                row["summary_copy_msg"] = "missing runs/<target>/<workload>/<size>/run_summary.json"
            else:
                summaries_dir = out_dir / "summaries"
                summaries_dir.mkdir(parents=True, exist_ok=True)
                dst_summary = summaries_dir / f"summary_{idx:04d}.json"
                shutil.copyfile(src_summary, dst_summary)
                row["summary_copy_ok"] = 1
                row["summary_path"] = str(dst_summary.resolve())
        rows.append(row)

        case_log = out_dir / f"case_{idx:04d}.log"
        case_log.write_text(
            "CMD: " + " ".join(cmd) + "\n\nSTDOUT:\n" + (result.stdout or "") + "\n\nSTDERR:\n" + (result.stderr or ""),
            encoding="utf-8",
        )

        if result.returncode != 0:
            failures += 1
            if args.fail_fast:
                break

    if rows:
        fieldnames = sorted({k for r in rows for k in r.keys()})
        with (out_dir / "sweep_results.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    if trace_index_rows:
        trace_fields = sorted({k for r in trace_index_rows for k in r.keys()})
        with (out_dir / "trace_index.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=trace_fields)
            writer.writeheader()
            writer.writerows(trace_index_rows)

    if emit_manifest and copied_trace_paths:
        masks_dir = (repo / residency_masks_root).resolve()
        default_window = cfg.get("window_us_default", shared.get("time_us", 256.0))
        try:
            window_us_default = float(default_window)
        except (TypeError, ValueError):
            window_us_default = 256.0
        dataset_version = (
            dataset_version_cfg
            if dataset_version_cfg
            else f"sweep-{timestamp}-{len(copied_trace_paths)}traces"
        )
        manifest = {
            "dataset_version": dataset_version,
            "window_us_default": window_us_default,
            "traces": [str(p.resolve()) for p in copied_trace_paths],
            "residency_masks": {
                "all": str((masks_dir / "all.csv").resolve()),
                "skip_w0": str((masks_dir / "skip_w0.csv").resolve()),
                "partial": str((masks_dir / "partial.csv").resolve()),
                "exact_boundary": str((masks_dir / "exact_boundary.csv").resolve()),
            },
        }
        (out_dir / "sweep_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    summary = {
        "total_cases": len(rows),
        "failures": failures,
        "passes": len(rows) - failures,
        "results_dir": str(out_dir),
        "trace_count": len(copied_trace_paths),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
