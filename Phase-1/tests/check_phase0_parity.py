from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument(
        "--expected",
        default="tests/fixtures/phase0_parity_expected.json",
        help="expected parity fixture JSON",
    )
    ap.add_argument("--tol", type=float, default=1e-9)
    args = ap.parse_args()

    expected_path = Path(args.expected)
    if not expected_path.exists():
        fail(f"expected fixture not found: {expected_path}")

    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual_summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    actual_windows = pd.read_csv(args.windows)

    check_summary(actual_summary, expected["summary"], tol=float(args.tol))
    check_windows(actual_windows, expected["windows"], tol=float(args.tol))

    print(f"PASS phase0 parity: {args.windows} {args.summary}")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(2)
