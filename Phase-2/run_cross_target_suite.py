#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

PRACTICAL_WORKLOADS = ["fm_loopback", "fm_mm", "fm_read", "fm_write", "matmul"]
VALID_TARGETS = ("spike", "cpu", "qemu", "gem5")


def run_cmd(cmd: list[str], dry_run: bool = False) -> int:
    print("$", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.run(cmd, check=False).returncode


def count_rows(csv_path: Path) -> int:
    if not csv_path.exists():
        return 0
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        return sum(1 for _ in reader)


def has_tool(tool_or_path: str) -> bool:
    if shutil.which(tool_or_path):
        return True
    return Path(tool_or_path).expanduser().exists()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run practical workloads across selected targets and check pipeline artifacts."
    )
    ap.add_argument("--workloads", nargs="+", default=PRACTICAL_WORKLOADS)
    ap.add_argument("--workload-size", default="small", choices=["test", "tiny", "small", "med", "large"])
    ap.add_argument("--time-us", type=float, default=256.0)
    ap.add_argument("--expected-work-rate", type=float, default=1.0)
    ap.add_argument("--targets", nargs="+", default=["spike", "cpu"], choices=VALID_TARGETS)
    ap.add_argument("--pk", default=None, help="Path to riscv-pk for spike")
    ap.add_argument("--qemu-bin", default=os.environ.get("QEMU_BIN", "qemu-riscv64"))
    ap.add_argument("--qemu-cc", default=os.environ.get("QEMU_CC", "riscv64-linux-gnu-gcc"))
    ap.add_argument("--qemu-extra-args", default="")
    ap.add_argument(
        "--allow-nonzero-exit",
        action="store_true",
        help="Pass --allow-nonzero-exit to qemu runs in riscvbench",
    )
    ap.add_argument("--gem5-bin", default=os.environ.get("GEM5_BIN", "gem5.opt"))
    ap.add_argument("--gem5-cc", default=os.environ.get("GEM5_CC", "riscv64-linux-gnu-gcc"))
    ap.add_argument("--gem5-root", default=os.environ.get("GEM5_ROOT", ""))
    ap.add_argument("--gem5-config", default=None)
    ap.add_argument("--gem5-extra-args", default="")
    ap.add_argument("--skip-missing-tools", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent
    failures: list[str] = []
    selected_targets = list(dict.fromkeys(args.targets))
    runnable_targets: list[str] = []

    for target in selected_targets:
        missing: list[str] = []
        if target == "spike":
            if not has_tool("spike"):
                missing.append("spike")
            if not has_tool("riscv64-unknown-elf-gcc"):
                missing.append("riscv64-unknown-elf-gcc")
            if not args.pk:
                missing.append("--pk (required for spike)")
            elif not Path(args.pk).expanduser().exists():
                missing.append(f"pk path not found: {args.pk}")
        elif target == "cpu":
            if not has_tool("gcc"):
                missing.append("gcc")
        elif target == "qemu":
            if not has_tool(args.qemu_bin):
                missing.append(f"qemu binary not found: {args.qemu_bin}")
            if not has_tool(args.qemu_cc):
                missing.append(f"qemu cc not found: {args.qemu_cc}")
        elif target == "gem5":
            if not has_tool(args.gem5_bin):
                missing.append(f"gem5 binary not found: {args.gem5_bin}")
            if not has_tool(args.gem5_cc):
                missing.append(f"gem5 cc not found: {args.gem5_cc}")

        if missing:
            msg = f"{target}: missing prerequisites -> {', '.join(missing)}"
            if args.skip_missing_tools:
                print(f"SKIP {msg}")
                continue
            failures.append(msg)
            continue

        runnable_targets.append(target)

    if not runnable_targets and not args.dry_run:
        if failures:
            print("\nCross-target suite failures:")
            for f in failures:
                print(" -", f)
            return 1
        print("No runnable targets selected.")
        return 1

    for workload in args.workloads:
        for target in runnable_targets:
            cmd = [
                sys.executable,
                str(repo / "riscvbench.py"),
                "--target",
                target,
                "--workload",
                workload,
                "--workload_size",
                args.workload_size,
                "--time_us",
                str(args.time_us),
                "--expected-work-rate",
                str(args.expected_work_rate),
            ]
            if target == "spike":
                cmd += ["--pk", args.pk]
            elif target == "qemu":
                cmd += ["--qemu-bin", args.qemu_bin, "--qemu-cc", args.qemu_cc]
                if args.allow_nonzero_exit:
                    cmd += ["--allow-nonzero-exit"]
                if args.qemu_extra_args.strip():
                    cmd += ["--qemu-extra-args", args.qemu_extra_args.strip()]
            elif target == "gem5":
                cmd += ["--gem5-bin", args.gem5_bin, "--gem5-cc", args.gem5_cc]
                if args.gem5_root.strip():
                    cmd += ["--gem5-root", args.gem5_root.strip()]
                if args.gem5_config:
                    cmd += ["--gem5-config", str(args.gem5_config)]
                if args.gem5_extra_args.strip():
                    cmd += ["--gem5-extra-args", args.gem5_extra_args.strip()]

            rc = run_cmd(cmd, dry_run=args.dry_run)
            if rc != 0:
                failures.append(f"{target}/{workload}: riscvbench failed rc={rc}")
                continue

            if args.dry_run:
                continue

            run_dir = repo / "runs" / target / workload / args.workload_size
            trace_csv = run_dir / "trace.csv"
            windows_csv = run_dir / "windows.csv"
            summary_json = run_dir / "summary.json"

            if not trace_csv.exists():
                failures.append(f"{target}/{workload}: missing {trace_csv}")
                continue
            if not windows_csv.exists():
                failures.append(f"{target}/{workload}: missing {windows_csv}")
                continue
            if not summary_json.exists():
                failures.append(f"{target}/{workload}: missing {summary_json}")
                continue

            n_trace = count_rows(trace_csv)
            n_windows = count_rows(windows_csv)
            if n_trace == 0:
                failures.append(f"{target}/{workload}: trace.csv has 0 rows")
            if n_windows == 0:
                failures.append(f"{target}/{workload}: windows.csv has 0 rows")

            print(f"✓ {target}/{workload}: trace_rows={n_trace} windows_rows={n_windows}")

    if failures:
        print("\nCross-target suite failures:")
        for f in failures:
            print(" -", f)
        return 1

    print("\n✓ Cross-target suite passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
