#!/usr/bin/env python3
"""Detect stall gaps in Tenstorrent trace profiler logs.

This script parses a `profile_log_device.csv` file and computes gaps between
profiling events. By default it treats gaps between a ZONE_END and the next
ZONE_START on the same (slot, core, processor) as stalls.
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

HEADER_RE = re.compile(r"CHIP_FREQ\[MHz\]:\s*(\d+)")


@dataclass(frozen=True)
class TraceEvent:
    slot: int
    core_x: int
    core_y: int
    processor: str
    time_cycles: int
    zone_name: str
    event_type: str


@dataclass(frozen=True)
class StallGap:
    slot: int
    core_x: int
    core_y: int
    processor: str
    prev_zone: str
    next_zone: str
    gap_cycles: int
    gap_us: float
    prev_time: int
    next_time: int


@dataclass(frozen=True)
class ZoneInstance:
    processor: str
    zone_name: str
    start_time: int
    end_time: int
    duration: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect stalls in Tenstorrent trace logs.")
    parser.add_argument("trace_csv", type=Path, help="Path to profile_log_device.csv")
    parser.add_argument(
        "--chip-freq-mhz",
        type=int,
        default=None,
        help="Override chip frequency in MHz (otherwise read from file header)",
    )
    parser.add_argument(
        "--gap-mode",
        choices=("end_to_start", "any"),
        default="end_to_start",
        help="How to detect gaps between events.",
    )
    parser.add_argument(
        "--threshold-us",
        type=float,
        default=5.0,
        help="Minimum gap in microseconds to report as a stall (default: 5.0).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output CSV path for stall gaps.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Show the top N stalls in stdout (default: 20).",
    )
    parser.add_argument(
        "--sram-zone-name",
        default="SRAM THROUGHPUT_SECTION",
        help="Zone name to use for SRAM bucket analysis.",
    )
    parser.add_argument(
        "--bucket-count",
        type=int,
        default=100,
        help="Number of buckets for SRAM analysis (default: 100).",
    )
    parser.add_argument(
        "--bucket-ops",
        type=float,
        default=2_097_152,
        help="Ops count to scale bucket analysis (default: 2,097,152).",
    )
    parser.add_argument(
        "--bucket-summary-out",
        type=Path,
        default=None,
        help="Optional CSV output for SRAM bucket summary.",
    )
    return parser.parse_args()


def parse_header_freq_mhz(first_line: str) -> Optional[int]:
    match = HEADER_RE.search(first_line)
    if not match:
        return None
    return int(match.group(1))


def parse_trace_events(trace_csv: Path) -> Tuple[int, List[TraceEvent]]:
    with trace_csv.open(newline="") as handle:
        first_line = handle.readline().strip()
        freq_mhz = parse_header_freq_mhz(first_line)
        header_line = handle.readline().strip()
        header = [item.strip() for item in csv.reader([header_line]).__next__()]
        reader = csv.DictReader(handle, fieldnames=header, skipinitialspace=True)

        events: List[TraceEvent] = []
        for row in reader:
            if not row or not row.get("PCIe slot"):
                continue
            events.append(
                TraceEvent(
                    slot=int(row["PCIe slot"]),
                    core_x=int(row["core_x"]),
                    core_y=int(row["core_y"]),
                    processor=row["RISC processor type"].strip(),
                    time_cycles=int(row["time[cycles since reset]"]),
                    zone_name=row["zone name"].strip(),
                    event_type=row["type"].strip(),
                )
            )
    if freq_mhz is None:
        raise ValueError("Unable to detect CHIP_FREQ[MHz] from header line.")
    return freq_mhz, events


def group_events(events: Iterable[TraceEvent]) -> dict[Tuple[int, int, int, str], List[TraceEvent]]:
    grouped: dict[Tuple[int, int, int, str], List[TraceEvent]] = {}
    for event in events:
        key = (event.slot, event.core_x, event.core_y, event.processor)
        grouped.setdefault(key, []).append(event)
    for group_events in grouped.values():
        group_events.sort(key=lambda event: event.time_cycles)
    return grouped


def find_stalls(
    grouped_events: dict[Tuple[int, int, int, str], List[TraceEvent]],
    freq_mhz: int,
    threshold_us: float,
    gap_mode: str,
) -> List[StallGap]:
    stalls: List[StallGap] = []
    cycles_per_us = float(freq_mhz)
    for (slot, core_x, core_y, processor), events in grouped_events.items():
        for prev, curr in zip(events, events[1:]):
            if gap_mode == "end_to_start":
                if prev.event_type != "ZONE_END" or curr.event_type != "ZONE_START":
                    continue
            gap_cycles = curr.time_cycles - prev.time_cycles
            if gap_cycles <= 0:
                continue
            gap_us = gap_cycles / cycles_per_us
            if gap_us < threshold_us:
                continue
            stalls.append(
                StallGap(
                    slot=slot,
                    core_x=core_x,
                    core_y=core_y,
                    processor=processor,
                    prev_zone=prev.zone_name,
                    next_zone=curr.zone_name,
                    gap_cycles=gap_cycles,
                    gap_us=gap_us,
                    prev_time=prev.time_cycles,
                    next_time=curr.time_cycles,
                )
            )
    stalls.sort(key=lambda stall: stall.gap_us, reverse=True)
    return stalls


def build_zone_instances(events: Sequence[TraceEvent]) -> List[ZoneInstance]:
    start_times: dict[Tuple[str, str], List[int]] = {}
    end_times: dict[Tuple[str, str], List[int]] = {}
    for event in events:
        key = (event.processor, event.zone_name)
        if event.event_type == "ZONE_START":
            start_times.setdefault(key, []).append(event.time_cycles)
        elif event.event_type == "ZONE_END":
            end_times.setdefault(key, []).append(event.time_cycles)

    zones: List[ZoneInstance] = []
    for key, starts in start_times.items():
        ends = end_times.get(key, [])
        for start, end in zip(starts, ends):
            duration = end - start
            if duration < 0:
                continue
            zones.append(
                ZoneInstance(
                    processor=key[0],
                    zone_name=key[1],
                    start_time=start,
                    end_time=end,
                    duration=duration,
                )
            )
    return zones


def compute_runtime_offset(events: Sequence[TraceEvent]) -> int:
    if not events:
        return 0
    return min(event.time_cycles for event in events)


def apply_runtime_offset(zones: Sequence[ZoneInstance], offset: int) -> List[ZoneInstance]:
    adjusted: List[ZoneInstance] = []
    for zone in zones:
        start_time = zone.start_time - offset
        end_time = zone.end_time - offset
        duration = end_time - start_time
        if duration < 0:
            continue
        adjusted.append(
            ZoneInstance(
                processor=zone.processor,
                zone_name=zone.zone_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
            )
        )
    return adjusted


def linspace(start: float, end: float, count: int) -> List[float]:
    if count <= 1:
        return [start]
    step = (end - start) / float(count - 1)
    return [start + step * i for i in range(count)]


def summarize_sram_buckets(
    zones: Sequence[ZoneInstance],
    sram_zone_name: str,
    bucket_count: int,
    bucket_ops: float,
) -> List[dict[str, float]]:
    sram_zones = [zone for zone in zones if zone.zone_name == sram_zone_name]
    if not sram_zones:
        return []

    sram_max_runtime = max(zone.end_time for zone in sram_zones)
    buckets = linspace(0.0, float(sram_max_runtime), bucket_count + 1)
    summary: List[dict[str, float]] = []

    for i in range(bucket_count):
        bucket_start = buckets[i]
        bucket_end = buckets[i + 1]
        total_percentage = 0.0
        for zone in sram_zones:
            overlap_duration = max(
                0.0,
                min(bucket_end, float(zone.end_time)) - max(bucket_start, float(zone.start_time)),
            )
            if overlap_duration <= 0.0:
                continue
            zone_total = float(zone.duration)
            percentage = 0.0 if zone_total <= 0.0 else (overlap_duration / zone_total) * 100.0
            total_percentage += percentage
        ops_for_bucket = (total_percentage / 100.0) * bucket_ops
        summary.append(
            {
                "bucket_number": float(i),
                "aggregate_percentage": total_percentage,
                "ops_for_bucket": ops_for_bucket,
            }
        )
    return summary


def write_bucket_summary(summary: Sequence[dict[str, float]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["bucket_number", "aggregate_percentage", "ops_for_bucket"])
        for row in summary:
            writer.writerow(
                [
                    int(row["bucket_number"]),
                    f"{row['aggregate_percentage']:.6f}",
                    f"{row['ops_for_bucket']:.6f}",
                ]
            )


def write_stalls_csv(stalls: Sequence[StallGap], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "PCIe slot",
                "core_x",
                "core_y",
                "processor",
                "prev_zone",
                "next_zone",
                "gap_cycles",
                "gap_us",
                "prev_time_cycles",
                "next_time_cycles",
            ]
        )
        for stall in stalls:
            writer.writerow(
                [
                    stall.slot,
                    stall.core_x,
                    stall.core_y,
                    stall.processor,
                    stall.prev_zone,
                    stall.next_zone,
                    stall.gap_cycles,
                    f"{stall.gap_us:.3f}",
                    stall.prev_time,
                    stall.next_time,
                ]
            )


def summarize(stalls: Sequence[StallGap], top_n: int) -> str:
    if not stalls:
        return "No stalls found above threshold."
    lines = ["Top stalls (by gap_us):"]
    for stall in stalls[:top_n]:
        lines.append(
            "- slot {slot} core({core_x},{core_y}) {processor}: {gap_us:.3f} us "
            "({prev_zone} -> {next_zone})".format(
                slot=stall.slot,
                core_x=stall.core_x,
                core_y=stall.core_y,
                processor=stall.processor,
                gap_us=stall.gap_us,
                prev_zone=stall.prev_zone,
                next_zone=stall.next_zone,
            )
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    freq_mhz, events = parse_trace_events(args.trace_csv)
    if args.chip_freq_mhz is not None:
        freq_mhz = args.chip_freq_mhz
    grouped = group_events(events)
    stalls = find_stalls(grouped, freq_mhz, args.threshold_us, args.gap_mode)
    print(summarize(stalls, args.top))
    if args.output:
        write_stalls_csv(stalls, args.output)
        print(f"Wrote {len(stalls)} stalls to {args.output}")
    if args.bucket_summary_out:
        runtime_offset = compute_runtime_offset(events)
        zones = build_zone_instances(events)
        zones = apply_runtime_offset(zones, runtime_offset)
        summary = summarize_sram_buckets(
            zones,
            sram_zone_name=args.sram_zone_name,
            bucket_count=args.bucket_count,
            bucket_ops=args.bucket_ops,
        )
        if not summary:
            print(f"No zones named '{args.sram_zone_name}' were found to analyze.")
        else:
            write_bucket_summary(summary, args.bucket_summary_out)
            print(f"Wrote SRAM bucket summary to {args.bucket_summary_out}")


if __name__ == "__main__":
    main()
