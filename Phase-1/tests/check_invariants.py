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
    cores = sorted(df["core"].unique().tolist())
    for c in cores:
        row = df[(df["core"] == c) & (df["window_id"] == 0)]
        if len(row) == 0:
            # acceptable: w0 omitted entirely => implicitly non-resident / no contribution
            continue
        require(len(row) == 1, f"Duplicate rows for (core={c}, window_id=0)")
        require(int(row.iloc[0]["is_resident_window"]) == 0, f"Expected w0 non-resident for core {c}")


def check_exact_boundary(df: pd.DataFrame):
    # exact boundary residency [0,256) => w0 resident, w1 non-resident (if present)
    # Check per core:
    cores = sorted(df["core"].unique().tolist())
    
    for c in cores:
        r0 = df[(df["core"] == c) & (df["window_id"] == 0)]
        require(len(r0) == 1, f"Expected w0 row for core {c}")
        require(int(r0.iloc[0]["is_resident_window"]) == 1, f"Expected w0 resident for core {c}")

        r1 = df[(df["core"] == c) & (df["window_id"] == 1)]
        # w1 should exist in your union-key model if residency created it; otherwise skip check
        if len(r1) == 1:
            require(int(r1.iloc[0]["is_resident_window"]) == 0, f"Expected w1 non-resident for core {c}")


def check_partial_expected_resident_us(df: pd.DataFrame, window_us: float = 256.0, tol: float = 1e-6):
    # For residency [300,900) with window_us=256:
    # w1 resident_us = 212, w2 = 256, w3 = 132
    expected = {1: 212.0, 2: 256.0, 3: 132.0}
    cores = sorted(df["core"].unique().tolist())
    for c in cores:
        for wid, exp in expected.items():
            row = df[(df["core"] == c) & (df["window_id"] == wid)]
            require(len(row) == 1, f"Expected (core={c}, window_id={wid}) row to exist for partial test")
            got = float(row.iloc[0]["resident_us"])
            require(abs(got - exp) <= tol, f"core {c} wid {wid}: resident_us {got} != expected {exp}")


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
        require(abs(args.window_us - 256.0) < 1e-9, "partial check assumes window_us=256")
        check_partial_expected_resident_us(df, window_us=args.window_us)
    elif args.mode == "exact_boundary":
        check_exact_boundary(df)

    print(f"PASS invariants: {args.mode} ({args.windows})")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(2)
