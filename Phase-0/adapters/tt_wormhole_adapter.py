from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE2_ROOT = REPO_ROOT / "Phase-2"
if str(PHASE2_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE2_ROOT))

from ingest.ingest_api import validate_resid_df, validate_state_df

HEADER_FREQ_RE = re.compile(r"CHIP_FREQ\[MHz\]:\s*(\d+)")
PRAGMA_RE = re.compile(r"#pragma message:\s*([^,]+),([^,]+),(\d+),KERNEL_PROFILER'")

STATE_PRIORITY = {"IDLE": 1, "STALL": 2, "ACTIVE": 3}
ORIGIN_PRIORITY = {
    "unknown": 0,
    "runtime": 1,
    "cb_compute": 2,
    "trisc_kernel_base": 3,
    "fallback_trisc_kernel": 4,
    "derived_from_cb": 5,
    "explicit_throughput": 6,
}


@dataclass(frozen=True)
class TTWormholeParseConfig:
    output_mode: str = "tile"  # tile (engine-facing default) | lane (debug)
    normalize_zero: bool = True
    strict_pairing: bool = False
    strict_map_hit: bool = False
    chip_freq_mhz_override: Optional[int] = None
    residency_model: str = "kernel_envelope"  # kernel_envelope | active_span
    ops_per_zone: Optional[float] = None


@dataclass(frozen=True)
class TraceEvent:
    row_idx: int
    pcie_slot: int
    core_x: int
    core_y: int
    risc_type: str
    timer_id: int
    time_cycle: int
    zone_name: str
    event_type: str
    source_line: int
    source_file: str
    map_hit: bool

    @property
    def lane(self) -> Tuple[int, int, int, str]:
        return (self.pcie_slot, self.core_x, self.core_y, self.risc_type)


@dataclass(frozen=True)
class ZoneInterval:
    pcie_slot: int
    core_x: int
    core_y: int
    risc_type: str
    timer_id: int
    start_cycle: int
    end_cycle: int
    zone_name: str
    source_line: int
    source_file: str
    map_hit: bool

    @property
    def lane(self) -> Tuple[int, int, int, str]:
        return (self.pcie_slot, self.core_x, self.core_y, self.risc_type)


@dataclass(frozen=True)
class StateCandidate:
    lane: Tuple[int, int, int, str]
    pcie_slot: int
    core_x: int
    core_y: int
    risc_type: str
    start_cycle: int
    end_cycle: int
    state: str  # ACTIVE | STALL | IDLE
    zone_name: str
    source_file: str
    source_line: int
    origin: str
    map_hit: bool
    work_done: float = 0.0


@dataclass(frozen=True)
class FlattenedInterval:
    lane: Tuple[int, int, int, str]
    pcie_slot: int
    core_x: int
    core_y: int
    risc_type: str
    start_cycle: int
    end_cycle: int
    state: str
    zone_name: str
    source_file: str
    source_line: int
    origin: str
    map_hit: bool
    core_id: str
    work_done: float = 0.0


def _event_order(event_type: str) -> int:
    # Same-cycle tie-break: close an interval before opening a new one.
    if event_type == "ZONE_END":
        return 0
    if event_type == "ZONE_START":
        return 1
    return 2


def _base_state(zone_name: str) -> str:
    if zone_name.endswith("-FW"):
        return "IDLE"
    if zone_name in {"BRISC-KERNEL", "NCRISC-KERNEL"}:
        return "STALL"
    if zone_name == "TRISC-KERNEL":
        return "STALL"
    if zone_name.startswith("CB-COMPUTE-"):
        return "ACTIVE"
    if _is_explicit_throughput_zone(zone_name):
        return "ACTIVE"
    return "STALL"


def _is_explicit_throughput_zone(zone_name: str) -> bool:
    zn = zone_name.upper()
    return "THROUGHPUT_SECTION" in zn or "THROUGHPUT-SECTION" in zn


def _is_kernel_zone(zone_name: str) -> bool:
    return zone_name.endswith("-KERNEL")


