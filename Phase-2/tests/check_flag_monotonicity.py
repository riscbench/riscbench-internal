from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, Tuple


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def load_summary(path: str) -> Dict[str, float]:
    p = Path(path).expanduser().resolve()
    require(p.exists(), f"summary not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return obj


def metric(summary: Dict[str, float], key: str) -> float:
    v = float(summary.get(key, float("nan")))
    return v


def check_variant(
    label: str,
    baseline: Dict[str, float],
    variant: Dict[str, float],
    min_sit_drop: float,
    min_stall_rise: float,
    max_idle_rise: float,
) -> Tuple[bool, str]:
    b_sit = metric(baseline, "sit_median")
    v_sit = metric(variant, "sit_median")
    b_stall = metric(baseline, "residency_stall_avg")
    v_stall = metric(variant, "residency_stall_avg")
    b_idle = metric(baseline, "residency_idle_avg")
    v_idle = metric(variant, "residency_idle_avg")

    for name, val in [
        ("baseline sit_median", b_sit),
        (f"{label} sit_median", v_sit),
        ("baseline residency_stall_avg", b_stall),
        (f"{label} residency_stall_avg", v_stall),
        ("baseline residency_idle_avg", b_idle),
        (f"{label} residency_idle_avg", v_idle),
    ]:
        if not math.isfinite(val):
            return False, f"{name} is not finite"

    sit_drop = b_sit - v_sit
    stall_rise = v_stall - b_stall
    idle_rise = v_idle - b_idle

    if sit_drop < min_sit_drop:
        return (
            False,
            f"{label}: sit_median drop too small ({sit_drop:.6f} < {min_sit_drop:.6f})",
        )
    if stall_rise < min_stall_rise:
        return (
            False,
            f"{label}: stall rise too small ({stall_rise:.6f} < {min_stall_rise:.6f})",
        )
    if idle_rise > max_idle_rise:
        return (
            False,
            f"{label}: idle rise too large ({idle_rise:.6f} > {max_idle_rise:.6f})",
        )

    msg = (
        f"{label}: PASS "
        f"(sit_drop={sit_drop:.6f}, stall_rise={stall_rise:.6f}, idle_rise={idle_rise:.6f})"
    )
    return True, msg


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Check monotonic flag behavior versus baseline summary.json"
    )
    ap.add_argument("--baseline", required=True, help="Baseline run summary.json")
    ap.add_argument("--branch", default=None, help="Branch-mispredict run summary.json")
    ap.add_argument("--cache", default=None, help="Cache-pressure run summary.json")
    ap.add_argument("--both", default=None, help="Branch+cache run summary.json")
    ap.add_argument("--min-sit-drop", type=float, default=0.02)
    ap.add_argument("--min-stall-rise", type=float, default=0.02)
    ap.add_argument(
        "--max-idle-rise",
        type=float,
        default=0.20,
        help="Upper bound on idle increase vs baseline",
    )
    args = ap.parse_args()

    baseline = load_summary(args.baseline)
    variants = {
        "branch": args.branch,
        "cache": args.cache,
        "both": args.both,
    }
    selected = [(k, v) for k, v in variants.items() if v]
    require(selected, "pass at least one variant summary (--branch/--cache/--both)")

    ok_all = True
    for label, p in selected:
        variant = load_summary(p)
        ok, msg = check_variant(
            label=label,
            baseline=baseline,
            variant=variant,
            min_sit_drop=float(args.min_sit_drop),
            min_stall_rise=float(args.min_stall_rise),
            max_idle_rise=float(args.max_idle_rise),
        )
        if ok:
            print(msg)
        else:
            ok_all = False
            print("FAIL:", msg)

    if not ok_all:
        raise SystemExit(2)
    print("PASS monotonicity checks")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(2)
