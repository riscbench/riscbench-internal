#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

PRACTICAL_WORKLOADS = ["branch", "memory", "memread", "memwrite", "memcpy", "matmul", "matmul_multicore"]


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


def within_tolerance(a: int, b: int, tol: int) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Run practical workloads on spike+cpu with a shared events cap, "
            "and verify event-count parity (exact or similar)."
        )
    )
    ap.add_argument("--workloads", nargs="+", default=PRACTICAL_WORKLOADS, help="Workloads to run on both targets")
    ap.add_argument("--workload-size", default="small", choices=["tiny", "small", "med", "large"])
    ap.add_argument("--time-us", type=float, default=256.0)
    ap.add_argument("--events-max", type=int, default=47_000, help="Shared parsing cap for both targets")
    ap.add_argument("--pk", required=True, help="Path to riscv-pk for spike")
    ap.add_argument("--cores", type=int, default=4, help="CPU cores for matmul_multicore")
    ap.add_argument(
        "--match-mode",
        choices=["exact", "similar"],
        default="similar",
        help="exact: require same counts and exact events-max; similar: allow tolerance",
    )
    ap.add_argument(
        "--similarity-pct",
        type=float,
        default=0.05,
        help="Allowed relative difference in similar mode (default: 5%%)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent
    failures: list[str] = []

    tolerance = max(10, int(args.events_max * args.similarity_pct))

    for workload in args.workloads:
        per_target_counts = {}
        if workload == "matmul_multicore":
            print(
                "! Note: Spike matmul_multicore uses a single-core matmul fallback for trace generation "
                "(not true pthread multicore execution)."
            )

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

        spike_count = per_target_counts.get("spike", 0)
        cpu_count = per_target_counts.get("cpu", 0)

        if args.match_mode == "exact":
            if spike_count != args.events_max:
                failures.append(f"{workload}: spike parsed {spike_count}, expected {args.events_max}")
            if cpu_count != args.events_max:
                failures.append(f"{workload}: cpu parsed {cpu_count}, expected {args.events_max}")
            if spike_count != cpu_count:
                failures.append(f"{workload}: mismatch spike={spike_count} cpu={cpu_count}")
        else:
            if not within_tolerance(spike_count, args.events_max, tolerance):
                failures.append(
                    f"{workload}: spike count {spike_count} not within ±{tolerance} of events-max {args.events_max}"
                )
            if not within_tolerance(cpu_count, args.events_max, tolerance):
                failures.append(
                    f"{workload}: cpu count {cpu_count} not within ±{tolerance} of events-max {args.events_max}"
                )
            if not within_tolerance(spike_count, cpu_count, tolerance):
                failures.append(
                    f"{workload}: spike/cpu mismatch {spike_count}/{cpu_count} exceeds ±{tolerance}"
                )

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
