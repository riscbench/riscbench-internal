from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any

REQUIRED_PARITY_CASE_FIELDS = ["case_id", "workload", "trace_file", "comparison_mode", "window_us", "expected"]
ALLOWED_PARITY_MODES = {"strict", "tolerance"}


def run(cmd: List[str]) -> Tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    return json.loads(path.read_text())


def load_json(path: Path, what: str) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{what} not found: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{what} must be a JSON object: {path}")
    return payload


def path_key(value: str) -> str:
    return Path(value).as_posix()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default=sys.executable, help="python executable")
    ap.add_argument("--outdir", default="golden_out", help="output directory")
    ap.add_argument("--manifest", default="datasets/manifest.json", help="datasets manifest")
    ap.add_argument("--window-us", type=float, default=None, help="override window_us (else manifest default)")
    ap.add_argument(
        "--parity-matrix",
        default="tests/fixtures/parity_baseline_matrix.json",
        help="Parity baseline matrix fixture JSON",
    )
    ap.add_argument(
        "--phase0-expected",
        default="tests/fixtures/phase0_parity_expected.json",
        help="Legacy strict phase0 fixture used for backward-compatibility checks",
    )
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    startup_failures: List[Tuple[str, str, str]] = []
    manifest: Dict[str, Any] = {}
    parity_matrix: Dict[str, Any] = {}
    phase0_fixture: Dict[str, Any] = {}
    parity_matrix_path = Path(args.parity_matrix)
    phase0_fixture_path = Path(args.phase0_expected)

    try:
        manifest = load_manifest(Path(args.manifest))
    except Exception as e:
        startup_failures.append((args.manifest, "config", str(e)))
    try:
        parity_matrix = load_json(parity_matrix_path, "parity matrix fixture")
    except Exception as e:
        startup_failures.append((str(parity_matrix_path), "config", str(e)))
    try:
        phase0_fixture = load_json(phase0_fixture_path, "Phase-0 parity fixture")
    except Exception as e:
        startup_failures.append((str(phase0_fixture_path), "config", str(e)))

    if startup_failures:
        print("\nFAILURES:")
        for tr, stage, msg in startup_failures:
            print(f"\n--- {tr} :: {stage} ---")
            print(msg.strip())
        sys.exit(2)

    window_us = float(args.window_us) if args.window_us is not None else float(manifest.get("window_us_default", 256.0))

    traces: List[str] = manifest.get("traces", [])
    masks: Dict[str, str] = manifest.get("residency_masks", {})
    phase0_parity_executed = False
    phase0_expected_trace = str(phase0_fixture.get("trace_file", "")).strip()
    if not phase0_expected_trace:
        failures = [("<manifest>", "config", f"Invalid Phase-0 parity fixture (trace_file missing): {phase0_fixture_path}")]
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

    # Parity matrix sanity checks.
    parity_cases = parity_matrix.get("cases", [])
    if not isinstance(parity_cases, list) or len(parity_cases) == 0:
        failures.append((str(parity_matrix_path), "config", "Parity matrix must define non-empty 'cases' list"))
        parity_cases = []

    manifest_trace_keys = {path_key(t) for t in traces}
    seen_case_ids = set()
    has_phase0_strict_case = False
    for idx, case in enumerate(parity_cases):
        if not isinstance(case, dict):
            failures.append((str(parity_matrix_path), "config", f"Case index {idx} must be an object"))
            continue

        case_id = str(case.get("case_id", "")).strip()
        if not case_id:
            failures.append((str(parity_matrix_path), "config", f"Case index {idx} missing case_id"))
            continue
        if case_id in seen_case_ids:
            failures.append((str(parity_matrix_path), "config", f"Duplicate case_id in parity matrix: {case_id}"))
        seen_case_ids.add(case_id)

        missing_fields = [k for k in REQUIRED_PARITY_CASE_FIELDS if k not in case]
        if missing_fields:
            failures.append(
                (
                    str(parity_matrix_path),
                    "config",
                    f"Case '{case_id}' missing required fields: {missing_fields}",
                )
            )
            continue

        mode = str(case.get("comparison_mode", "")).strip().lower()
        if mode not in ALLOWED_PARITY_MODES:
            failures.append(
                (
                    str(parity_matrix_path),
                    "config",
                    f"Case '{case_id}' invalid comparison_mode='{case.get('comparison_mode')}', "
                    f"allowed={sorted(ALLOWED_PARITY_MODES)}",
                )
            )

        trace_file = str(case.get("trace_file", "")).strip()
        if path_key(trace_file) not in manifest_trace_keys:
            failures.append(
                (
                    str(parity_matrix_path),
                    "config",
                    f"Case '{case_id}' trace_file not listed in manifest traces: {trace_file}",
                )
            )

        try:
            _ = float(case.get("window_us"))
        except (TypeError, ValueError):
            failures.append(
                (
                    str(parity_matrix_path),
                    "config",
                    f"Case '{case_id}' window_us must be numeric, got {case.get('window_us')!r}",
                )
            )

        expected = case.get("expected")
        if not isinstance(expected, dict):
            failures.append(
                (
                    str(parity_matrix_path),
                    "config",
                    f"Case '{case_id}' expected must be an object",
                )
            )

        if mode == "strict" and path_key(trace_file) == path_key(phase0_expected_trace):
            has_phase0_strict_case = True

    if not has_phase0_strict_case:
        failures.append(
            (
                str(parity_matrix_path),
                "config",
                "Parity matrix must include a strict case for "
                f"{phase0_expected_trace} to preserve Phase-0 trace_F parity behavior",
            )
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

    # Run workload-specific parity matrix cases independently.
    parity_case_summaries: Dict[str, Path] = {}
    parity_cases_executed = 0
    for case in parity_cases:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id", "")).strip()
        workload = str(case.get("workload", "")).strip()
        trace_file = str(case.get("trace_file", "")).strip()
        mode = str(case.get("comparison_mode", "")).strip().lower()
        case_window_us = float(case.get("window_us", window_us))
        case_label = f"case:{case_id} workload:{workload}"

        trace_path = Path(trace_file)
        if not trace_path.exists():
            failures.append((case_label, "parity(config)", f"Trace file not found: {trace_path}"))
            continue

        parity_out_prefix = outdir / f"parity__{case_id}"
        cmd_engine = [
            args.python, "sit_engine_phase1.py",
            "--trace", str(trace_path),
            "--window-us", str(case_window_us),
            "--out-prefix", str(parity_out_prefix),
        ]
        rc, out = run(cmd_engine)
        if rc != 0:
            failures.append((case_label, "parity(engine)", out))
            continue
        executed_runs += 1
        parity_cases_executed += 1

        windows_csv = str(parity_out_prefix) + "_windows.csv"
        summary_json = str(parity_out_prefix) + "_summary.json"
        parity_case_summaries[case_id] = Path(summary_json)
        cmd_parity = [
            args.python, "tests/check_phase0_parity.py",
            "--windows", windows_csv,
            "--summary", summary_json,
            "--expected", str(parity_matrix_path),
            "--case-id", case_id,
        ]
        rc, out = run(cmd_parity)
        if rc != 0:
            failures.append((case_label, f"parity({mode})", out))
            continue

        if mode == "strict" and trace_path.as_posix() == Path(phase0_expected_trace).as_posix():
            phase0_parity_executed = True

    # Optional cross-workload assertions from matrix.
    if parity_cases:
        cmd_cross = [
            args.python, "tests/check_phase0_parity.py",
            "--expected", str(parity_matrix_path),
            "--check-cross-workload",
        ]
        for case_id in sorted(parity_case_summaries.keys()):
            cmd_cross.extend(["--case-summary", f"{case_id}={parity_case_summaries[case_id]}"])
        rc, out = run(cmd_cross)
        if rc != 0:
            failures.append(("<parity-matrix>", "parity(cross_workload)", out))

    if executed_traces == 0:
        failures.append(("<manifest>", "config", "No trace files were executed"))
    if executed_runs == 0:
        failures.append(("<manifest>", "config", "No golden runs were executed"))
    if parity_cases_executed == 0:
        failures.append((str(parity_matrix_path), "config", "No parity matrix cases were executed"))
    if not phase0_parity_executed:
        failures.append(
            (
                "<manifest>",
                "config",
                f"Phase-0 strict parity case did not pass for trace {phase0_expected_trace}",
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
