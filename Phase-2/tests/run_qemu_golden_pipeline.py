#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from run_spike_golden_pipeline import build_common_outputs, run_monotonic_matrix_checks

DEFAULT_QEMU_WORKLOADS = ["fm_loopback", "fm_mm", "fm_read", "fm_write", "matmul"]
ALL_SIZES = ["test", "tiny", "small", "med", "large"]
FLAG_MODES = ["none", "branch_mispredict", "cache_pressure", "both"]


def run(cmd: List[str], cwd: Path) -> int:
    print("$", " ".join(cmd))
    p = subprocess.run(cmd, cwd=cwd)
    return int(p.returncode)


def build_manifest(repo: Path, traces: List[Path], window_us: float, dataset_version: str) -> dict:
    masks_dir = repo / "datasets" / "residency"
    return {
        "dataset_version": dataset_version,
        "window_us_default": float(window_us),
        "traces": [str(p.resolve()) for p in traces],
        "residency_masks": {
            "all": str((masks_dir / "all.csv").resolve()),
            "skip_w0": str((masks_dir / "skip_w0.csv").resolve()),
            "partial": str((masks_dir / "partial.csv").resolve()),
            "exact_boundary": str((masks_dir / "exact_boundary.csv").resolve()),
        },
    }


def bool_to_int(v: bool) -> str:
    return "1" if v else "0"


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    fields = sorted({k for r in rows for k in r.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def parse_sizes(args: argparse.Namespace) -> List[str]:
    if args.all_sizes:
        return list(ALL_SIZES)
    if args.workload_sizes:
        return list(args.workload_sizes)
    return [args.workload_size]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Run QEMU workloads across size/flag matrix -> build QEMU manifest -> "
            "run golden suite -> visualize invariants -> emit common combined graph."
        )
    )
    ap.add_argument("--python", default=sys.executable, help="Python executable")
    ap.add_argument("--workloads", nargs="+", default=DEFAULT_QEMU_WORKLOADS)
    ap.add_argument("--workload-size", default="small", choices=ALL_SIZES)
    ap.add_argument("--workload-sizes", nargs="+", choices=ALL_SIZES, help="Optional list of sizes (overrides --workload-size)")
    ap.add_argument("--all-sizes", action="store_true", help="Run all sizes: test,tiny,small,med,large")
    ap.add_argument("--emulated-flags", nargs="+", choices=FLAG_MODES, default=["none"])
    ap.add_argument("--time-us", type=float, default=256.0, help="time_us passed to riscvbench")
    ap.add_argument("--window-us", type=float, default=None, help="window_us for golden suite (default: --time-us)")
    ap.add_argument("--expected-work-rate", type=float, default=1.0)
    ap.add_argument("--inst-us", type=float, default=1.0)
    ap.add_argument("--resident-pc-ge", default="0x80000000")
    ap.add_argument("--qemu-bin", default="qemu-riscv64")
    ap.add_argument("--qemu-cc", default="riscv64-linux-gnu-gcc")
    ap.add_argument("--qemu-extra-args", default="")
    ap.add_argument("--allow-nonzero-exit", action="store_true", help="Pass through to riscvbench qemu runner")
    ap.add_argument("--outdir", default="golden_out_qemu", help="Output directory for golden suite artifacts")
    ap.add_argument(
        "--manifest-out",
        default=None,
        help="Path to write generated QEMU manifest JSON (default: <outdir>/qemu_manifest.json)",
    )
    ap.add_argument("--skip-visualize", action="store_true", help="Skip visualization step")
    ap.add_argument("--skip-common-visualize", action="store_true", help="Skip common combined graph output")
    ap.add_argument("--skip-monotonic-check", action="store_true", help="Skip monotonic flag behavior checks")
    ap.add_argument("--monotonic-min-sit-drop", type=float, default=0.02, help="Minimum sit_median drop vs baseline")
    ap.add_argument("--monotonic-min-stall-rise", type=float, default=0.02, help="Minimum residency_stall_avg rise vs baseline")
    ap.add_argument("--monotonic-max-idle-rise", type=float, default=0.20, help="Maximum residency_idle_avg rise vs baseline")
    ap.add_argument("--common-mode", default="base", choices=["base", "all", "skip_w0", "partial", "exact_boundary"])
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    window_us = float(args.window_us) if args.window_us is not None else float(args.time_us)
    sizes = parse_sizes(args)
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    traces_out = outdir / "traces"
    traces_out.mkdir(parents=True, exist_ok=True)
    manifest_out = Path(args.manifest_out).resolve() if args.manifest_out else (outdir / "qemu_manifest.json")

    traces: List[Path] = []
    trace_index_rows: List[Dict[str, str]] = []
    failures: List[str] = []

    case_id = 0
    total_cases = len(args.workloads) * len(sizes) * len(args.emulated_flags)
    print(f"Running QEMU cases sequentially: total={total_cases}")
    for wl in args.workloads:
        for sz in sizes:
            for flag_mode in args.emulated_flags:
                branch_mispredict = flag_mode in {"branch_mispredict", "both"}
                cache_pressure = flag_mode in {"cache_pressure", "both"}
                case_id += 1
                trace_id = f"trace_{case_id:04d}"
                print(
                    f">>> case {case_id}/{total_cases}: "
                    f"workload={wl} size={sz} flag={flag_mode}"
                )

                cmd = [
                    args.python,
                    str(repo / "riscvbench.py"),
                    "--target",
                    "qemu",
                    "--workload",
                    wl,
                    "--workload_size",
                    sz,
                    "--time_us",
                    str(args.time_us),
                    "--expected-work-rate",
                    str(args.expected_work_rate),
                    "--inst_us",
                    str(args.inst_us),
                    "--resident_pc_ge",
                    str(args.resident_pc_ge),
                    "--qemu-bin",
                    str(args.qemu_bin),
                    "--qemu-cc",
                    str(args.qemu_cc),
                ]
                if args.qemu_extra_args.strip():
                    cmd += ["--qemu-extra-args", args.qemu_extra_args.strip()]
                if args.allow_nonzero_exit:
                    cmd.append("--allow-nonzero-exit")
                if branch_mispredict:
                    cmd.append("--branch-mispredict")
                if cache_pressure:
                    cmd.append("--cache-pressure")

                rc = run(cmd, cwd=repo)
                if rc != 0:
                    failures.append(f"qemu run failed workload={wl} size={sz} flags={flag_mode} rc={rc}")
                    continue

                trace_csv = repo / "runs" / "qemu" / wl / sz / "trace.csv"
                if not trace_csv.exists():
                    failures.append(f"missing trace.csv workload={wl} size={sz} flags={flag_mode}: {trace_csv}")
                    continue

                dst = traces_out / f"{trace_id}.csv"
                shutil.copyfile(trace_csv, dst)
                traces.append(dst)
                trace_index_rows.append(
                    {
                        "trace_id": trace_id,
                        "trace_path": str(dst.resolve()),
                        "workload": wl,
                        "workload_size": sz,
                        "flag_mode": flag_mode,
                        "branch_mispredict": bool_to_int(branch_mispredict),
                        "cache_pressure": bool_to_int(cache_pressure),
                    }
                )

    if failures:
        print("\nFAILURES during QEMU generation:")
        for f in failures:
            print(" -", f)
        return 2
    if not traces:
        print("No QEMU traces generated; aborting.")
        return 2

    trace_index_csv = outdir / "trace_index.csv"
    write_csv(trace_index_csv, trace_index_rows)
    print(f"✓ wrote trace index: {trace_index_csv}")

    manifest = build_manifest(
        repo,
        traces,
        window_us=window_us,
        dataset_version=f"qemu-golden-v1-{len(traces)}traces",
    )
    manifest_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"✓ wrote manifest: {manifest_out}")

    cmd_golden = [
        args.python,
        str(repo / "tests" / "run_golden_suite.py"),
        "--manifest",
        str(manifest_out),
        "--outdir",
        str(outdir),
        "--window-us",
        str(window_us),
    ]
    rc = run(cmd_golden, cwd=repo)
    if rc != 0:
        return rc

    if not args.skip_monotonic_check:
        rc = run_monotonic_matrix_checks(
            repo=repo,
            outdir=outdir,
            trace_index_rows=trace_index_rows,
            python_exec=args.python,
            min_sit_drop=float(args.monotonic_min_sit_drop),
            min_stall_rise=float(args.monotonic_min_stall_rise),
            max_idle_rise=float(args.monotonic_max_idle_rise),
        )
        if rc != 0:
            return rc

    if not args.skip_visualize:
        cmd_vis = [
            args.python,
            str(repo / "tests" / "visualize_golden_invariants.py"),
            "--golden-out",
            str(outdir),
            "--window-us",
            str(window_us),
        ]
        rc = run(cmd_vis, cwd=repo)
        if rc != 0:
            return rc

    if not args.skip_common_visualize:
        rc = build_common_outputs(outdir=outdir, common_mode=args.common_mode)
        if rc != 0:
            return rc

    print("\n✓ QEMU golden pipeline complete")
    print(f"  outdir: {outdir}")
    print(f"  manifest: {manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
