#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

VALID_TARGETS = ("spike", "qemu", "gem5")


def has_tool(tool_or_path: str) -> bool:
    if shutil.which(tool_or_path):
        return True
    return Path(tool_or_path).expanduser().exists()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: List[str], cwd: Path) -> int:
    print("$", " ".join(cmd))
    return int(subprocess.run(cmd, cwd=cwd).returncode)


def collect_hashes(outdir: Path) -> Dict[str, str]:
    files = sorted(list(outdir.glob("*_windows.csv")) + list(outdir.glob("*_summary.json")))
    out: Dict[str, str] = {}
    for p in files:
        out[p.name] = sha256_file(p)
    return out


def build_manifest(repo: Path, trace_csv: Path, manifest_path: Path, window_us: float) -> None:
    masks_dir = repo / "datasets" / "residency"
    obj = {
        "dataset_version": "determinism-v1",
        "window_us_default": float(window_us),
        "traces": [str(trace_csv.resolve())],
        "residency_masks": {
            "all": str((masks_dir / "all.csv").resolve()),
            "skip_w0": str((masks_dir / "skip_w0.csv").resolve()),
            "partial": str((masks_dir / "partial.csv").resolve()),
            "exact_boundary": str((masks_dir / "exact_boundary.csv").resolve()),
        },
    }
    manifest_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def check_target_prereqs(target: str, args: argparse.Namespace) -> List[str]:
    missing: List[str] = []
    if target == "spike":
        if not has_tool("spike"):
            missing.append("spike")
        if not has_tool("riscv64-unknown-elf-gcc"):
            missing.append("riscv64-unknown-elf-gcc")
        if not args.pk:
            missing.append("--pk (required for spike)")
        elif not Path(args.pk).expanduser().exists():
            missing.append(f"pk path not found: {args.pk}")
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
    return missing


def main() -> int:
    ap = argparse.ArgumentParser(description="Determinism check: golden replay outputs must be byte-identical.")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--targets", nargs="+", default=["spike", "qemu"], choices=VALID_TARGETS)
    ap.add_argument("--workload", default="hello")
    ap.add_argument("--workload-size", default="test", choices=["test", "tiny", "small", "med", "large"])
    ap.add_argument("--time-us", type=float, default=256.0)
    ap.add_argument("--window-us", type=float, default=256.0)
    ap.add_argument("--expected-work-rate", type=float, default=1.0)
    ap.add_argument("--pk", default=None)
    ap.add_argument("--qemu-bin", default=os.environ.get("QEMU_BIN", "qemu-riscv64"))
    ap.add_argument("--qemu-cc", default=os.environ.get("QEMU_CC", "riscv64-linux-gnu-gcc"))
    ap.add_argument("--allow-nonzero-exit", action="store_true", help="Pass through to qemu riscvbench runs")
    ap.add_argument("--gem5-bin", default=os.environ.get("GEM5_BIN", "gem5.opt"))
    ap.add_argument("--gem5-cc", default=os.environ.get("GEM5_CC", "riscv64-linux-gnu-gcc"))
    ap.add_argument("--gem5-root", default=os.environ.get("GEM5_ROOT", ""))
    ap.add_argument("--gem5-config", default=None)
    ap.add_argument("--skip-missing-tools", action="store_true")
    ap.add_argument(
        "--no-work-sit-mode",
        choices=["global_active", "window_active"],
        default="window_active",
        help="Pass-through to run_golden_suite for no-work traces",
    )
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    failures: List[str] = []

    targets = list(dict.fromkeys(args.targets))
    for target in targets:
        missing = check_target_prereqs(target, args)
        if missing:
            msg = f"{target}: missing prerequisites -> {', '.join(missing)}"
            if args.skip_missing_tools:
                print(f"SKIP {msg}")
                continue
            failures.append(msg)
            continue

        cmd = [
            args.python,
            str(repo / "riscvbench.py"),
            "--target",
            target,
            "--workload",
            args.workload,
            "--workload_size",
            args.workload_size,
            "--time_us",
            str(args.time_us),
            "--expected-work-rate",
            str(args.expected_work_rate),
        ]
        if target == "spike":
            cmd += ["--pk", str(args.pk)]
        elif target == "qemu":
            cmd += ["--qemu-bin", str(args.qemu_bin), "--qemu-cc", str(args.qemu_cc)]
            if args.allow_nonzero_exit:
                cmd += ["--allow-nonzero-exit"]
        elif target == "gem5":
            cmd += ["--gem5-bin", str(args.gem5_bin), "--gem5-cc", str(args.gem5_cc)]
            if args.gem5_root.strip():
                cmd += ["--gem5-root", args.gem5_root.strip()]
            if args.gem5_config:
                cmd += ["--gem5-config", str(args.gem5_config)]

        rc = run(cmd, cwd=repo)
        if rc != 0:
            failures.append(f"{target}: riscvbench failed rc={rc}")
            continue

        trace_csv = repo / "runs" / target / args.workload / args.workload_size / "trace.csv"
        if not trace_csv.exists():
            failures.append(f"{target}: missing normalized trace {trace_csv}")
            continue

        with tempfile.TemporaryDirectory(prefix=f"det_{target}_") as td:
            td_path = Path(td)
            manifest = td_path / "manifest.json"
            build_manifest(repo, trace_csv, manifest, window_us=float(args.window_us))

            out_a = td_path / "golden_a"
            out_b = td_path / "golden_b"

            cmd_golden_a = [
                args.python,
                str(repo / "tests" / "run_golden_suite.py"),
                "--manifest",
                str(manifest),
                "--outdir",
                str(out_a),
                "--window-us",
                str(args.window_us),
                "--no-work-sit-mode",
                str(args.no_work_sit_mode),
            ]
            cmd_golden_b = [
                args.python,
                str(repo / "tests" / "run_golden_suite.py"),
                "--manifest",
                str(manifest),
                "--outdir",
                str(out_b),
                "--window-us",
                str(args.window_us),
                "--no-work-sit-mode",
                str(args.no_work_sit_mode),
            ]

            rc_a = run(cmd_golden_a, cwd=repo)
            rc_b = run(cmd_golden_b, cwd=repo)
            if rc_a != 0 or rc_b != 0:
                failures.append(f"{target}: golden reruns failed rc_a={rc_a} rc_b={rc_b}")
                continue

            hashes_a = collect_hashes(out_a)
            hashes_b = collect_hashes(out_b)
            if not hashes_a:
                failures.append(f"{target}: no golden output hashes collected from {out_a}")
                continue
            if set(hashes_a.keys()) != set(hashes_b.keys()):
                missing_keys = sorted(set(hashes_a.keys()) ^ set(hashes_b.keys()))
                failures.append(f"{target}: output file set mismatch: {missing_keys}")
                continue

            mismatches = [
                name
                for name in sorted(hashes_a.keys())
                if hashes_a[name] != hashes_b[name]
            ]
            if mismatches:
                failures.append(f"{target}: non-deterministic artifacts: {', '.join(mismatches)}")
                continue

            print(f"PASS deterministic: {target} ({len(hashes_a)} artifacts)")

    if failures:
        print("\nDeterminism failures:")
        for f in failures:
            print(" -", f)
        return 2

    print("\nPASS determinism checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
