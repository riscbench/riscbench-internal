#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import itertools
import json
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

    if not matrix:
        print("No matrix in config")
        return 2

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = repo / "sweeps" / "results" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    failures = 0

    cases = list(build_cases(matrix))
    max_cases_cfg = cfg.get("max_cases")
    max_cases = args.max_cases if args.max_cases is not None else max_cases_cfg
    if max_cases is not None:
        cases = cases[: int(max_cases)]

    for idx, case in enumerate(cases, start=1):
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

    summary = {
        "total_cases": len(rows),
        "failures": failures,
        "passes": len(rows) - failures,
        "results_dir": str(out_dir),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
