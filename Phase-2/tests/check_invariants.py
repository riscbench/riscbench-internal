from __future__ import annotations

import argparse
import math
import sys
from typing import Tuple

import numpy as np
import pandas as pd


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    if (isinstance(a, float) and math.isnan(a)) and (isinstance(b, float) and math.isnan(b)):
        return True
    return abs(a - b) <= tol


def require(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def load_windows(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # minimal required columns for invariants
    req = [
        "core", "window_id",
        "resident_us", "is_resident_window",
        "active_frac", "stall_frac", "idle_frac",
        "sit"
    ]
    missing = [c for c in req if c not in df.columns]
    require(not missing, f"{path}: missing columns {missing}")
    return df


def check_sit_bounds(df: pd.DataFrame, tol: float = 1e-6):
    resident = df[df["is_resident_window"] == 1].copy()
    sits = resident["sit"].astype(float).to_numpy()
    require(np.all(sits >= -tol), "SIT below 0 found in resident windows")
    require(np.all(sits <= 1.0 + tol), "SIT above 1 found in resident windows")


def check_fracs_sum_to_one(df: pd.DataFrame, tol: float = 1e-6):
    resident = df[df["is_resident_window"] == 1].copy()
    s = (resident["active_frac"] + resident["stall_frac"] + resident["idle_frac"]).astype(float).to_numpy()
    require(np.all(np.abs(s - 1.0) <= tol), "Fractions do not sum to 1 in some resident windows")


def check_nonresident_are_nan(df: pd.DataFrame):
    nonres = df[df["is_resident_window"] == 0].copy()
    if len(nonres) == 0:
        return
    for col in ["active_frac", "stall_frac", "idle_frac", "sit"]:
        arr = nonres[col].astype(float).to_numpy()
        require(np.all(np.isnan(arr)), f"Non-resident windows must have NaN {col}")


def check_skip_w0(df: pd.DataFrame):
    # skip_w0 mask is [256, +inf) in datasets/residency/skip_w0.csv.
    # For arbitrary window sizes, w0 can be partially resident when window_us > 256.
    boundary_start = 256.0
    cores = sorted(df["core"].unique().tolist())
    for c in cores:
        row = df[(df["core"] == c) & (df["window_id"] == 0)]
        if len(row) == 0:
            # acceptable: w0 omitted entirely in sparse outputs
            continue
        require(len(row) == 1, f"Duplicate rows for (core={c}, window_id=0)")
        r = row.iloc[0]
        window_us = float(r["window_end_us"]) - float(r["window_start_us"])
        expected_w0 = max(0.0, window_us - boundary_start)
        got_w0 = float(r["resident_us"])
        require(abs(got_w0 - expected_w0) <= 1e-6, f"core {c} w0 resident_us {got_w0} != expected {expected_w0}")
        expected_flag = 1 if expected_w0 > 1e-6 else 0
        require(int(r["is_resident_window"]) == expected_flag, f"Expected w0 is_resident_window={expected_flag} for core {c}")


def _window_overlap(wid: int, start_us: float, end_us: float, window_us: float) -> float:
    ws = float(wid) * float(window_us)
    we = float(wid + 1) * float(window_us)
    return max(0.0, min(we, end_us) - max(ws, start_us))


def _expected_window_ids(start_us: float, end_us: float, window_us: float) -> range:
    if end_us <= start_us:
        return range(0)
    first = int(math.floor(start_us / window_us))
    last = int(math.floor((end_us - 1e-9) / window_us))
    return range(first, last + 1)


def _check_interval_windows(df: pd.DataFrame, start_us: float, end_us: float, window_us: float, label: str):
    cores = sorted(df["core"].unique().tolist())
    for c in cores:
        for wid in _expected_window_ids(start_us, end_us, window_us):
            exp = _window_overlap(wid, start_us, end_us, window_us)
            row = df[(df["core"] == c) & (df["window_id"] == wid)]
            require(len(row) == 1, f"{label}: expected (core={c}, window_id={wid}) row")
            got = float(row.iloc[0]["resident_us"])
            require(abs(got - exp) <= 1e-6, f"{label}: core {c} wid {wid}: resident_us {got} != expected {exp}")
            exp_flag = 1 if exp > 1e-6 else 0
            got_flag = int(row.iloc[0]["is_resident_window"])
            require(got_flag == exp_flag, f"{label}: core {c} wid {wid}: is_resident_window {got_flag} != expected {exp_flag}")


def check_exact_boundary(df: pd.DataFrame, window_us: float = 256.0):
    # exact_boundary mask is [0,256) independent of engine window size.
    start_us = 0.0
    end_us = 256.0
    _check_interval_windows(df, start_us, end_us, window_us, label="exact_boundary")

    # If 256 aligns exactly to window boundary, ensure the next window (if present) is non-resident.
    if abs((end_us / window_us) - round(end_us / window_us)) <= 1e-9:
        next_wid = int(round(end_us / window_us))
        cores = sorted(df["core"].unique().tolist())
        for c in cores:
            rn = df[(df["core"] == c) & (df["window_id"] == next_wid)]
            if len(rn) == 1:
                require(
                    int(rn.iloc[0]["is_resident_window"]) == 0,
                    f"exact_boundary: expected window_id={next_wid} non-resident for core {c}",
                )


def check_partial_expected_resident_us(df: pd.DataFrame, window_us: float = 256.0):
    # partial mask is [300,900) independent of engine window size.
    _check_interval_windows(df, start_us=300.0, end_us=900.0, window_us=window_us, label="partial")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", required=True, help="Path to *_windows.csv produced by engine")
    ap.add_argument("--mode", required=True, choices=["base", "all", "skip_w0", "partial", "exact_boundary"])
    ap.add_argument("--window-us", type=float, default=256.0)
    args = ap.parse_args()

    df = load_windows(args.windows)

    # Common invariants
    check_sit_bounds(df)
    check_fracs_sum_to_one(df)
    check_nonresident_are_nan(df)

    # Mode-specific invariants
    if args.mode == "skip_w0":
        check_skip_w0(df)
    elif args.mode == "partial":
        check_partial_expected_resident_us(df, window_us=args.window_us)
    elif args.mode == "exact_boundary":
        check_exact_boundary(df, window_us=args.window_us)

    print(f"PASS invariants: {args.mode} ({args.windows})")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(2)
