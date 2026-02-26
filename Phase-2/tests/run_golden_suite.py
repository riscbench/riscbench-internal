from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any


def run(cmd: List[str]) -> Tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    return json.loads(path.read_text())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable, help="python executable")
    ap.add_argument("--outdir", default="golden_out", help="output directory")
    ap.add_argument("--manifest", default="datasets/manifest.json", help="datasets manifest")
    ap.add_argument("--window-us", type=float, default=None, help="override window_us (else manifest default)")
    ap.add_argument(
        "--no-work-sit-mode",
        choices=["global_active", "window_active"],
        default="window_active",
        help="Fallback SIT mode when work_done is unavailable",
    )
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(Path(args.manifest))

    window_us = float(args.window_us) if args.window_us is not None else float(manifest.get("window_us_default", 256.0))

    traces: List[str] = manifest.get("traces", [])
    masks: Dict[str, str] = manifest.get("residency_masks", {})

    # map masks -> invariant modes (keys must exist in manifest)
    mask_modes = [
        ("all", "all"),
        ("skip_w0", "skip_w0"),
        ("partial", "partial"),
        ("exact_boundary", "exact_boundary"),
    ]

    failures = []

    for trace in traces:
        trace_path = Path(trace)
        if not trace_path.exists():
            print(f"SKIP missing trace: {trace}")
            continue

        # Base run (no residency)
        out_prefix = outdir / f"{trace_path.stem}__base"
        cmd_engine = [
            args.python, "sit_engine_phase1.py",
            "--trace", str(trace_path),
            "--window-us", str(window_us),
            "--out-prefix", str(out_prefix),
            "--no-work-sit-mode", str(args.no_work_sit_mode),
        ]
        rc, out = run(cmd_engine)
        if rc != 0:
            failures.append((str(trace_path), "base(engine)", out))
            continue

        windows_csv = str(out_prefix) + "_windows.csv"
        cmd_inv = [
            args.python, "tests/check_invariants.py",
            "--windows", windows_csv,
            "--mode", "base",
            "--window-us", str(window_us),
        ]
        rc, out2 = run(cmd_inv)
        if rc != 0:
            failures.append((str(trace_path), "base(invariants)", out2))

        # Residency mask runs (if present in manifest and file exists)
        for mask_key, mode in mask_modes:
            mask_file = masks.get(mask_key, None)
            if mask_file is None:
                continue

            mask_path = Path(mask_file)
            if not mask_path.exists():
                print(f"SKIP missing mask file: {mask_key} -> {mask_path}")
                continue

            out_prefix = outdir / f"{trace_path.stem}__{mode}"
            cmd_engine = [
                args.python, "sit_engine_phase1.py",
                "--trace", str(trace_path),
                "--residency", str(mask_path),
                "--window-us", str(window_us),
                "--out-prefix", str(out_prefix),
                "--no-work-sit-mode", str(args.no_work_sit_mode),
            ]
            rc, out = run(cmd_engine)
            if rc != 0:
                failures.append((str(trace_path), f"{mode}(engine)", out))
                continue

            windows_csv = str(out_prefix) + "_windows.csv"
            cmd_inv = [
                args.python, "tests/check_invariants.py",
                "--windows", windows_csv,
                "--mode", mode,
                "--window-us", str(window_us),
            ]
            rc, out2 = run(cmd_inv)
            if rc != 0:
                failures.append((str(trace_path), f"{mode}(invariants)", out2))

    if failures:
        print("\nFAILURES:")
        for tr, stage, msg in failures:
            print(f"\n--- {tr} :: {stage} ---")
            print(msg.strip())
        sys.exit(2)

    print("\nALL PASS: golden suite")
    sys.exit(0)


if __name__ == "__main__":
    main()
