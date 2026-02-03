#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd

from adapters.baseline_adapter import BaselineAdapter

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

    # Union of keys to output
    all_keys = set(state_acc.keys())
    if residency_by_core is not None:
        all_keys |= set(resident_acc.keys())

    records = []
    for (core, wid) in sorted(all_keys, key=lambda x: (x[0], x[1])):
        w_start = wid * window_us
        w_end = (wid + 1) * window_us

        resident_us = window_us if residency_by_core is None else resident_acc.get((core, wid), 0.0)
        is_resident_window = 1 if resident_us > 0 else 0

        d = state_acc.get((core, wid), {"active_us": 0.0, "stall_us": 0.0, "idle_us": 0.0})
        active = float(d["active_us"])
        stall = float(d["stall_us"])
        idle = float(d["idle_us"])

        if resident_us > 0:
            denom = resident_us  # normalize by resident time
            total = active + stall + idle
            if total < denom:
                idle += (denom - total)  # gap-fill inside residency
                total = denom

            active_f = active / total
            stall_f = stall / total
            idle_f = idle / total

            sit = active_f  # toy SIT
            sit = max(0.0, min(1.0, sit))
        else:
            active_f = float("nan")
            stall_f = float("nan")
            idle_f = float("nan")
            sit = float("nan")

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
            "sit": sit,
        })

    out = pd.DataFrame.from_records(records).sort_values(["core", "window_id"]).reset_index(drop=True)

    # Summary uses only resident windows
    resident_out = out[out["is_resident_window"] == 1].copy()
    sits = resident_out["sit"].dropna().astype(float).tolist()

    summary = {
        "schema_version": 1,
        "window_us": window_us,
        "windows_total": int(len(out)),
        "resident_windows_total": int(len(resident_out)),
        "cores": sorted(out["core"].unique().tolist()) if len(out) else [],
        "sit_median": float(np.median(np.array(sits, dtype=float))) if sits else float("nan"),
        "sit_p95": percentile(sits, 95),
        "residency_idle_avg": float(resident_out["idle_frac"].mean()) if len(resident_out) else float("nan"),
        "residency_stall_avg": float(resident_out["stall_frac"].mean()) if len(resident_out) else float("nan"),
        "residency_active_avg": float(resident_out["active_frac"].mean()) if len(resident_out) else float("nan"),
        "used_residency_file": bool(args.residency is not None),
    }

    csv_path = f"{args.out_prefix}_windows.csv"
    json_path = f"{args.out_prefix}_summary.json"
    out.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("✓ windows written:", csv_path)
    print("✓ summary written:", json_path)


if __name__ == "__main__":
    main()
