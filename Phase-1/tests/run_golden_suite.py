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
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(Path(args.manifest))

    window_us = float(args.window_us) if args.window_us is not None else float(manifest.get("window_us_default", 256.0))

    traces: List[str] = manifest.get("traces", [])
    masks: Dict[str, str] = manifest.get("residency_masks", {})
    phase0_fixture = Path("tests/fixtures/phase0_parity_expected.json")
    phase0_parity_executed = False
    phase0_expected_trace = None

    if not phase0_fixture.exists():
        failures = [("<manifest>", "config", f"Missing Phase-0 parity fixture: {phase0_fixture}")]
        print("\nFAILURES:")
        for tr, stage, msg in failures:
            print(f"\n--- {tr} :: {stage} ---")
            print(msg.strip())
        sys.exit(2)
    else:
        phase0_payload = json.loads(phase0_fixture.read_text())
        phase0_expected_trace = str(phase0_payload.get("trace_file", "")).strip()
        if not phase0_expected_trace:
            failures = [("<manifest>", "config", f"Invalid Phase-0 parity fixture (trace_file missing): {phase0_fixture}")]
            print("\nFAILURES:")
            for tr, stage, msg in failures:
                print(f"\n--- {tr} :: {stage} ---")
                print(msg.strip())
            sys.exit(2)

    # map masks -> invariant modes (keys must exist in manifest)
    mask_modes = [
        ("all", "all"),
        ("skip_w0", "skip_w0"),
        ("partial", "partial"),
        ("exact_boundary", "exact_boundary"),
    ]

    failures = []
    executed_traces = 0
    executed_runs = 0

    # Manifest sanity checks must fail-fast; SKIP here can hide broken baselines.
    if not traces:
        failures.append(("<manifest>", "config", "No traces listed in manifest"))

    missing_mask_keys = [k for (k, _) in mask_modes if k not in masks]
    if missing_mask_keys:
        failures.append(
            (
                "<manifest>",
                "config",
                f"Missing residency mask keys: {missing_mask_keys}. "
                f"Required keys: {[k for (k, _) in mask_modes]}",
            )
        )

    for mask_key, _ in mask_modes:
        if mask_key in masks:
            mask_path = Path(masks[mask_key])
            if not mask_path.exists():
                failures.append(
                    ("<manifest>", "config", f"Mask file not found for {mask_key}: {mask_path}")
                )

    if failures:
        print("\nFAILURES:")
        for tr, stage, msg in failures:
            print(f"\n--- {tr} :: {stage} ---")
            print(msg.strip())
        sys.exit(2)

    for trace in traces:
        trace_path = Path(trace)
        if not trace_path.exists():
            failures.append((str(trace_path), "config", "Trace file not found"))
            continue
        executed_traces += 1

        # Base run (no residency)
        out_prefix = outdir / f"{trace_path.stem}__base"
        cmd_engine = [
            args.python, "sit_engine_phase1.py",
            "--trace", str(trace_path),
            "--window-us", str(window_us),
            "--out-prefix", str(out_prefix),
        ]
        rc, out = run(cmd_engine)
        if rc != 0:
            failures.append((str(trace_path), "base(engine)", out))
            continue
        executed_runs += 1

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

        # Phase-0 strict parity check (trace_F sample baseline)
        if trace_path.as_posix() == Path(phase0_expected_trace).as_posix():
            summary_json = str(out_prefix) + "_summary.json"
            cmd_parity = [
                args.python, "tests/check_phase0_parity.py",
                "--windows", windows_csv,
                "--summary", summary_json,
                "--expected", str(phase0_fixture),
            ]
            rc, out3 = run(cmd_parity)
            if rc != 0:
                failures.append((str(trace_path), "base(phase0_parity)", out3))
            else:
                phase0_parity_executed = True

        # Residency mask runs (if present in manifest and file exists)
        for mask_key, mode in mask_modes:
            mask_file = masks.get(mask_key, None)
            if mask_file is None:
                continue

            mask_path = Path(mask_file)
            if not mask_path.exists():
                failures.append((str(trace_path), f"{mode}(config)", f"Mask file not found: {mask_path}"))
                continue

            out_prefix = outdir / f"{trace_path.stem}__{mode}"
            cmd_engine = [
                args.python, "sit_engine_phase1.py",
                "--trace", str(trace_path),
                "--residency", str(mask_path),
                "--window-us", str(window_us),
                "--out-prefix", str(out_prefix),
            ]
            rc, out = run(cmd_engine)
            if rc != 0:
                failures.append((str(trace_path), f"{mode}(engine)", out))
                continue
            executed_runs += 1

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

    if executed_traces == 0:
        failures.append(("<manifest>", "config", "No trace files were executed"))
    if executed_runs == 0:
        failures.append(("<manifest>", "config", "No golden runs were executed"))
    if not phase0_parity_executed:
        failures.append(
            (
                "<manifest>",
                "config",
                f"Phase-0 parity trace not executed. Ensure manifest includes {phase0_expected_trace}",
            )
        )

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
