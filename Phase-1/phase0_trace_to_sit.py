"""Convert Phase-0 Tenstorrent profiler traces into Phase-1 SIT inputs."""

from __future__ import annotations

import argparse
import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


HEADER_FREQ_RE = re.compile(r"CHIP_FREQ\[MHz\]:\s*(\d+)")
DEFAULT_ACTIVE_TOKENS = ("KERNEL", "THROUGHPUT_SECTION", "COMPUTE", "MATMUL")
DEFAULT_IDLE_TOKENS = ("IDLE", "FW")


@dataclass(frozen=True)
class TTEvent:
    core_x: int
    core_y: int
    processor: str
    time_cycles: int
    zone_name: str
    event_type: str


def parse_trace_csv(trace_csv: str | Path) -> Iterable[dict[str, str]]:
    """Legacy parser: return CSV rows after skipping metadata header lines."""
    trace_csv = Path(trace_csv)
    header_found = False
    remaining_lines: List[str] = []

    with trace_csv.open("r", newline="") as handle:
        for line in handle:
            if not header_found:
                if "core_x" in line and "core_y" in line:
                    header_found = True
                    remaining_lines.append(line)
                continue
            remaining_lines.append(line)

    if not header_found:
        raise ValueError(
            f"Unable to find a valid header containing 'core_x' and 'core_y' in {trace_csv}."
        )

    return list(csv.DictReader(io.StringIO("".join(remaining_lines))))


def _parse_freq_mhz(first_line: str) -> Optional[int]:
    m = HEADER_FREQ_RE.search(first_line)
    if not m:
        return None
    return int(m.group(1))


def parse_phase0_events(trace_csv: Path, max_events: Optional[int] = None) -> Tuple[int, List[TTEvent]]:
    """Parse Tenstorrent profile_log_device.csv into typed events."""
    events: List[TTEvent] = []
    with trace_csv.open("r", newline="") as handle:
        first_line = handle.readline()
        freq_mhz = _parse_freq_mhz(first_line) or 1000

        reader = csv.DictReader(handle)
        for raw_row in reader:
            row = {str(k).strip(): str(v).strip() for k, v in raw_row.items() if k is not None}
            try:
                event_type = row.get("type", "")
                if event_type not in {"ZONE_START", "ZONE_END"}:
                    continue
                events.append(
                    TTEvent(
                        core_x=int(row["core_x"]),
                        core_y=int(row["core_y"]),
                        processor=row.get("RISC processor type", "UNKNOWN"),
                        time_cycles=int(row["time[cycles since reset]"]),
                        zone_name=row.get("zone name", ""),
                        event_type=event_type,
                    )
                )
            except (KeyError, ValueError):
                # Skip malformed rows; this converter is best-effort and deterministic.
                continue
            if max_events is not None and len(events) >= max_events:
                break

    if not events:
        raise ValueError(f"No valid ZONE_START/ZONE_END events found in {trace_csv}")
    return freq_mhz, events


def _classify_zone(zone_name: str, active_tokens: Sequence[str], idle_tokens: Sequence[str]) -> str:
    z = zone_name.upper()
    if any(tok in z for tok in active_tokens):
        return "active"
    if any(tok in z for tok in idle_tokens):
        return "idle"
    return "stall"


def _state_from_counts(counts: Dict[str, int]) -> str:
    if counts["active"] > 0:
        return "active"
    if counts["stall"] > 0:
        return "stall"
    if counts["idle"] > 0:
        return "idle"
    return "idle"


def _merge_adjacent_state_rows(rows: List[dict]) -> List[dict]:
    if not rows:
        return []
    rows = sorted(rows, key=lambda r: (int(r["core"]), float(r["start_us"]), float(r["end_us"])))
    out: List[dict] = [rows[0].copy()]
    tol = 1e-9
    for row in rows[1:]:
        prev = out[-1]
        same_core = int(prev["core"]) == int(row["core"])
        same_state = str(prev["state"]) == str(row["state"])
        touching = abs(float(prev["end_us"]) - float(row["start_us"])) <= tol
        if same_core and same_state and touching:
            prev["end_us"] = float(row["end_us"])
            prev["duration_us"] = float(prev["end_us"]) - float(prev["start_us"])
        else:
            out.append(row.copy())
    return out


def build_zone_mapping_dataframe(
    events: Sequence[TTEvent],
    active_tokens: Sequence[str] = DEFAULT_ACTIVE_TOKENS,
    idle_tokens: Sequence[str] = DEFAULT_IDLE_TOKENS,
) -> pd.DataFrame:
    """Build explicit zone_name -> SIT state mapping from observed trace zones."""
    zone_names = sorted({ev.zone_name for ev in events if str(ev.zone_name).strip()}, key=lambda z: z.upper())
    rows = [{"zone_name": z, "state": _classify_zone(z, active_tokens, idle_tokens)} for z in zone_names]
    return pd.DataFrame.from_records(rows, columns=["zone_name", "state"])


