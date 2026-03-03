#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

PRACTICAL_WORKLOADS = ["branch", "memory", "memread", "memwrite", "memcpy", "matmul"]


def run_cmd(cmd: list[str], dry_run: bool = False) -> None:
    print("$", " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True)


def count_events(trace_csv: Path) -> int:
    if not trace_csv.exists():
        raise FileNotFoundError(f"missing trace file: {trace_csv}")
    with trace_csv.open("r", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        return sum(1 for _ in reader)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Run the same practical workloads on spike+cpu with the same events cap, "
            "and verify matched event counts."
        )
    )
    ap.add_argument("--workloads", nargs="+", default=PRACTICAL_WORKLOADS, help="Workloads to run on both targets")
    ap.add_argument("--workload-size", default="small", choices=["tiny", "small", "med", "large"])
    ap.add_argument("--time-us", type=float, default=256.0)
    ap.add_argument("--events-max", type=int, default=2000)
    ap.add_argument("--pk", required=True, help="Path to riscv-pk for spike")
    ap.add_argument("--cores", type=int, default=4, help="CPU cores for matmul_multicore (if selected)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent
    failures: list[str] = []

    for workload in args.workloads:
        if workload == "matmul_multicore":
            failures.append("matmul_multicore is excluded from strict parity because spike falls back to single-core matmul")
            continue

        per_target_counts = {}
        for target in ("spike", "cpu"):
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
                "--events-max",
                str(args.events_max),
                "--expected-work-rate",
                "1.15",
            ]
            if target == "spike":
                cmd += ["--pk", args.pk]
            else:
                # Introduce practical queue pressure so SIT is usually < 1 for compute-heavy workloads.
                cmd += ["--overflow", "--underflow", "--reader-sleep-ns", "2000", "--writer-sleep-ns", "5000"]
                if workload == "matmul_multicore":
                    cmd += ["--cores", str(args.cores)]

            run_cmd(cmd, dry_run=args.dry_run)
            if args.dry_run:
                continue

            trace_csv = repo / "runs" / target / workload / args.workload_size / "trace.csv"
            per_target_counts[target] = count_events(trace_csv)

        if args.dry_run:
            continue

        spike_count = per_target_counts.get("spike")
        cpu_count = per_target_counts.get("cpu")
        if spike_count != args.events_max:
            failures.append(f"{workload}: spike parsed {spike_count}, expected {args.events_max}")
        if cpu_count != args.events_max:
            failures.append(f"{workload}: cpu parsed {cpu_count}, expected {args.events_max}")
        if spike_count != cpu_count:
            failures.append(f"{workload}: mismatch spike={spike_count} cpu={cpu_count}")

        print(f"✓ {workload}: spike={spike_count} cpu={cpu_count}")

    if failures:
        print("\nParity suite failures:")
        for item in failures:
            print(" -", item)
        return 1

    print("\n✓ Cross-target parity suite passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
