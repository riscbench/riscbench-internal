from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import pandas as pd

DEFAULT_TOLERANCE_SUMMARY_METRICS = [
    "sit_median",
    "sit_p95",
    "residency_active_avg",
    "residency_stall_avg",
    "residency_idle_avg",
    "resident_windows_total",
]

ALLOWED_COMPARISON_MODES = {"strict", "tolerance"}
ALLOWED_ASSERTION_OPS = {"gt", "ge", "lt", "le", ">", ">=", "<", "<="}


def fail(msg: str) -> None:
    raise AssertionError(msg)


def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= tol


def check_summary(actual: Dict[str, Any], expected: Dict[str, Any], tol: float) -> None:
    missing = [k for k in expected if k not in actual]
    if missing:
        fail(f"summary missing keys: {missing}")

    for k, ev in expected.items():
        av = actual[k]
        if isinstance(ev, float):
            if not approx(float(av), ev, tol):
                fail(f"summary mismatch for {k}: actual={av} expected={ev}")
        elif isinstance(ev, list):
            if list(av) != list(ev):
                fail(f"summary mismatch for {k}: actual={av} expected={ev}")
        else:
            if av != ev:
                fail(f"summary mismatch for {k}: actual={av} expected={ev}")


def check_windows(actual_df: pd.DataFrame, expected_rows: List[Dict[str, Any]], tol: float) -> None:
    actual = actual_df.sort_values(["core", "window_id"]).reset_index(drop=True)
    if len(actual) != len(expected_rows):
        fail(f"windows row count mismatch: actual={len(actual)} expected={len(expected_rows)}")

    for idx, expected in enumerate(expected_rows):
        row = actual.iloc[idx]
        for k, ev in expected.items():
            if k not in actual.columns:
                fail(f"windows missing column: {k}")
            av = row[k]
            if isinstance(ev, float):
                if not approx(float(av), ev, tol):
                    fail(
                        f"windows mismatch row={idx} col={k}: actual={av} expected={ev}"
                    )
            elif isinstance(ev, int):
                if int(av) != ev:
                    fail(
                        f"windows mismatch row={idx} col={k}: actual={int(av)} expected={ev}"
                    )
            else:
                if av != ev:
                    fail(
                        f"windows mismatch row={idx} col={k}: actual={av} expected={ev}"
                    )


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        fail(f"fixture not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"invalid JSON object in fixture: {path}")
    return payload


def is_matrix_payload(payload: Mapping[str, Any]) -> bool:
    return isinstance(payload.get("cases"), list)


def require_case_fields(case: Mapping[str, Any], case_id: str) -> None:
    required = ["workload", "trace_file", "comparison_mode", "window_us", "expected"]
    missing = [k for k in required if k not in case]
    if missing:
        fail(f"case '{case_id}' missing required fields: {missing}")

    mode = str(case.get("comparison_mode", "")).strip().lower()
    if mode not in ALLOWED_COMPARISON_MODES:
        fail(
            f"case '{case_id}' invalid comparison_mode='{case.get('comparison_mode')}'. "
            f"allowed={sorted(ALLOWED_COMPARISON_MODES)}"
        )


def get_case_by_id(payload: Mapping[str, Any], case_id: str) -> Dict[str, Any]:
    cases = payload.get("cases")
    if not isinstance(cases, list):
        fail("expected a matrix fixture with top-level 'cases' list")

    found: List[Dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        if str(case.get("case_id", "")).strip() == case_id:
            found.append(case)

    if not found:
        fail(f"case_id '{case_id}' not found in matrix fixture")
    if len(found) > 1:
        fail(f"case_id '{case_id}' is duplicated in matrix fixture")
    return found[0]


def to_float(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        fail(f"{label} must be numeric, got {value!r}")
    return float("nan")


def parse_tolerance_spec(
    spec: Any,
    *,
    metric: str,
    default_abs_tol: float,
    default_rel_tol: float,
) -> Tuple[float, float, float]:
    if isinstance(spec, dict):
        if "value" not in spec:
            fail(f"metric '{metric}' tolerance spec must contain 'value'")
        expected_value = to_float(spec["value"], f"{metric}.value")
        abs_tol = to_float(spec.get("abs_tol", default_abs_tol), f"{metric}.abs_tol")
        rel_tol = to_float(spec.get("rel_tol", default_rel_tol), f"{metric}.rel_tol")
    else:
        expected_value = to_float(spec, f"{metric}.value")
        abs_tol = float(default_abs_tol)
        rel_tol = float(default_rel_tol)

    if abs_tol < 0 or rel_tol < 0:
        fail(
            f"metric '{metric}' tolerance must be non-negative; "
            f"got abs_tol={abs_tol}, rel_tol={rel_tol}"
        )
    return expected_value, abs_tol, rel_tol


def within_tolerance(actual: float, expected: float, abs_tol: float, rel_tol: float) -> Tuple[bool, float, float]:
    if math.isnan(actual) and math.isnan(expected):
        return True, 0.0, 0.0
    diff = abs(actual - expected)
    rel_component = rel_tol * max(abs(actual), abs(expected))
    threshold = max(abs_tol, rel_component)
    return diff <= threshold, diff, threshold


def resolve_case_expected(case: Mapping[str, Any], matrix_path: Path, case_id: str) -> Dict[str, Any]:
    expected = case.get("expected")
    if not isinstance(expected, dict):
        fail(f"case '{case_id}' expected payload must be an object")

    fixture_ref = expected.get("fixture")
    if fixture_ref is None:
        return dict(expected)

    fixture_path = Path(str(fixture_ref))
    if not fixture_path.is_absolute():
        fixture_path = (matrix_path.parent / fixture_path).resolve()
    return load_json(fixture_path)


def check_tolerance_summary(
    actual_summary: Mapping[str, Any],
    summary_specs: Mapping[str, Any],
    *,
    case_id: str,
    workload: str,
    default_abs_tol: float,
    default_rel_tol: float,
) -> None:
    missing_metrics = [m for m in DEFAULT_TOLERANCE_SUMMARY_METRICS if m not in summary_specs]
    if missing_metrics:
        fail(
            f"case '{case_id}' (workload={workload}) missing required tolerance metrics: "
            f"{missing_metrics}"
        )

    for metric, spec in summary_specs.items():
        if metric not in actual_summary:
            fail(f"case '{case_id}' summary missing metric '{metric}'")
        expected_value, abs_tol, rel_tol = parse_tolerance_spec(
            spec,
            metric=metric,
            default_abs_tol=default_abs_tol,
            default_rel_tol=default_rel_tol,
        )
        actual_value = to_float(actual_summary[metric], f"{metric}.actual")
        ok, diff, threshold = within_tolerance(actual_value, expected_value, abs_tol, rel_tol)
        if not ok:
            fail(
                f"case '{case_id}' workload={workload} summary metric '{metric}' out of tolerance: "
                f"actual={actual_value} expected={expected_value} abs_diff={diff} "
                f"allowed<={threshold} (abs_tol={abs_tol}, rel_tol={rel_tol})"
            )


def check_tolerance_windows(
    actual_df: pd.DataFrame,
    window_checks: List[Dict[str, Any]],
    *,
    case_id: str,
    workload: str,
    default_abs_tol: float,
    default_rel_tol: float,
) -> None:
    required_cols = {"core", "window_id"}
    missing = [c for c in required_cols if c not in actual_df.columns]
    if missing:
        fail(f"case '{case_id}' windows missing required selector columns: {missing}")

    for idx, entry in enumerate(window_checks):
        if not isinstance(entry, dict):
            fail(f"case '{case_id}' window check #{idx} must be an object")
        selector = entry.get("selector")
        metrics = entry.get("metrics")
        if not isinstance(selector, dict) or not isinstance(metrics, dict):
            fail(
                f"case '{case_id}' window check #{idx} must contain object fields "
                f"'selector' and 'metrics'"
            )
        if "core" not in selector or "window_id" not in selector:
            fail(
                f"case '{case_id}' window check #{idx} selector must include 'core' and 'window_id'"
            )
        core = int(selector["core"])
        window_id = int(selector["window_id"])
        row = actual_df[(actual_df["core"] == core) & (actual_df["window_id"] == window_id)]
        if len(row) != 1:
            fail(
                f"case '{case_id}' workload={workload} window selector "
                f"(core={core}, window_id={window_id}) matched {len(row)} rows"
            )
        actual_row = row.iloc[0]

        for metric, spec in metrics.items():
            if metric not in actual_df.columns:
                fail(f"case '{case_id}' window metric '{metric}' missing from output columns")
            expected_value, abs_tol, rel_tol = parse_tolerance_spec(
                spec,
                metric=metric,
                default_abs_tol=default_abs_tol,
                default_rel_tol=default_rel_tol,
            )
            actual_value = to_float(actual_row[metric], f"{metric}.actual")
            ok, diff, threshold = within_tolerance(actual_value, expected_value, abs_tol, rel_tol)
            if not ok:
                fail(
                    f"case '{case_id}' workload={workload} window(core={core},window_id={window_id}) "
                    f"metric '{metric}' out of tolerance: actual={actual_value} expected={expected_value} "
                    f"abs_diff={diff} allowed<={threshold} (abs_tol={abs_tol}, rel_tol={rel_tol})"
                )


def check_matrix_case(
    actual_summary: Mapping[str, Any],
    actual_windows: pd.DataFrame,
    matrix_payload: Mapping[str, Any],
    matrix_path: Path,
    case_id: str,
    strict_tol: float,
) -> Dict[str, Any]:
    case = get_case_by_id(matrix_payload, case_id)
    require_case_fields(case, case_id=case_id)

    workload = str(case.get("workload", "")).strip()
    mode = str(case.get("comparison_mode", "")).strip().lower()
    expected_payload = resolve_case_expected(case, matrix_path=matrix_path, case_id=case_id)

    if mode == "strict":
        summary_expected = expected_payload.get("summary")
        if not isinstance(summary_expected, dict):
            fail(f"case '{case_id}' strict mode requires expected.summary object")
        check_summary(actual_summary, summary_expected, tol=float(strict_tol))

        windows_expected = expected_payload.get("windows")
        if windows_expected is not None:
            if not isinstance(windows_expected, list):
                fail(f"case '{case_id}' strict mode expected.windows must be a list")
            check_windows(actual_windows, windows_expected, tol=float(strict_tol))
        return case

    if mode == "tolerance":
        summary_specs = expected_payload.get("summary_metrics")
        if not isinstance(summary_specs, dict):
            fail(f"case '{case_id}' tolerance mode requires expected.summary_metrics object")
        default_abs_tol = to_float(case.get("abs_tol", 0.0), f"case '{case_id}'.abs_tol")
        default_rel_tol = to_float(case.get("rel_tol", 0.0), f"case '{case_id}'.rel_tol")
        if default_abs_tol < 0 or default_rel_tol < 0:
            fail(
                f"case '{case_id}' default tolerances must be non-negative; "
                f"got abs_tol={default_abs_tol}, rel_tol={default_rel_tol}"
            )

        check_tolerance_summary(
            actual_summary,
            summary_specs,
            case_id=case_id,
            workload=workload,
            default_abs_tol=default_abs_tol,
            default_rel_tol=default_rel_tol,
        )

        window_checks = expected_payload.get("window_metrics", [])
        if not isinstance(window_checks, list):
            fail(f"case '{case_id}' expected.window_metrics must be a list when provided")
        if window_checks:
            check_tolerance_windows(
                actual_windows,
                window_checks,
                case_id=case_id,
                workload=workload,
                default_abs_tol=default_abs_tol,
                default_rel_tol=default_rel_tol,
            )
        return case

    fail(f"case '{case_id}' unsupported comparison_mode='{mode}'")
    return case


def parse_case_summary_arg(entry: str) -> Tuple[str, Path]:
    if "=" not in entry:
        fail(f"--case-summary must be in '<case_id>=<summary_json>' form, got: {entry}")
    case_id, raw_path = entry.split("=", 1)
    case_id = case_id.strip()
    raw_path = raw_path.strip()
    if not case_id or not raw_path:
        fail(f"invalid --case-summary value: {entry}")
    return case_id, Path(raw_path)


def _resolve_endpoint_case_id(
    endpoint: Mapping[str, Any],
    cases_by_id: Mapping[str, Dict[str, Any]],
    *,
    assertion_name: str,
    side: str,
) -> str:
    endpoint_case_id = str(endpoint.get("case_id", "")).strip()
    if endpoint_case_id:
        if endpoint_case_id not in cases_by_id:
            fail(
                f"cross assertion '{assertion_name}' {side} references unknown case_id='{endpoint_case_id}'"
            )
        return endpoint_case_id

    workload = str(endpoint.get("workload", "")).strip()
    if not workload:
        fail(
            f"cross assertion '{assertion_name}' {side} must define either case_id or workload"
        )
    matches = [
        cid for cid, c in cases_by_id.items()
        if str(c.get("workload", "")).strip() == workload
    ]
    if not matches:
        fail(
            f"cross assertion '{assertion_name}' {side} workload='{workload}' matched no cases"
        )
    if len(matches) > 1:
        fail(
            f"cross assertion '{assertion_name}' {side} workload='{workload}' is ambiguous; "
            f"matching case_ids={matches}. Use case_id explicitly."
        )
    return matches[0]


def _check_relation(left: float, right: float, op: str, margin: float) -> Tuple[bool, str]:
    if op in {"gt", ">"}:
        threshold = right + margin
        return left > threshold, f"left > right + margin ({threshold})"
    if op in {"ge", ">="}:
        threshold = right + margin
        return left >= threshold, f"left >= right + margin ({threshold})"
    if op in {"lt", "<"}:
        threshold = right - margin
        return left < threshold, f"left < right - margin ({threshold})"
    if op in {"le", "<="}:
        threshold = right - margin
        return left <= threshold, f"left <= right - margin ({threshold})"
    fail(f"unsupported assertion operator '{op}', allowed={sorted(ALLOWED_ASSERTION_OPS)}")
    return False, ""


def evaluate_cross_workload_assertions(
    matrix_payload: Mapping[str, Any],
    case_summaries: Mapping[str, Mapping[str, Any]],
) -> List[str]:
    if not is_matrix_payload(matrix_payload):
        fail("cross-workload assertions require a matrix fixture containing 'cases'")

    assertions = matrix_payload.get("cross_workload_assertions", [])
    if assertions is None:
        return []
    if not isinstance(assertions, list):
        fail("matrix field 'cross_workload_assertions' must be a list when provided")
    if not assertions:
        return []

    cases = matrix_payload.get("cases", [])
    cases_by_id: Dict[str, Dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("case_id", "")).strip()
        if not case_id:
            continue
        if case_id in cases_by_id:
            fail(f"duplicate case_id in matrix fixture: {case_id}")
        cases_by_id[case_id] = case

    failures: List[str] = []
    for idx, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            fail(f"cross assertion at index {idx} must be an object")
        name = str(assertion.get("name", f"assertion_{idx}")).strip() or f"assertion_{idx}"
        left = assertion.get("left")
        right = assertion.get("right")
        if not isinstance(left, dict) or not isinstance(right, dict):
            fail(f"cross assertion '{name}' must contain object fields 'left' and 'right'")

        op = str(assertion.get("op", "gt")).strip().lower()
        if op not in ALLOWED_ASSERTION_OPS:
            fail(
                f"cross assertion '{name}' invalid op='{op}', "
                f"allowed={sorted(ALLOWED_ASSERTION_OPS)}"
            )
        margin = to_float(assertion.get("margin", 0.0), f"cross assertion '{name}'.margin")
        if margin < 0:
            fail(f"cross assertion '{name}' margin must be non-negative")

        left_case_id = _resolve_endpoint_case_id(left, cases_by_id, assertion_name=name, side="left")
        right_case_id = _resolve_endpoint_case_id(right, cases_by_id, assertion_name=name, side="right")

        left_metric = str(left.get("metric", "")).strip()
        right_metric = str(right.get("metric", "")).strip()
        if not left_metric or not right_metric:
            fail(f"cross assertion '{name}' both left.metric and right.metric are required")

        if left_case_id not in case_summaries:
            failures.append(
                f"[{name}] missing summary for left case_id='{left_case_id}'"
            )
            continue
        if right_case_id not in case_summaries:
            failures.append(
                f"[{name}] missing summary for right case_id='{right_case_id}'"
            )
            continue

        left_summary = case_summaries[left_case_id]
        right_summary = case_summaries[right_case_id]
        if left_metric not in left_summary:
            failures.append(
                f"[{name}] left metric '{left_metric}' missing in summary for case_id='{left_case_id}'"
            )
            continue
        if right_metric not in right_summary:
            failures.append(
                f"[{name}] right metric '{right_metric}' missing in summary for case_id='{right_case_id}'"
            )
            continue

        left_value = to_float(left_summary[left_metric], f"{name}.left.{left_metric}")
        right_value = to_float(right_summary[right_metric], f"{name}.right.{right_metric}")
        ok, rule = _check_relation(left_value, right_value, op, margin)
        if not ok:
            failures.append(
                f"[{name}] FAILED: left case_id={left_case_id} metric={left_metric} value={left_value} "
                f"violates '{rule}' where right case_id={right_case_id} "
                f"metric={right_metric} value={right_value}, margin={margin}"
            )
    return failures


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default=None, help="Path to *_windows.csv")
    ap.add_argument("--summary", default=None, help="Path to *_summary.json")
    ap.add_argument(
        "--expected",
        default="tests/fixtures/phase0_parity_expected.json",
        help="Expected parity fixture JSON (legacy strict or matrix)",
    )
    ap.add_argument("--tol", type=float, default=1e-9)
    ap.add_argument("--case-id", default=None, help="case_id for matrix fixtures")
    ap.add_argument(
        "--check-cross-workload",
        action="store_true",
        help="Validate matrix cross_workload_assertions using --case-summary",
    )
    ap.add_argument(
        "--case-summary",
        action="append",
        default=[],
        help="case summary mapping in form '<case_id>=<summary_json>' (repeatable)",
    )
    args = ap.parse_args()

    expected_path = Path(args.expected)
    if not expected_path.exists():
        fail(f"expected fixture not found: {expected_path}")
    expected_payload = load_json(expected_path)

    if args.check_cross_workload:
        case_summaries: Dict[str, Dict[str, Any]] = {}
        for entry in args.case_summary:
            case_id, summary_path = parse_case_summary_arg(entry)
            if case_id in case_summaries:
                fail(f"duplicate --case-summary case_id: {case_id}")
            case_summaries[case_id] = load_json(summary_path)
        if not case_summaries:
            fail("--check-cross-workload requires at least one --case-summary")
        failures = evaluate_cross_workload_assertions(
            expected_payload,
            case_summaries=case_summaries,
        )
        if failures:
            fail("\n".join(failures))
        assertions = expected_payload.get("cross_workload_assertions", [])
        count = len(assertions) if isinstance(assertions, list) else 0
        print(f"PASS parity cross-workload assertions: {count}")
        return

    if not args.windows or not args.summary:
        fail("--windows and --summary are required unless --check-cross-workload is set")

    actual_summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    actual_windows = pd.read_csv(args.windows)

    if is_matrix_payload(expected_payload):
        if not args.case_id:
            fail("matrix fixture requires --case-id for per-case parity checks")
        case = check_matrix_case(
            actual_summary=actual_summary,
            actual_windows=actual_windows,
            matrix_payload=expected_payload,
            matrix_path=expected_path,
            case_id=str(args.case_id),
            strict_tol=float(args.tol),
        )
        case_id = str(case.get("case_id", "")).strip()
        workload = str(case.get("workload", "")).strip()
        mode = str(case.get("comparison_mode", "")).strip().lower()
        print(
            f"PASS parity case={case_id} workload={workload} mode={mode}: "
            f"{args.windows} {args.summary}"
        )
        return

    if args.case_id:
        fail("--case-id cannot be used with legacy strict fixture")
    if "summary" not in expected_payload or "windows" not in expected_payload:
        fail(
            "legacy fixture requires top-level keys 'summary' and 'windows'; "
            "for matrix fixtures use --case-id"
        )
    check_summary(actual_summary, expected_payload["summary"], tol=float(args.tol))
    check_windows(actual_windows, expected_payload["windows"], tol=float(args.tol))

    print(f"PASS phase0 parity: {args.windows} {args.summary}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(2)