def build_state_dataframe(
    events: Sequence[TTEvent],
    freq_mhz: int,
    core_granularity: str = "xy",
    max_cores: Optional[int] = 4,
    active_tokens: Sequence[str] = DEFAULT_ACTIVE_TOKENS,
    idle_tokens: Sequence[str] = DEFAULT_IDLE_TOKENS,
) -> pd.DataFrame:
    """Build normalized state intervals: start_us,end_us,duration_us,core,state."""
    grouped: Dict[Tuple, List[TTEvent]] = {}
    for ev in events:
        key = (ev.core_x, ev.core_y) if core_granularity == "xy" else (ev.core_x, ev.core_y, ev.processor)
        grouped.setdefault(key, []).append(ev)

    keys = sorted(grouped.keys())
    if max_cores is not None:
        keys = keys[: max(0, int(max_cores))]
    core_map = {k: i for i, k in enumerate(keys)}

    interval_rows_cycles: List[Tuple[int, int, int, str]] = []
    for key in keys:
        evs = sorted(
            grouped[key],
            key=lambda e: (e.time_cycles, 0 if e.event_type == "ZONE_END" else 1, e.zone_name),
        )
        if not evs:
            continue

        counts = {"active": 0, "stall": 0, "idle": 0}
        current_state = "idle"
        prev_t = evs[0].time_cycles
        core_id = core_map[key]

        for ev in evs:
            t = ev.time_cycles
            if t > prev_t:
                interval_rows_cycles.append((core_id, prev_t, t, current_state))

            zone_state = _classify_zone(ev.zone_name, active_tokens, idle_tokens)
            if ev.event_type == "ZONE_START":
                counts[zone_state] += 1
            else:
                counts[zone_state] = max(0, counts[zone_state] - 1)
            current_state = _state_from_counts(counts)
            prev_t = t

    if not interval_rows_cycles:
        raise ValueError("No state intervals could be produced from input events.")

    t0 = min(s for _, s, _, _ in interval_rows_cycles)
    rows_us: List[dict] = []
    for core, s, e, state in interval_rows_cycles:
        start_us = (float(s - t0) / float(freq_mhz))
        end_us = (float(e - t0) / float(freq_mhz))
        if end_us <= start_us:
            continue
        rows_us.append(
            {
                "start_us": start_us,
                "end_us": end_us,
                "duration_us": end_us - start_us,
                "core": int(core),
                "state": state,
            }
        )

    rows_us = _merge_adjacent_state_rows(rows_us)
    return pd.DataFrame.from_records(rows_us, columns=["start_us", "end_us", "duration_us", "core", "state"])


def _merge_intervals(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: (x[0], x[1]))
    out: List[Tuple[float, float]] = []
    cs, ce = intervals[0]
    for s, e in intervals[1:]:
        if s <= ce + 1e-9:
            ce = max(ce, e)
        else:
            out.append((cs, ce))
            cs, ce = s, e
    out.append((cs, ce))
    return out


def build_residency_dataframe(state_df: pd.DataFrame, residency_from_state: str = "nonidle") -> Optional[pd.DataFrame]:
    """Build residency intervals from state intervals."""
    if residency_from_state == "none":
        return None
    if residency_from_state == "active":
        keep = {"active"}
    else:  # nonidle
        keep = {"active", "stall"}

    rows: List[dict] = []
    for core in sorted(state_df["core"].unique().tolist()):
        sdf = state_df[(state_df["core"] == core) & (state_df["state"].isin(list(keep)))]
        intervals = [(float(r.start_us), float(r.end_us)) for r in sdf.itertuples(index=False)]
        for s, e in _merge_intervals(intervals):
            if e > s:
                rows.append({"start_us": s, "end_us": e, "core": int(core), "resident": 1})
    if not rows:
        return None
    return pd.DataFrame.from_records(rows, columns=["start_us", "end_us", "core", "resident"])


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert Phase-0 Tenstorrent profiler CSV to Phase-1 SIT inputs.")
    ap.add_argument("--trace-csv", required=True, help="Path to profile_log_device.csv")
    ap.add_argument("--out-trace", required=True, help="Output normalized state_intervals.csv")
    ap.add_argument("--out-zone-map", default=None, help="Optional output zone_to_state.csv")
    ap.add_argument("--out-residency", default=None, help="Optional output residency_intervals.csv")
    ap.add_argument("--core-granularity", choices=["xy", "xyproc"], default="xy")
    ap.add_argument("--residency-from-state", choices=["nonidle", "active", "none"], default="nonidle")
    ap.add_argument("--max-events", type=int, default=None)
    ap.add_argument("--max-cores", type=int, default=4)
    ap.add_argument("--chip-freq-mhz", type=int, default=None, help="Override header frequency")
    args = ap.parse_args()

    trace_csv = Path(args.trace_csv)
    out_trace = Path(args.out_trace)
    out_trace.parent.mkdir(parents=True, exist_ok=True)

    freq_mhz, events = parse_phase0_events(trace_csv, max_events=args.max_events)
    if args.chip_freq_mhz is not None:
        freq_mhz = int(args.chip_freq_mhz)

    if args.out_zone_map is not None:
        out_zone_map = Path(args.out_zone_map)
        out_zone_map.parent.mkdir(parents=True, exist_ok=True)
        zone_df = build_zone_mapping_dataframe(events=events)
        zone_df.to_csv(out_zone_map, index=False)
        print(f"wrote zone mapping: {out_zone_map} ({len(zone_df)} rows)")

    state_df = build_state_dataframe(
        events=events,
        freq_mhz=freq_mhz,
        core_granularity=args.core_granularity,
        max_cores=args.max_cores,
    )
    state_df.to_csv(out_trace, index=False)
    print(f"wrote state intervals: {out_trace} ({len(state_df)} rows)")
    print(f"detected freq_mhz: {freq_mhz}")

    if args.out_residency is not None:
        out_resid = Path(args.out_residency)
        out_resid.parent.mkdir(parents=True, exist_ok=True)
        resid_df = build_residency_dataframe(state_df, residency_from_state=args.residency_from_state)
        if resid_df is None:
            print("no residency intervals produced")
        else:
            resid_df.to_csv(out_resid, index=False)
            print(f"wrote residency intervals: {out_resid} ({len(resid_df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
