#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def has_tool(tool_or_path: str) -> bool:
    if shutil.which(tool_or_path):
        return True
    return Path(tool_or_path).expanduser().exists()


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate qemu non-zero exit handling policy in riscvbench.")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--qemu-bin", default="qemu-riscv64")
    ap.add_argument("--qemu-cc", default="riscv64-linux-gnu-gcc")
    ap.add_argument("--workload", default="fm_mm")
    ap.add_argument("--workload-size", default="test", choices=["test", "tiny", "small", "med", "large"])
    ap.add_argument("--time-us", type=float, default=128.0)
    ap.add_argument("--expected-work-rate", type=float, default=1.0)
    ap.add_argument("--skip-missing-tools", action="store_true")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    missing: list[str] = []
    if not has_tool(args.qemu_bin):
        missing.append(f"qemu binary not found: {args.qemu_bin}")
    if not has_tool(args.qemu_cc):
        missing.append(f"qemu cc not found: {args.qemu_cc}")
    if missing:
        msg = "; ".join(missing)
        if args.skip_missing_tools:
            print(f"SKIP {msg}")
            return 0
        print(f"FAIL {msg}")
        return 2

    base_cmd = [
        args.python,
        str(repo / "riscvbench.py"),
        "--target",
        "qemu",
        "--workload",
        args.workload,
        "--workload_size",
        args.workload_size,
        "--time_us",
        str(args.time_us),
        "--expected-work-rate",
        str(args.expected_work_rate),
        "--qemu-bin",
        str(args.qemu_bin),
        "--qemu-cc",
        str(args.qemu_cc),
    ]

    p_fail = run(base_cmd, cwd=repo)
    if p_fail.returncode == 0:
        print("FAIL expected non-zero return without --allow-nonzero-exit")
        return 2
    if "qemu run failed (rc=" not in ((p_fail.stdout or "") + (p_fail.stderr or "")):
        print("FAIL missing fatal qemu non-zero message without --allow-nonzero-exit")
        return 2

    p_allow = run(base_cmd + ["--allow-nonzero-exit"], cwd=repo)
    if p_allow.returncode != 0:
        print("FAIL expected success with --allow-nonzero-exit")
        return 2

    print("PASS qemu exit policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
