#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path

TT_MATMUL_SIZE_RE = re.compile(r"^tt_m(\d+)_n(\d+)_k(\d+)$")
TT_TILE_SIZE_RE = re.compile(r"^tt_(\d+)tile$")
SERIF = "Times New Roman, Times, serif"
PALETTE = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#ea580c",
    "#7c3aed",
    "#0891b2",
    "#db2777",
    "#ca8a04",
]


def parse_float(value: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return float("nan")


def svg_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def slug(text: str) -> str:
    out = []
    for ch in str(text).lower():
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_") or "plot"


def pretty_workload(name: str) -> str:
    raw = str(name).strip()
    if raw.startswith("tt_"):
        raw = raw[3:]
    return raw.replace("_", " ")


def case_label(size: str) -> str:
    raw = str(size).strip()
    match = TT_MATMUL_SIZE_RE.match(raw)
    if match:
        return f"M{match.group(1)}"
    match = TT_TILE_SIZE_RE.match(raw)
    if match:
        return f"{match.group(1)}t"
    if raw == "tt_1tile":
        return "1t"
    return raw


def case_sort_key(size: str) -> tuple[int, int]:
    raw = str(size).strip()
    match = TT_MATMUL_SIZE_RE.match(raw)
    if match:
        return (0, int(match.group(1)))
    match = TT_TILE_SIZE_RE.match(raw)
    if match:
        return (1, int(match.group(1)))
    if raw == "tt_1tile":
        return (2, 1)
    return (9, 0)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def bounds(values: list[float], *, include_zero: bool = False) -> tuple[float, float]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return (0.0, 1.0)
    lo = min(clean)
    hi = max(clean)
    if include_zero:
        lo = min(lo, 0.0)
    if hi <= lo:
        hi = lo + 1.0
    pad = 0.06 * (hi - lo)
    if pad <= 0.0:
        pad = 0.05
    return lo - pad, hi + pad


def ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    if not math.isfinite(lo) or not math.isfinite(hi):
        return [0.0, 1.0]
    if hi <= lo:
        return [lo, hi + 1.0]
    step = (hi - lo) / max(1, count - 1)
    return [lo + (idx * step) for idx in range(count)]


def fmt_tick(value: float) -> str:
    if not math.isfinite(value):
        return "nan"
    abs_value = abs(value)
    if abs_value >= 10000.0:
        return f"{value/1000.0:.0f}k"
    if abs_value >= 1000.0:
        return f"{value/1000.0:.1f}k"
    if abs_value >= 100.0:
        return f"{value:.0f}"
    if abs_value >= 10.0:
        return f"{value:.1f}"
    return f"{value:.2f}"


def load_clarity_series(rows_csv: Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    with rows_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if str(row.get("status", "")).strip() != "ok":
                continue
            workload = str(row.get("workload", "")).strip()
            workload_size = str(row.get("workload_size", "")).strip()
            run_dir = Path(str(row.get("run_dir", "")).strip()).expanduser()
            aggregate_csv = run_dir / "aggregate_windows.csv"
            if not aggregate_csv.exists():
                continue
            points = []
            with aggregate_csv.open("r", encoding="utf-8", newline="") as agg_handle:
                agg_reader = csv.DictReader(agg_handle)
                raw_rows = [r for r in agg_reader if str(r.get("is_resident_window", "")).strip() == "1"]
            if not raw_rows:
                continue
            starts = [parse_float(r.get("window_start_us", "")) for r in raw_rows]
            ends = [parse_float(r.get("window_end_us", "")) for r in raw_rows]
            start_min = min(v for v in starts if math.isfinite(v))
            end_max = max(v for v in ends if math.isfinite(v))
            span = max(1e-9, end_max - start_min)
            for r in raw_rows:
                x0 = parse_float(r.get("window_start_us", ""))
                x1 = parse_float(r.get("window_end_us", ""))
                progress = ((0.5 * (x0 + x1)) - start_min) / span if math.isfinite(x0) and math.isfinite(x1) else float("nan")
                points.append(
                    {
                        "progress": progress,
                        "observed_flops_per_us": parse_float(r.get("observed_flops_per_us", "")),
                        "sit": parse_float(r.get("sit", "")),
                        "stall_frac": parse_float(r.get("stall_frac", "")),
                        "active_frac": parse_float(r.get("active_frac", "")),
                    }
                )
            grouped.setdefault(workload, []).append(
                {
                    "workload": workload,
                    "workload_size": workload_size,
                    "case": case_label(workload_size),
                    "points": points,
                }
            )
    for series in grouped.values():
        series.sort(key=lambda item: case_sort_key(item["workload_size"]))
    return grouped


def write_clarity_plot(workload: str, series: list[dict], out_path: Path) -> None:
    width = 1520
    height = 980
    ml = 90
    mr = 260
    mt = 88
    mb = 80
    gap = 42
    panel_h = 220
    pw = width - ml - mr
    panels = [
        ("Observed FLOPs/us", "observed_flops_per_us", True),
        ("SIT", "sit", False),
        ("Stall Fraction", "stall_frac", False),
    ]

    metric_values = {
        key: [float(point[key]) for item in series for point in item["points"]]
        for _, key, _ in panels
    }
    metric_ranges = {
        "observed_flops_per_us": bounds(metric_values["observed_flops_per_us"], include_zero=True),
        "sit": bounds(metric_values["sit"], include_zero=True),
        "stall_frac": bounds(metric_values["stall_frac"], include_zero=True),
    }
    metric_ranges["sit"] = (min(metric_ranges["sit"][0], 0.75), max(metric_ranges["sit"][1], 1.02))
    metric_ranges["stall_frac"] = (0.0, max(metric_ranges["stall_frac"][1], 0.08))

    def x_for(progress: float) -> float:
        return ml + (clamp(progress, 0.0, 1.0) * pw)

    def y_for(value: float, lo: float, hi: float, panel_top: float) -> float:
        frac = 0.5 if hi <= lo else (value - lo) / (hi - lo)
        frac = clamp(frac, 0.0, 1.0)
        return panel_top + panel_h - (frac * panel_h)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2:.1f}" y="38" text-anchor="middle" font-family="{SERIF}" font-size="28" font-weight="700">TT Workload Sweep Comparison</text>',
        f'<text x="{width/2:.1f}" y="68" text-anchor="middle" font-family="{SERIF}" font-size="16">{svg_escape(pretty_workload(workload))} | normalized progress view</text>',
        f'<text x="{width/2:.1f}" y="92" text-anchor="middle" font-family="{SERIF}" font-size="12">Cases share colors across panels so differences are easier to spot than in the single SIT overlay.</text>',
    ]

    for panel_idx, (title, key, _) in enumerate(panels):
        panel_top = mt + (panel_idx * (panel_h + gap))
        lo, hi = metric_ranges[key]
        svg.extend(
            [
                f'<line x1="{ml}" y1="{panel_top}" x2="{ml}" y2="{panel_top + panel_h}" stroke="#9ca3af" stroke-width="1"/>',
                f'<line x1="{ml}" y1="{panel_top + panel_h}" x2="{ml + pw}" y2="{panel_top + panel_h}" stroke="#9ca3af" stroke-width="1"/>',
                f'<text x="{ml}" y="{panel_top - 14}" font-family="{SERIF}" font-size="18" font-weight="700">{svg_escape(title)}</text>',
            ]
        )
        for tick in ticks(lo, hi, 5):
            y = y_for(tick, lo, hi, panel_top)
            svg.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml + pw}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>')
            svg.append(f'<text x="{ml - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="{SERIF}" font-size="13">{svg_escape(fmt_tick(tick))}</text>')
        if panel_idx == len(panels) - 1:
            for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
                x = x_for(tick)
                svg.append(f'<line x1="{x:.2f}" y1="{panel_top}" x2="{x:.2f}" y2="{panel_top + panel_h}" stroke="#f3f4f6" stroke-width="1"/>')
                svg.append(f'<text x="{x:.2f}" y="{panel_top + panel_h + 24:.2f}" text-anchor="middle" font-family="{SERIF}" font-size="13">{int(tick*100)}%</text>')
        else:
            for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
                x = x_for(tick)
                svg.append(f'<line x1="{x:.2f}" y1="{panel_top}" x2="{x:.2f}" y2="{panel_top + panel_h}" stroke="#f9fafb" stroke-width="1"/>')

        for idx, item in enumerate(series):
            color = PALETTE[idx % len(PALETTE)]
            pts = [
                (x_for(float(point["progress"])), y_for(float(point[key]), lo, hi, panel_top))
                for point in item["points"]
                if math.isfinite(float(point["progress"])) and math.isfinite(float(point[key]))
            ]
            if not pts:
                continue
            svg.append(
                '<polyline fill="none" stroke="{}" stroke-width="2.5" points="{}"/>'.format(
                    color, " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
                )
            )
            for x, y in pts:
                svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.8" fill="{color}" stroke="#ffffff" stroke-width="0.8"/>')
            end_x, end_y = pts[-1]
            svg.append(f'<text x="{end_x + 8:.2f}" y="{end_y + 4:.2f}" font-family="{SERIF}" font-size="12" fill="{color}">{svg_escape(item["case"])}</text>')

    legend_x = width - mr + 28
    legend_y = mt + 20
    legend_h = max(100, 30 + (len(series) * 26))
    svg.append(f'<rect x="{legend_x - 18}" y="{legend_y - 18}" width="212" height="{legend_h}" fill="#ffffff" stroke="#d1d5db" stroke-width="1"/>')
    svg.append(f'<text x="{legend_x}" y="{legend_y}" font-family="{SERIF}" font-size="14" font-weight="700">Sweep cases</text>')
    for idx, item in enumerate(series):
        color = PALETTE[idx % len(PALETTE)]
        y = legend_y + 24 + (idx * 24)
        svg.append(f'<line x1="{legend_x}" y1="{y:.2f}" x2="{legend_x + 26}" y2="{y:.2f}" stroke="{color}" stroke-width="3"/>')
        svg.append(f'<circle cx="{legend_x + 13:.2f}" cy="{y:.2f}" r="3" fill="{color}" stroke="#ffffff" stroke-width="0.8"/>')
        svg.append(f'<text x="{legend_x + 38}" y="{y + 4:.2f}" font-family="{SERIF}" font-size="13">{svg_escape(item["case"])}</text>')

    svg.extend(
        [
            f'<text x="{ml - 60}" y="{mt + 110:.1f}" transform="rotate(-90 {ml - 60} {mt + 110:.1f})" text-anchor="middle" font-family="{SERIF}" font-size="17">Metric value</text>',
            f'<text x="{ml + pw/2:.1f}" y="{height - 22}" text-anchor="middle" font-family="{SERIF}" font-size="18">Normalized progress through run</text>',
            '</svg>',
        ]
    )
    out_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Render clearer multi-panel TT workload comparison plots.")
    ap.add_argument("--rows-csv", required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    rows_csv = Path(args.rows_csv).expanduser().resolve()
    if not rows_csv.exists():
        raise SystemExit(f"rows csv not found: {rows_csv}")
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (rows_csv.parent / "plots_clarity")
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped = load_clarity_series(rows_csv)
    if not grouped:
        raise SystemExit(f"no clarity series found in: {rows_csv}")

    for workload, series in sorted(grouped.items()):
        out_path = out_dir / f"{slug(workload)}__clarity.svg"
        write_clarity_plot(workload, series, out_path)
        print(f"wrote svg: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
