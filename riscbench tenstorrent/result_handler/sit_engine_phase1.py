#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd

_BUNDLE_ROOT = Path(__file__).resolve().parent.parent
if str(_BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUNDLE_ROOT))

from sit_classifier.adapters.baseline_adapter import BaselineAdapter

VALID_STATES = {"active", "stall", "idle"}


def split_interval_into_windows(start_us: float, end_us: float, window_us: float):
    """Yield (window_id, overlap_us) pieces for [start_us, end_us) split by fixed windows."""
    if end_us <= start_us:
        return
    w0 = int(math.floor(start_us / window_us))
    w1 = int(math.floor((end_us - 1e-9) / window_us))  # exact-boundary correctness
    for wid in range(w0, w1 + 1):
        w_start = wid * window_us
        w_end = (wid + 1) * window_us
        overlap = max(0.0, min(end_us, w_end) - max(start_us, w_start))
        if overlap > 0:
            yield wid, overlap


def percentile(values, p):
    if len(values) == 0:
        return float("nan")
    return float(np.percentile(np.array(values, dtype=float), p))


def merge_intervals(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Merge overlapping/adjacent half-open intervals."""
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda t: (t[0], t[1]))
    out: List[Tuple[float, float]] = []
    cs, ce = intervals[0]
    for s, e in intervals[1:]:
        if e <= s:
            continue
        if s <= ce:  # overlap/adjacent
            ce = max(ce, e)
        else:
            out.append((cs, ce))
            cs, ce = s, e
    out.append((cs, ce))
    return out


def intersect_with_mask(start: float, end: float, mask: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Return segments of [start,end) that lie inside union(mask). mask must be merged & sorted."""
    if end <= start or not mask:
        return []
    res: List[Tuple[float, float]] = []
    for ms, me in mask:
        if me <= start:
            continue
        if ms >= end:
            break
        s2 = max(start, ms)
        e2 = min(end, me)
        if e2 > s2:
            res.append((s2, e2))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, help="Trace input (baseline adapter reads CSV)")
    ap.add_argument("--residency", default=None, help="Residency input (baseline adapter reads CSV)")
    ap.add_argument("--window-us", type=float, default=256.0, help="Window size in microseconds")
    ap.add_argument("--out-prefix", default="sit_out", help="Output prefix (CSV + JSON)")
    ap.add_argument("--expected-work-rate", type=float, default=None, help="Expected work per us for normalization")
    ap.add_argument(
        "--no-work-sit-mode",
        choices=["global_active", "window_active"],
        default="global_active",
        help=(
            "Fallback SIT mode when work_done is unavailable: "
            "global_active=total_active/total_resident for all windows, "
            "window_active=per-window active fraction"
        ),
    )
    ap.add_argument("--debug-sit", action="store_true", help="Print raw SIT components before normalization")
    args = ap.parse_args()

    window_us = float(args.window_us)

    # Adapter boundary: engine consumes only normalized events
    adapter = BaselineAdapter(trace_path=args.trace, residency_path=args.residency)
    df = adapter.load_state_intervals()
    rdf = adapter.load_residency_intervals()  # None if not provided

    # Build residency mask per core (merged)
    residency_by_core: Optional[Dict[int, List[Tuple[float, float]]]] = None
    if rdf is not None:
        residency_by_core = {}
        for r in rdf.itertuples(index=False):
            s = float(getattr(r, "start_us"))
            e = float(getattr(r, "end_us"))
            c = int(getattr(r, "core"))
            if e > s:
                residency_by_core.setdefault(c, []).append((s, e))
        for c in list(residency_by_core.keys()):
            residency_by_core[c] = merge_intervals(residency_by_core[c])

    # resident_us per (core, window)
    resident_acc: Dict[Tuple[int, int], float] = {}
    if residency_by_core is not None:
        for core, intervals in residency_by_core.items():
            for s, e in intervals:
                for wid, ov in split_interval_into_windows(s, e, window_us):
                    resident_acc[(core, wid)] = resident_acc.get((core, wid), 0.0) + ov

    # state_us per (core, window), gated by residency if present
    state_acc: Dict[Tuple[int, int], Dict[str, float]] = {}
    work_acc: Dict[Tuple[int, int], float] = {}
    work_enabled = "work_done" in df.columns
    for row in df.itertuples(index=False):
        start = float(row.start_us)
        end = float(row.end_us)
        core = int(row.core)
        state = str(row.state)
        if state not in VALID_STATES or end <= start:
            continue

        if residency_by_core is None:
            pieces = [(start, end)]
        else:
            mask = residency_by_core.get(core, [])
            pieces = intersect_with_mask(start, end, mask)
            if not pieces:
                continue

        for ps, pe in pieces:
            for wid, overlap in split_interval_into_windows(ps, pe, window_us):
                key = (core, wid)
                if key not in state_acc:
                    state_acc[key] = {"active_us": 0.0, "stall_us": 0.0, "idle_us": 0.0}
                state_acc[key][f"{state}_us"] += overlap
                if work_enabled:
                    duration = max(0.0, end - start)
                    if duration > 0:
                        work_rate = float(getattr(row, "work_done", 0.0)) / duration
                        work_acc[key] = work_acc.get(key, 0.0) + (work_rate * overlap)

    # Union of keys to output
    all_keys = set(state_acc.keys())
    if residency_by_core is not None:
        all_keys |= set(resident_acc.keys())

    # FIRST PASS: Calculate global totals for SIT calculation when work_done is unavailable
    total_active_us = 0.0
    total_stall_us = 0.0
    total_idle_us = 0.0
    total_resident_us = 0.0
    
    for (core, wid) in sorted(all_keys, key=lambda x: (x[0], x[1])):
        resident_us = window_us if residency_by_core is None else resident_acc.get((core, wid), 0.0)
        if resident_us > 0:
            d = state_acc.get((core, wid), {"active_us": 0.0, "stall_us": 0.0, "idle_us": 0.0})
            active = float(d["active_us"])
            stall = float(d["stall_us"])
            idle = float(d["idle_us"])
            
            total = active + stall + idle
            if total < resident_us:
                idle += (resident_us - total)  # gap-fill inside residency
            
            total_active_us += active
            total_stall_us += stall
            total_idle_us += idle
            total_resident_us += resident_us
    
    # Calculate global active fraction fallback when work_done is unavailable.
    global_sit_fallback = float("nan")
    if not work_enabled and total_resident_us > 0:
        global_sit_fallback = total_active_us / total_resident_us
    
    # SECOND PASS: Generate output records using global SIT if needed
    records = []
    debug_sit_raw: List[float] = []
    debug_sit_clamped: List[float] = []
    
    # Reset for second pass
    total_active_us = 0.0
    total_stall_us = 0.0
    total_idle_us = 0.0
    total_resident_us = 0.0
    
    for (core, wid) in sorted(all_keys, key=lambda x: (x[0], x[1])):
        w_start = wid * window_us
        w_end = (wid + 1) * window_us

        resident_us = window_us if residency_by_core is None else resident_acc.get((core, wid), 0.0)
        is_resident_window = 1 if resident_us > 0 else 0

        d = state_acc.get((core, wid), {"active_us": 0.0, "stall_us": 0.0, "idle_us": 0.0})
        active = float(d["active_us"])
        stall = float(d["stall_us"])
        idle = float(d["idle_us"])
        work_done = work_acc.get((core, wid), 0.0) if work_enabled else float("nan")

        observed_work_rate = float("nan")
        if resident_us > 0:
            denom = resident_us  # normalize by resident time
            total = active + stall + idle
            if total < denom:
                idle += (denom - total)  # gap-fill inside residency
                total = denom

            active_f = active / total
            stall_f = stall / total
            idle_f = idle / total

            sit_window_active = float("nan")
            sit_global_active = float("nan")
            if work_enabled:
                observed_work_rate = work_done / denom
            if work_enabled and args.expected_work_rate is not None and args.expected_work_rate > 0:
                sit_raw = (work_done / denom) / float(args.expected_work_rate)
                if not math.isfinite(sit_raw) or (sit_raw <= 0.0 and active > 0.0):
                    sit_raw = active_f  # fallback when work_done is missing/zero
            elif not work_enabled:
                sit_window_active = active_f
                sit_global_active = global_sit_fallback
                if args.no_work_sit_mode == "global_active":
                    sit_raw = sit_global_active
                else:
                    sit_raw = sit_window_active
            else:
                sit_raw = active_f  # fallback
            sit = max(0.0, min(1.0, sit_raw))
        else:
            active_f = float("nan")
            stall_f = float("nan")
            idle_f = float("nan")
            sit_raw = float("nan")
            sit = float("nan")
            sit_window_active = float("nan")
            sit_global_active = float("nan")

        records.append({
            "core": core,
            "window_id": wid,
            "window_start_us": w_start,
            "window_end_us": w_end,
            "resident_us": resident_us,
            "resident_frac_of_window": (resident_us / window_us) if window_us > 0 else float("nan"),
            "is_resident_window": is_resident_window,
            "active_frac": active_f,
            "stall_frac": stall_f,
            "idle_frac": idle_f,
            "work_done": work_done,
            "observed_flops": work_done,
            "observed_work_rate": observed_work_rate,
            "observed_flops_per_us": observed_work_rate,
            "sit_no_work_window_active": sit_window_active,
            "sit_no_work_global_active": sit_global_active,
            "sit": sit,
        })
        if is_resident_window == 1:
            total_active_us += active
            total_stall_us += stall
            total_idle_us += idle
            total_resident_us += resident_us
            if not math.isnan(sit_raw):
                debug_sit_raw.append(float(sit_raw))
            if not math.isnan(sit):
                debug_sit_clamped.append(float(sit))

    out_cols = [
        "core", "window_id", "window_start_us", "window_end_us",
        "resident_us", "resident_frac_of_window", "is_resident_window",
        "active_frac", "stall_frac", "idle_frac",
        "work_done", "observed_flops", "observed_work_rate", "observed_flops_per_us",
        "sit_no_work_window_active", "sit_no_work_global_active",
        "sit",
    ]
    out = pd.DataFrame.from_records(records, columns=out_cols)
    out = out.sort_values(["core", "window_id"]).reset_index(drop=True)

    cores_present = sorted(out["core"].unique().tolist()) if len(out) else []
    total_cores = max(len(cores_present), 1)

    aggregate_state_acc: Dict[int, Dict[str, float]] = {}
    aggregate_resident_acc: Dict[int, float] = {}
    aggregate_work_acc: Dict[int, float] = {}
    aggregate_resident_cores: Dict[int, int] = {}
    all_window_ids = sorted({wid for (_core, wid) in all_keys})

    for (core, wid) in all_keys:
        resident_us = window_us if residency_by_core is None else resident_acc.get((core, wid), 0.0)
        if wid not in aggregate_state_acc:
            aggregate_state_acc[wid] = {"active_us": 0.0, "stall_us": 0.0, "idle_us": 0.0}
        d = state_acc.get((core, wid), {"active_us": 0.0, "stall_us": 0.0, "idle_us": 0.0})
        aggregate_state_acc[wid]["active_us"] += float(d["active_us"])
        aggregate_state_acc[wid]["stall_us"] += float(d["stall_us"])
        aggregate_state_acc[wid]["idle_us"] += float(d["idle_us"])
        aggregate_resident_acc[wid] = aggregate_resident_acc.get(wid, 0.0) + float(resident_us)
        if resident_us > 0:
            aggregate_resident_cores[wid] = aggregate_resident_cores.get(wid, 0) + 1
        if work_enabled:
            aggregate_work_acc[wid] = aggregate_work_acc.get(wid, 0.0) + float(work_acc.get((core, wid), 0.0))

    aggregate_records = []
    for wid in all_window_ids:
        w_start = wid * window_us
        w_end = (wid + 1) * window_us
        resident_us = float(aggregate_resident_acc.get(wid, 0.0))
        is_resident_window = 1 if resident_us > 0 else 0
        resident_cores = int(aggregate_resident_cores.get(wid, 0))

        d = aggregate_state_acc.get(wid, {"active_us": 0.0, "stall_us": 0.0, "idle_us": 0.0})
        active = float(d["active_us"])
        stall = float(d["stall_us"])
        idle = float(d["idle_us"])
        work_done = float(aggregate_work_acc.get(wid, 0.0)) if work_enabled else float("nan")

        observed_work_rate = float("nan")
        if resident_us > 0:
            denom = resident_us
            total = active + stall + idle
            if total < denom:
                idle += (denom - total)
                total = denom

            active_f = active / total
            stall_f = stall / total
            idle_f = idle / total

            sit_window_active = float("nan")
            sit_global_active = float("nan")
            if work_enabled:
                observed_work_rate = work_done / denom
            if work_enabled and args.expected_work_rate is not None and args.expected_work_rate > 0:
                sit_raw = (work_done / denom) / float(args.expected_work_rate)
                if not math.isfinite(sit_raw) or (sit_raw <= 0.0 and active > 0.0):
                    sit_raw = active_f
            elif not work_enabled:
                sit_window_active = active_f
                sit_global_active = global_sit_fallback
                if args.no_work_sit_mode == "global_active":
                    sit_raw = sit_global_active
                else:
                    sit_raw = sit_window_active
            else:
                sit_raw = active_f
            sit = max(0.0, min(1.0, sit_raw))
        else:
            active_f = float("nan")
            stall_f = float("nan")
            idle_f = float("nan")
            sit_raw = float("nan")
            sit = float("nan")
            sit_window_active = float("nan")
            sit_global_active = float("nan")

        aggregate_records.append({
            "window_id": wid,
            "window_start_us": w_start,
            "window_end_us": w_end,
            "resident_us": resident_us,
            "resident_core_equiv": (resident_us / window_us) if window_us > 0 else float("nan"),
            "resident_cores": resident_cores,
            "resident_frac_of_capacity": (
                resident_us / (window_us * float(total_cores))
            ) if window_us > 0 and total_cores > 0 else float("nan"),
            "is_resident_window": is_resident_window,
            "active_frac": active_f,
            "stall_frac": stall_f,
            "idle_frac": idle_f,
            "work_done": work_done,
            "observed_flops": work_done,
            "observed_work_rate": observed_work_rate,
            "observed_flops_per_us": observed_work_rate,
            "sit_no_work_window_active": sit_window_active,
            "sit_no_work_global_active": sit_global_active,
            "sit": sit,
        })

    aggregate_cols = [
        "window_id", "window_start_us", "window_end_us",
        "resident_us", "resident_core_equiv", "resident_cores",
        "resident_frac_of_capacity", "is_resident_window",
        "active_frac", "stall_frac", "idle_frac",
        "work_done", "observed_flops", "observed_work_rate", "observed_flops_per_us",
        "sit_no_work_window_active", "sit_no_work_global_active",
        "sit",
    ]
    aggregate_out = pd.DataFrame.from_records(aggregate_records, columns=aggregate_cols)
    aggregate_out = aggregate_out.sort_values(["window_id"]).reset_index(drop=True)

    # Summary uses only resident windows
    resident_out = out[out["is_resident_window"] == 1].copy()
    sits = resident_out["sit"].dropna().astype(float).tolist()
    aggregate_resident_out = aggregate_out[aggregate_out["is_resident_window"] == 1].copy()
    aggregate_sits = aggregate_resident_out["sit"].dropna().astype(float).tolist()

    per_core_sit_median = float(np.median(np.array(sits, dtype=float))) if sits else float("nan")
    per_core_sit_p95 = percentile(sits, 95)
    per_core_idle_avg = float(resident_out["idle_frac"].mean()) if len(resident_out) else float("nan")
    per_core_stall_avg = float(resident_out["stall_frac"].mean()) if len(resident_out) else float("nan")
    per_core_active_avg = float(resident_out["active_frac"].mean()) if len(resident_out) else float("nan")
    per_core_observed_rates = resident_out["observed_work_rate"].dropna().astype(float).tolist()
    per_core_observed_rate_median = float(np.median(np.array(per_core_observed_rates, dtype=float))) if per_core_observed_rates else float("nan")
    per_core_observed_rate_p95 = percentile(per_core_observed_rates, 95)

    overall_sit_median = float(np.median(np.array(aggregate_sits, dtype=float))) if aggregate_sits else float("nan")
    overall_sit_p95 = percentile(aggregate_sits, 95)
    overall_idle_avg = float(aggregate_resident_out["idle_frac"].mean()) if len(aggregate_resident_out) else float("nan")
    overall_stall_avg = float(aggregate_resident_out["stall_frac"].mean()) if len(aggregate_resident_out) else float("nan")
    overall_active_avg = float(aggregate_resident_out["active_frac"].mean()) if len(aggregate_resident_out) else float("nan")
    overall_observed_rates = aggregate_resident_out["observed_work_rate"].dropna().astype(float).tolist()
    overall_observed_rate_median = float(np.median(np.array(overall_observed_rates, dtype=float))) if overall_observed_rates else float("nan")
    overall_observed_rate_p95 = percentile(overall_observed_rates, 95)
    observed_work_total = float(np.nansum([work_acc.get(k, 0.0) for k in work_acc])) if work_enabled else float("nan")
    observed_work_rate_overall = (observed_work_total / total_resident_us) if work_enabled and total_resident_us > 0 else float("nan")

    summary = {
        "schema_version": 1,
        "window_us": window_us,
        "windows_total": int(len(out)),
        "resident_windows_total": int(len(resident_out)),
        "cores": cores_present,
        "sit_summary_basis": "per_core_window",
        "sit_median": per_core_sit_median,
        "sit_p95": per_core_sit_p95,
        "observed_flops_per_us_median": per_core_observed_rate_median,
        "observed_flops_per_us_p95": per_core_observed_rate_p95,
        "observed_work_rate_median": per_core_observed_rate_median,
        "observed_work_rate_p95": per_core_observed_rate_p95,
        "residency_idle_avg": per_core_idle_avg,
        "residency_stall_avg": per_core_stall_avg,
        "residency_active_avg": per_core_active_avg,
        "aggregate_windows_total": int(len(aggregate_out)),
        "aggregate_resident_windows_total": int(len(aggregate_resident_out)),
        "overall_window_sit_median": overall_sit_median,
        "overall_window_sit_p95": overall_sit_p95,
        "overall_window_observed_flops_per_us_median": overall_observed_rate_median,
        "overall_window_observed_flops_per_us_p95": overall_observed_rate_p95,
        "overall_window_observed_work_rate_median": overall_observed_rate_median,
        "overall_window_observed_work_rate_p95": overall_observed_rate_p95,
        "overall_window_residency_idle_avg": overall_idle_avg,
        "overall_window_residency_stall_avg": overall_stall_avg,
        "overall_window_residency_active_avg": overall_active_avg,
        "observed_flops_total": observed_work_total,
        "overall_observed_flops_per_us": observed_work_rate_overall,
        "observed_work_total": observed_work_total,
        "overall_observed_work_rate": observed_work_rate_overall,
        "used_residency_file": bool(args.residency is not None),
        "expected_work_rate": float(args.expected_work_rate) if args.expected_work_rate is not None else float("nan"),
        "work_done_present": bool(work_enabled),
        "no_work_sit_mode": str(args.no_work_sit_mode),
        "no_work_global_active_sit": float(global_sit_fallback) if not math.isnan(global_sit_fallback) else float("nan"),
    }

    csv_path = f"{args.out_prefix}_windows.csv"
    aggregate_csv_path = f"{args.out_prefix}_aggregate_windows.csv"
    json_path = f"{args.out_prefix}_summary.json"
    out.to_csv(csv_path, index=False)
    aggregate_out.to_csv(aggregate_csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("✓ windows written:", csv_path)
    print("✓ aggregate windows written:", aggregate_csv_path)
    print("✓ summary written:", json_path)
    if args.debug_sit:
        total_us = total_active_us + total_stall_us + total_idle_us
        print("---- debug sit ----")
        print(f"total_us={total_us:.3f} resident_us={total_resident_us:.3f} idle_us={total_idle_us:.3f} stall_us={total_stall_us:.3f}")
        print(f"windows_total={len(out)} windows_good={len(resident_out)}")
        if work_enabled:
            print(f"work_done={float(np.nansum([work_acc.get(k, 0.0) for k in work_acc])):.3f}")
        else:
            print("work_done=nan")
            if not math.isnan(global_sit_fallback):
                print(f"no_work_global_active_sit={global_sit_fallback:.6f}")
            print(f"no_work_sit_mode={args.no_work_sit_mode}")
        if args.expected_work_rate is not None:
            print(f"expected_work_rate={float(args.expected_work_rate):.6f}")
        else:
            print("expected_work_rate=nan")
        if debug_sit_raw:
            print(f"sit_raw min/mean/max={np.min(debug_sit_raw):.6f}/{np.mean(debug_sit_raw):.6f}/{np.max(debug_sit_raw):.6f}")
        if debug_sit_clamped:
            print(f"sit_clamped min/mean/max={np.min(debug_sit_clamped):.6f}/{np.mean(debug_sit_clamped):.6f}/{np.max(debug_sit_clamped):.6f}")


if __name__ == "__main__":
    main()