def _merge_segments(segments: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    clean = sorted((int(s), int(e)) for s, e in segments if int(e) > int(s))
    if not clean:
        return []
    out: List[Tuple[int, int]] = []
    cs, ce = clean[0]
    for s, e in clean[1:]:
        if s <= ce:
            ce = max(ce, e)
        else:
            out.append((cs, ce))
            cs, ce = s, e
    out.append((cs, ce))
    return out


def _intersect_with_segments(start: int, end: int, segments: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    if end <= start:
        return out
    for s, e in segments:
        if e <= start:
            continue
        if s >= end:
            break
        a = max(start, s)
        b = min(end, e)
        if b > a:
            out.append((a, b))
    return out


class TTWormholePlatformAdapter:
    """
    Tenstorrent Wormhole adapter:
    - Parses profile_log_device.csv + zone_src_locations log
    - Emits normalized state/residency intervals for Phase-2 ingest contract
    - Applies TRISC compute-envelope policy:
      explicit throughput > derived CB span > fallback full TRISC-KERNEL ACTIVE
    - Derives residency as a workload-owned outer kernel envelope per exported core
      (resident may contain ACTIVE/STALL/IDLE)
    """

    def __init__(self, profile_csv: str, zone_log: str, cfg: Optional[TTWormholeParseConfig] = None):
        self.profile_csv = str(profile_csv)
        self.zone_log = str(zone_log)
        self.cfg = cfg or TTWormholeParseConfig()

        self._chip_freq_mhz, self._events = self._parse_profile_events()
        self._zone_map = self._parse_zone_map()
        self._events = self._events_with_map()
        self._map_hit_count = sum(1 for e in self._events if e.map_hit)
        self._intervals, self._anomalies = self._pair_intervals()
        if self.cfg.strict_pairing and self._anomalies:
            raise ValueError(f"Pairing anomalies detected in strict mode: {self._anomalies[:10]}")
        if self.cfg.strict_map_hit and any(not e.map_hit for e in self._events):
            raise ValueError("Found profile events missing zone-map tuple in strict_map_hit mode.")

        self._state_df_cache: Optional[pd.DataFrame] = None
        self._resid_df_cache: Optional[pd.DataFrame] = None

    def _parse_zone_map(self) -> Dict[Tuple[str, str, int], Dict[str, object]]:
        out: Dict[Tuple[str, str, int], Dict[str, object]] = {}
        with open(self.zone_log, "r", encoding="utf-8", errors="ignore") as handle:
            for line_no, line in enumerate(handle, start=1):
                m = PRAGMA_RE.search(line.strip())
                if not m:
                    continue
                zone_name = m.group(1).strip()
                source_file = m.group(2).strip()
                source_line = int(m.group(3).strip())
                key = (zone_name, source_file, source_line)
                if key not in out:
                    out[key] = {"line_nos": [line_no]}
                else:
                    out[key]["line_nos"].append(line_no)
        return out

    def _parse_profile_events(self) -> Tuple[int, List[TraceEvent]]:
        profile_path = Path(self.profile_csv)
        with profile_path.open("r", newline="", encoding="utf-8", errors="ignore") as handle:
            first = handle.readline().strip()
            freq = self.cfg.chip_freq_mhz_override
            if freq is None:
                m = HEADER_FREQ_RE.search(first)
                if not m:
                    raise ValueError(
                        f"Unable to parse CHIP_FREQ[MHz] from header of {profile_path}; use --chip-freq-mhz."
                    )
                freq = int(m.group(1))
            header_line = handle.readline().strip()
            header = [h.strip() for h in csv.reader([header_line]).__next__()]
            raw = list(csv.DictReader(handle, fieldnames=header, skipinitialspace=True))

        events: List[TraceEvent] = []
        for idx, row in enumerate(raw, start=3):
            if not row or not row.get("PCIe slot"):
                continue
            zone_name = (row.get("zone name") or "").strip()
            source_file = (row.get("source file") or "").strip()
            source_line_raw = (row.get("source line") or "").strip()
            event_type = (row.get("type") or "").strip()
            if event_type not in {"ZONE_START", "ZONE_END"}:
                continue
            try:
                source_line = int(source_line_raw)
            except ValueError:
                continue
            events.append(
                TraceEvent(
                    row_idx=idx,
                    pcie_slot=int((row.get("PCIe slot") or "0").strip()),
                    core_x=int((row.get("core_x") or "0").strip()),
                    core_y=int((row.get("core_y") or "0").strip()),
                    risc_type=(row.get("RISC processor type") or "").strip(),
                    timer_id=int((row.get("timer_id") or "0").strip()),
                    time_cycle=int((row.get("time[cycles since reset]") or "0").strip()),
                    zone_name=zone_name,
                    event_type=event_type,
                    source_line=source_line,
                    source_file=source_file,
                    map_hit=False,  # patched below after zone-map parse
                )
            )

        # map_hit depends on parsed zone map, so patch in ctor after both are parsed.
        # Here keep a temporary list with map_hit False.
        return int(freq), events

    def _events_with_map(self) -> List[TraceEvent]:
        out: List[TraceEvent] = []
        for e in self._events:
            key = (e.zone_name, e.source_file, e.source_line)
            out.append(
                TraceEvent(
                    row_idx=e.row_idx,
                    pcie_slot=e.pcie_slot,
                    core_x=e.core_x,
                    core_y=e.core_y,
                    risc_type=e.risc_type,
                    timer_id=e.timer_id,
                    time_cycle=e.time_cycle,
                    zone_name=e.zone_name,
                    event_type=e.event_type,
                    source_line=e.source_line,
                    source_file=e.source_file,
                    map_hit=(key in self._zone_map),
                )
            )
        return out

    def _pair_intervals(self) -> Tuple[List[ZoneInterval], List[dict]]:
        events = self._events
        anomalies: List[dict] = []
        by_lane: Dict[Tuple[int, int, int, str], List[TraceEvent]] = {}
        for e in events:
            by_lane.setdefault(e.lane, []).append(e)

        intervals: List[ZoneInterval] = []
        for lane, lane_events in by_lane.items():
            lane_events = sorted(lane_events, key=lambda r: (r.time_cycle, _event_order(r.event_type), r.row_idx))
            open_stack: Dict[Tuple[int, str, str, int], List[TraceEvent]] = {}
            for ev in lane_events:
                key = (ev.timer_id, ev.zone_name, ev.source_file, ev.source_line)
                if ev.event_type == "ZONE_START":
                    open_stack.setdefault(key, []).append(ev)
                    continue
                if ev.event_type == "ZONE_END":
                    if not open_stack.get(key):
                        anomalies.append(
                            {
                                "type": "unmatched_end",
                                "lane": lane,
                                "row_idx": ev.row_idx,
                                "zone_name": ev.zone_name,
                            }
                        )
                        continue
                    st = open_stack[key].pop()
                    if ev.time_cycle <= st.time_cycle:
                        anomalies.append(
                            {
                                "type": "non_positive_interval",
                                "lane": lane,
                                "start_row": st.row_idx,
                                "end_row": ev.row_idx,
                                "zone_name": ev.zone_name,
                            }
                        )
                        continue
                    intervals.append(
                        ZoneInterval(
                            pcie_slot=ev.pcie_slot,
                            core_x=ev.core_x,
                            core_y=ev.core_y,
                            risc_type=ev.risc_type,
                            timer_id=ev.timer_id,
                            start_cycle=st.time_cycle,
                            end_cycle=ev.time_cycle,
                            zone_name=ev.zone_name,
                            source_line=ev.source_line,
                            source_file=ev.source_file,
                            map_hit=(st.map_hit and ev.map_hit),
                        )
                    )

            for k, starts in open_stack.items():
                if not starts:
                    continue
                for st in starts:
                    anomalies.append(
                        {
                            "type": "unmatched_start",
                            "lane": lane,
                            "row_idx": st.row_idx,
                            "zone_name": st.zone_name,
                        }
                    )
        return intervals, anomalies

    def _nested_inside(self, envelope: ZoneInterval, pool: Sequence[ZoneInterval], predicate) -> List[ZoneInterval]:
        out: List[ZoneInterval] = []
        for iv in pool:
            if iv.lane != envelope.lane:
                continue
            if iv.start_cycle < envelope.start_cycle or iv.end_cycle > envelope.end_cycle:
                continue
            if not predicate(iv):
                continue
            out.append(iv)
        return out

    def _trisc_active_spans(self, tk: ZoneInterval, lane_intervals: Sequence[ZoneInterval]) -> List[Tuple[int, int, str, float]]:
        explicit = self._nested_inside(tk, lane_intervals, lambda z: _is_explicit_throughput_zone(z.zone_name))
        if explicit:
            merged = _merge_segments([(z.start_cycle, z.end_cycle) for z in explicit])
            out: List[Tuple[int, int, str, float]] = []
            for s, e in merged:
                count = sum(1 for z in explicit if z.end_cycle > s and z.start_cycle < e)
                work_done = float(self.cfg.ops_per_zone or 0.0) * float(count)
                out.append((s, e, "explicit_throughput", work_done))
            return out

        cb = self._nested_inside(tk, lane_intervals, lambda z: z.zone_name.startswith("CB-COMPUTE-"))
        if cb:
            s = min(z.start_cycle for z in cb)
            e = max(z.end_cycle for z in cb)
            return [(s, e, "derived_from_cb", 0.0)]

        return [(tk.start_cycle, tk.end_cycle, "fallback_trisc_kernel", 0.0)]

    def _build_candidates(self) -> List[StateCandidate]:
        by_lane: Dict[Tuple[int, int, int, str], List[ZoneInterval]] = {}
        for iv in self._intervals:
            by_lane.setdefault(iv.lane, []).append(iv)

        cands: List[StateCandidate] = []
        for lane, lane_intervals in by_lane.items():
            for iv in lane_intervals:
                base = _base_state(iv.zone_name)
                origin = "trisc_kernel_base" if iv.zone_name == "TRISC-KERNEL" else (
                    "cb_compute" if iv.zone_name.startswith("CB-COMPUTE-") else "runtime"
                )
                cands.append(
                    StateCandidate(
                        lane=lane,
                        pcie_slot=iv.pcie_slot,
                        core_x=iv.core_x,
                        core_y=iv.core_y,
                        risc_type=iv.risc_type,
                        start_cycle=iv.start_cycle,
                        end_cycle=iv.end_cycle,
                        state=base,
                        zone_name=iv.zone_name,
                        source_file=iv.source_file,
                        source_line=iv.source_line,
                        origin=origin,
                        map_hit=iv.map_hit,
                        work_done=0.0,
                    )
                )

            trisc_kernels = [iv for iv in lane_intervals if iv.zone_name == "TRISC-KERNEL"]
            for tk in trisc_kernels:
                for s, e, origin, work_done in self._trisc_active_spans(tk, lane_intervals):
                    if e <= s:
                        continue
                    cands.append(
                        StateCandidate(
                            lane=lane,
                            pcie_slot=tk.pcie_slot,
                            core_x=tk.core_x,
                            core_y=tk.core_y,
                            risc_type=tk.risc_type,
                            start_cycle=s,
                            end_cycle=e,
                            state="ACTIVE",
                            zone_name="THROUGHPUT_SECTION",
                            source_file=tk.source_file,
                            source_line=tk.source_line,
                            origin=origin,
                            map_hit=tk.map_hit,
                            work_done=work_done,
                        )
                    )
        return cands

    def _flatten_lane_candidates(self, lane_cands: Sequence[StateCandidate]) -> List[FlattenedInterval]:
        points = sorted(
            {
                int(c.start_cycle)
                for c in lane_cands
            }
            | {
                int(c.end_cycle)
                for c in lane_cands
            }
        )
        out: List[FlattenedInterval] = []
        if len(points) < 2:
            return out

        lane = lane_cands[0].lane
        core_id = f"slot{lane[0]}_x{lane[1]}_y{lane[2]}_{lane[3]}"
        for i in range(len(points) - 1):
            a = points[i]
            b = points[i + 1]
            if b <= a:
                continue
            covering = [c for c in lane_cands if c.start_cycle < b and c.end_cycle > a]
            if not covering:
                continue
            chosen = max(
                covering,
                key=lambda c: (
                    STATE_PRIORITY.get(c.state, 0),
                    ORIGIN_PRIORITY.get(c.origin, 0),
                    c.start_cycle,
                    -c.end_cycle,
                ),
            )
            chosen_dur = max(1, int(chosen.end_cycle) - int(chosen.start_cycle))
            overlap_dur = max(0, int(b) - int(a))
            work_done = float(chosen.work_done) * (float(overlap_dur) / float(chosen_dur))
            out.append(
                FlattenedInterval(
                    lane=chosen.lane,
                    pcie_slot=chosen.pcie_slot,
                    core_x=chosen.core_x,
                    core_y=chosen.core_y,
                    risc_type=chosen.risc_type,
                    start_cycle=a,
                    end_cycle=b,
                    state=chosen.state,
                    zone_name=chosen.zone_name,
                    source_file=chosen.source_file,
                    source_line=chosen.source_line,
                    origin=chosen.origin,
                    map_hit=chosen.map_hit,
                    core_id=core_id,
                    work_done=work_done,
                )
            )

        if not out:
            return out

        merged: List[FlattenedInterval] = [out[0]]
        for cur in out[1:]:
            prev = merged[-1]
            if (
                cur.core_id == prev.core_id
                and cur.state == prev.state
                and cur.zone_name == prev.zone_name
                and cur.origin == prev.origin
                and cur.start_cycle == prev.end_cycle
            ):
                merged[-1] = FlattenedInterval(
                    lane=prev.lane,
                    pcie_slot=prev.pcie_slot,
                    core_x=prev.core_x,
                    core_y=prev.core_y,
                    risc_type=prev.risc_type,
                    start_cycle=prev.start_cycle,
                    end_cycle=cur.end_cycle,
                    state=prev.state,
                    zone_name=prev.zone_name,
                    source_file=prev.source_file,
                    source_line=prev.source_line,
                    origin=prev.origin,
                    map_hit=(prev.map_hit and cur.map_hit),
                    core_id=prev.core_id,
                    work_done=(prev.work_done + cur.work_done),
                )
            else:
                merged.append(cur)
        return merged

    def _fuse_tile_mode(self, intervals: Sequence[FlattenedInterval]) -> List[FlattenedInterval]:
        by_tile: Dict[Tuple[int, int, int], List[FlattenedInterval]] = {}
        for iv in intervals:
            tile = (iv.pcie_slot, iv.core_x, iv.core_y)
            by_tile.setdefault(tile, []).append(iv)

        fused: List[FlattenedInterval] = []
        for tile, tile_intervals in by_tile.items():
            points = sorted({iv.start_cycle for iv in tile_intervals} | {iv.end_cycle for iv in tile_intervals})
            if len(points) < 2:
                continue
            core_id = f"slot{tile[0]}_x{tile[1]}_y{tile[2]}"
            for i in range(len(points) - 1):
                a = points[i]
                b = points[i + 1]
                if b <= a:
                    continue
                covering = [iv for iv in tile_intervals if iv.start_cycle < b and iv.end_cycle > a]
                if not covering:
                    continue
                chosen = max(
                    covering,
                    key=lambda c: (
                        STATE_PRIORITY.get(c.state, 0),
                        ORIGIN_PRIORITY.get(c.origin, 0),
                    ),
                )
                work_done = sum(float(iv.work_done) for iv in covering if iv.state == "ACTIVE")
                fused.append(
                    FlattenedInterval(
                        lane=(tile[0], tile[1], tile[2], "TILE"),
                        pcie_slot=tile[0],
                        core_x=tile[1],
                        core_y=tile[2],
                        risc_type="TILE",
                        start_cycle=a,
                        end_cycle=b,
                        state=chosen.state,
                        zone_name=chosen.zone_name,
                        source_file=chosen.source_file,
                        source_line=chosen.source_line,
                        origin=f"tile_fused:{chosen.origin}",
                        map_hit=chosen.map_hit,
                        core_id=core_id,
                        work_done=work_done,
                    )
                )

        fused = sorted(fused, key=lambda x: (x.core_id, x.start_cycle))
        merged: List[FlattenedInterval] = []
        for cur in fused:
            if not merged:
                merged.append(cur)
                continue
            prev = merged[-1]
            if prev.core_id == cur.core_id and prev.state == cur.state and prev.end_cycle == cur.start_cycle:
                merged[-1] = FlattenedInterval(
                    lane=prev.lane,
                    pcie_slot=prev.pcie_slot,
                    core_x=prev.core_x,
                    core_y=prev.core_y,
                    risc_type=prev.risc_type,
                    start_cycle=prev.start_cycle,
                    end_cycle=cur.end_cycle,
                    state=prev.state,
                    zone_name=prev.zone_name,
                    source_file=prev.source_file,
                    source_line=prev.source_line,
                    origin=prev.origin,
                    map_hit=(prev.map_hit and cur.map_hit),
                    core_id=prev.core_id,
                    work_done=(prev.work_done + cur.work_done),
                )
            else:
                merged.append(cur)
        return merged

    def _build_flattened_intervals(self) -> List[FlattenedInterval]:
        cands = self._build_candidates()
        by_lane: Dict[Tuple[int, int, int, str], List[StateCandidate]] = {}
        for c in cands:
            by_lane.setdefault(c.lane, []).append(c)
        flattened: List[FlattenedInterval] = []
        for lane in sorted(by_lane.keys()):
            flattened.extend(self._flatten_lane_candidates(by_lane[lane]))
        flattened = sorted(flattened, key=lambda x: (x.core_id, x.start_cycle))
        if self.cfg.output_mode == "tile":
            flattened = self._fuse_tile_mode(flattened)
        return flattened

    def _output_core_id(self, pcie_slot: int, core_x: int, core_y: int, risc_type: str) -> str:
        if self.cfg.output_mode == "tile":
            return f"slot{pcie_slot}_x{core_x}_y{core_y}"
        return f"slot{pcie_slot}_x{core_x}_y{core_y}_{risc_type}"

    def _derive_kernel_envelopes(self, flattened: Sequence[FlattenedInterval]) -> Dict[str, List[Tuple[int, int]]]:
        """
        Derive workload-owned residency envelopes per exported core.
        Primary signal: runtime *-KERNEL intervals from raw paired zones.
        Fallback: full observed span of exported intervals for cores without kernel zones.
        """
        by_core_kernel: Dict[str, List[Tuple[int, int]]] = {}
        for iv in self._intervals:
            if not _is_kernel_zone(iv.zone_name):
                continue
            core_id = self._output_core_id(iv.pcie_slot, iv.core_x, iv.core_y, iv.risc_type)
            by_core_kernel.setdefault(core_id, []).append((iv.start_cycle, iv.end_cycle))

        envelopes: Dict[str, List[Tuple[int, int]]] = {}
        for core_id, segs in by_core_kernel.items():
            merged = _merge_segments(segs)
            if not merged:
                continue
            # Residency is the enclosing workload scope, not non-idle union.
            envelopes[core_id] = [(merged[0][0], merged[-1][1])]

        by_core_span: Dict[str, List[Tuple[int, int]]] = {}
        for iv in flattened:
            by_core_span.setdefault(iv.core_id, []).append((iv.start_cycle, iv.end_cycle))
        for core_id, segs in by_core_span.items():
            if core_id in envelopes:
                continue
            merged = _merge_segments(segs)
            if not merged:
                continue
            envelopes[core_id] = [(merged[0][0], merged[-1][1])]
        return envelopes

    def _derive_active_span_envelopes(self, flattened: Sequence[FlattenedInterval]) -> Dict[str, List[Tuple[int, int]]]:
        """
        Derive a compute-oriented residency model per exported core.
        When ACTIVE intervals exist, bound residency to the first/last ACTIVE span so
        long terminal kernel tails do not dominate no-work SIT summaries.
        """
        by_core_active: Dict[str, List[Tuple[int, int]]] = {}
        for iv in flattened:
            if iv.state != "ACTIVE":
                continue
            by_core_active.setdefault(iv.core_id, []).append((iv.start_cycle, iv.end_cycle))

        envelopes: Dict[str, List[Tuple[int, int]]] = {}
        for core_id, segs in by_core_active.items():
            merged = _merge_segments(segs)
            if not merged:
                continue
            envelopes[core_id] = [(merged[0][0], merged[-1][1])]
        return envelopes

    def _derive_residency_envelopes(self, flattened: Sequence[FlattenedInterval]) -> Dict[str, List[Tuple[int, int]]]:
        kernel_envelopes = self._derive_kernel_envelopes(flattened)
        if self.cfg.residency_model == "kernel_envelope":
            return kernel_envelopes
        if self.cfg.residency_model == "active_span":
            active_envelopes = self._derive_active_span_envelopes(flattened)
            out: Dict[str, List[Tuple[int, int]]] = {}
            all_core_ids = sorted(set(kernel_envelopes.keys()) | set(active_envelopes.keys()))
            for core_id in all_core_ids:
                if core_id in active_envelopes:
                    out[core_id] = active_envelopes[core_id]
                elif core_id in kernel_envelopes:
                    out[core_id] = kernel_envelopes[core_id]
            return out
        raise ValueError(f"Unknown residency model: {self.cfg.residency_model}")

    def _build_state_and_residency(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if self._state_df_cache is not None and self._resid_df_cache is not None:
            return self._state_df_cache.copy(), self._resid_df_cache.copy()

        flattened = self._build_flattened_intervals()
        if not flattened:
            state_empty = validate_state_df(pd.DataFrame(columns=["start_us", "end_us", "core", "state"]))
            resid_empty = validate_resid_df(pd.DataFrame(columns=["start_us", "end_us", "core", "resident"]))
            self._state_df_cache = state_empty
            self._resid_df_cache = resid_empty
            return state_empty.copy(), resid_empty.copy()

        residency_by_core = self._derive_residency_envelopes(flattened)

        clipped: List[FlattenedInterval] = []
        for iv in flattened:
            mask = residency_by_core.get(iv.core_id, [])
            if not mask:
                continue
            for s, e in _intersect_with_segments(iv.start_cycle, iv.end_cycle, mask):
                clipped.append(
                    FlattenedInterval(
                        lane=iv.lane,
                        pcie_slot=iv.pcie_slot,
                        core_x=iv.core_x,
                        core_y=iv.core_y,
                        risc_type=iv.risc_type,
                        start_cycle=s,
                        end_cycle=e,
                        state=iv.state,
                        zone_name=iv.zone_name,
                        source_file=iv.source_file,
                        source_line=iv.source_line,
                        origin=iv.origin,
                        map_hit=iv.map_hit,
                        core_id=iv.core_id,
                        work_done=(float(iv.work_done) * (float(e - s) / float(max(1, iv.end_cycle - iv.start_cycle)))),
                    )
                )

        all_core_ids = sorted(set(residency_by_core.keys()) | {iv.core_id for iv in clipped})
        core_map = {cid: i for i, cid in enumerate(all_core_ids)}
        if self.cfg.normalize_zero:
            t0_candidates: List[int] = []
            for core_id in all_core_ids:
                t0_candidates.extend([s for s, _ in residency_by_core.get(core_id, [])])
            for iv in clipped:
                t0_candidates.append(iv.start_cycle)
            t0 = min(t0_candidates) if t0_candidates else 0
        else:
            t0 = 0

        state_rows: List[Dict[str, object]] = []
        for iv in sorted(clipped, key=lambda x: (x.core_id, x.start_cycle, x.end_cycle)):
            row = {
                "start_us": (iv.start_cycle - t0) / float(self._chip_freq_mhz),
                "end_us": (iv.end_cycle - t0) / float(self._chip_freq_mhz),
                "core": core_map[iv.core_id],
                "state": iv.state.lower(),
                # debug lineage
                "start_cycle": iv.start_cycle,
                "end_cycle": iv.end_cycle,
                "core_id": iv.core_id,
                "pcie_slot": iv.pcie_slot,
                "core_x": iv.core_x,
                "core_y": iv.core_y,
                "risc_type": iv.risc_type,
                "zone_name": iv.zone_name,
                "source_file": iv.source_file,
                "source_line": iv.source_line,
                "origin": iv.origin,
                "map_hit": int(iv.map_hit),
            }
            if self.cfg.ops_per_zone is not None:
                row["work_done"] = float(iv.work_done)
            state_rows.append(row)
        state_df = pd.DataFrame(state_rows)
        if len(state_df) == 0:
            cols = ["start_us", "end_us", "core", "state"]
            if self.cfg.ops_per_zone is not None:
                cols.append("work_done")
            state_df = pd.DataFrame(columns=cols)
        state_df = state_df.sort_values(["core", "start_us"]).reset_index(drop=True)
        state_df = validate_state_df(state_df)

        resid_rows: List[Dict[str, object]] = []
        for core_id in all_core_ids:
            for s, e in residency_by_core.get(core_id, []):
                if e <= s:
                    continue
                resid_rows.append(
                    {
                        "start_us": (s - t0) / float(self._chip_freq_mhz),
                        "end_us": (e - t0) / float(self._chip_freq_mhz),
                        "core": core_map[core_id],
                        "resident": 1,
                    }
                )
        resid_df = pd.DataFrame(resid_rows)
        if len(resid_df) == 0:
            resid_df = pd.DataFrame(columns=["start_us", "end_us", "core", "resident"])
        resid_df = resid_df.sort_values(["core", "start_us"]).reset_index(drop=True)
        resid_df = validate_resid_df(resid_df)

        self._state_df_cache = state_df
        self._resid_df_cache = resid_df
        return state_df.copy(), resid_df.copy()

    def build_state_intervals(self) -> pd.DataFrame:
        state_df, _ = self._build_state_and_residency()
        return state_df

    def build_residency_intervals(self) -> pd.DataFrame:
        _, resid_df = self._build_state_and_residency()
        return resid_df

    def anomaly_summary(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for a in self._anomalies:
            out[a["type"]] = out.get(a["type"], 0) + 1
        return out

    def export_baseline_csvs(self, out_dir: str) -> Tuple[str, str, str]:
        os.makedirs(out_dir, exist_ok=True)
        state_df = self.build_state_intervals()
        resid_df = self.build_residency_intervals()

        state_path = os.path.join(out_dir, "state_intervals.csv")
        resid_path = os.path.join(out_dir, "residency_intervals.csv")
        debug_meta_path = os.path.join(out_dir, "adapter_debug_summary.txt")

        state_df.to_csv(state_path, index=False)
        resid_df.to_csv(resid_path, index=False)

        with open(debug_meta_path, "w", encoding="utf-8") as f:
            f.write(f"profile_csv={self.profile_csv}\n")
            f.write(f"zone_log={self.zone_log}\n")
            f.write(f"chip_freq_mhz={self._chip_freq_mhz}\n")
            f.write(f"output_mode={self.cfg.output_mode}\n")
            f.write(f"residency_model={self.cfg.residency_model}\n")
            f.write(f"ops_per_zone={'' if self.cfg.ops_per_zone is None else self.cfg.ops_per_zone}\n")
            f.write(f"normalize_zero={int(self.cfg.normalize_zero)}\n")
            f.write(f"events={len(self._events)}\n")
            f.write(f"intervals={len(self._intervals)}\n")
            f.write(f"map_hit_events={self._map_hit_count}\n")
            f.write(f"map_total_events={len(self._events)}\n")
            f.write(f"anomalies={self.anomaly_summary()}\n")

        return state_path, resid_path, debug_meta_path


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Parse Tenstorrent Wormhole profile_log_device.csv + zone_src_locations.log "
            "and export normalized Phase-2 state/residency intervals."
        )
    )
    ap.add_argument("--profile-csv", required=True, help="Path to profile_log_device.csv")
    ap.add_argument("--zone-log", required=True, help="Path to zone_src_locations.log or new_zone_src_locations.log")
    ap.add_argument("--out-dir", required=True, help="Directory for output CSVs")
    ap.add_argument(
        "--output-mode",
        choices=["lane", "tile"],
        default="tile",
        help="Core output mode (tile for engine-facing export; lane for debug)",
    )
    ap.add_argument("--chip-freq-mhz", type=int, default=None, help="Override CHIP_FREQ[MHz]")
    ap.add_argument("--no-normalize-zero", action="store_true", help="Keep original cycle origin instead of t0=0")
    ap.add_argument("--strict-pairing", action="store_true", help="Fail on unmatched start/end events")
    ap.add_argument("--strict-map-hit", action="store_true", help="Fail if any profile tuple is absent in zone map")
    ap.add_argument("--ops-per-zone", type=float, default=None, help="Optional work_done units attached to each explicit throughput zone")
    ap.add_argument(
        "--residency-model",
        choices=["kernel_envelope", "active_span"],
        default="kernel_envelope",
        help="Residency policy: default kernel envelope or compute-oriented active span.",
    )
    args = ap.parse_args()

    cfg = TTWormholeParseConfig(
        output_mode=args.output_mode,
        normalize_zero=not args.no_normalize_zero,
        strict_pairing=bool(args.strict_pairing),
        strict_map_hit=bool(args.strict_map_hit),
        chip_freq_mhz_override=args.chip_freq_mhz,
        residency_model=args.residency_model,
        ops_per_zone=args.ops_per_zone,
    )
    ad = TTWormholePlatformAdapter(args.profile_csv, args.zone_log, cfg=cfg)
    state_path, resid_path, debug_path = ad.export_baseline_csvs(args.out_dir)

    print(f"wrote: {state_path}")
    print(f"wrote: {resid_path}")
    print(f"wrote: {debug_path}")
    print(f"anomalies: {ad.anomaly_summary()}")


if __name__ == "__main__":
    main()
