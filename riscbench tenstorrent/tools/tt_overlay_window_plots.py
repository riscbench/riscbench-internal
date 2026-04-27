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
    pad = 0.05 * (hi - lo)
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


def load_overlay_series(rows_csv: Path) -> dict[str, list[dict]]:
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
            with aggregate_csv.open("r", encoding="utf-8", newline="") as aggregate_handle:
                agg_reader = csv.DictReader(aggregate_handle)
                for agg_row in agg_reader:
                    if str(agg_row.get("is_resident_window", "")).strip() != "1":
                        continue
                    x = parse_float(agg_row.get("window_start_us", ""))
                    sit = parse_float(agg_row.get("sit", ""))
                    if math.isfinite(x) and math.isfinite(sit):
                        points.append((x, sit))
            if not points:
                continue
            grouped.setdefault(workload, []).append(
                {
                    "workload": workload,
                    "workload_size": workload_size,
                    "case": case_label(workload_size),
                    "points": sorted(points),
                }
            )

    for series in grouped.values():
        series.sort(key=lambda item: case_sort_key(item["workload_size"]))
    return grouped


def write_overlay_plot(workload: str, series: list[dict], out_path: Path) -> None:
    width = 1500
    height = 780
    ml = 88
    mr = 230
    mt = 92
    mb = 96
    pw = width - ml - mr
    ph = height - mt - mb

    x_vals = [x for item in series for x, _ in item["points"]]
    y_vals = [y for item in series for _, y in item["points"]]
    x_lo, x_hi = bounds(x_vals)
    y_lo, y_hi = bounds(y_vals, include_zero=True)
    y_lo = min(y_lo, -0.03)
    y_hi = max(y_hi, 1.02)

    def x_for(value: float) -> float:
        frac = 0.5 if x_hi <= x_lo else (value - x_lo) / (x_hi - x_lo)
        frac = clamp(frac, 0.0, 1.0)
        return ml + (frac * pw)

    def y_for(value: float) -> float:
        frac = 0.5 if y_hi <= y_lo else (value - y_lo) / (y_hi - y_lo)
        frac = clamp(frac, 0.0, 1.0)
        return mt + ph - (frac * ph)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2:.1f}" y="40" text-anchor="middle" font-family="{SERIF}" font-size="28" font-weight="700">TT Workload SIT Comparison</text>',
        f'<text x="{width/2:.1f}" y="72" text-anchor="middle" font-family="{SERIF}" font-size="16">{svg_escape(pretty_workload(workload))} | aggregate resident windows</text>',
        f'<text x="{width/2:.1f}" y="96" text-anchor="middle" font-family="{SERIF}" font-size="12">Source metric: sit</text>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#9ca3af" stroke-width="1"/>',
        f'<line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#9ca3af" stroke-width="1"/>',
    ]

    for tick in ticks(y_lo, y_hi, 6):
        y = y_for(tick)
        svg.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml + pw}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>')
        svg.append(f'<text x="{ml - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="{SERIF}" font-size="13">{svg_escape(fmt_tick(tick))}</text>')

    for tick in ticks(x_lo, x_hi, 7):
        x = x_for(tick)
        svg.append(f'<line x1="{x:.2f}" y1="{mt}" x2="{x:.2f}" y2="{mt + ph}" stroke="#f3f4f6" stroke-width="1"/>')
        svg.append(f'<text x="{x:.2f}" y="{mt + ph + 24:.2f}" text-anchor="middle" font-family="{SERIF}" font-size="13">{svg_escape(fmt_tick(tick))}</text>')

    for idx, item in enumerate(series):
        color = PALETTE[idx % len(PALETTE)]
        points = " ".join(f"{x_for(x):.2f},{y_for(y):.2f}" for x, y in item["points"])
        svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.4" points="{points}"/>')

    legend_x = width - mr + 22
    legend_y = mt + 24
    legend_h = max(86, 26 + (len(series) * 24))
    svg.append(f'<rect x="{legend_x - 16}" y="{legend_y - 18}" width="196" height="{legend_h}" fill="#ffffff" stroke="#d1d5db" stroke-width="1"/>')
    for idx, item in enumerate(series):
        color = PALETTE[idx % len(PALETTE)]
        y = legend_y + (idx * 24)
        svg.append(f'<line x1="{legend_x}" y1="{y:.2f}" x2="{legend_x + 28}" y2="{y:.2f}" stroke="{color}" stroke-width="3"/>')
        svg.append(f'<text x="{legend_x + 38}" y="{y + 4:.2f}" font-family="{SERIF}" font-size="13">{svg_escape(item["case"])}</text>')

    svg.extend(
        [
            f'<text x="{ml - 56}" y="{mt + ph/2:.1f}" transform="rotate(-90 {ml - 56} {mt + ph/2:.1f})" text-anchor="middle" font-family="{SERIF}" font-size="18">Preferred SIT</text>',
            f'<text x="{ml + pw/2:.1f}" y="{height - 28}" text-anchor="middle" font-family="{SERIF}" font-size="18">Elapsed time (us)</text>',
            f'<text x="{ml}" y="{height - 56}" font-family="{SERIF}" font-size="12" fill="#4b5563">Overlay view: each color is one sweep case for the same TT workload.</text>',
            '</svg>',
        ]
    )
    out_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Render overlay TT workload SIT plots from comparison_rows.csv.")
    ap.add_argument("--rows-csv", required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    rows_csv = Path(args.rows_csv).expanduser().resolve()
    if not rows_csv.exists():
        raise SystemExit(f"rows csv not found: {rows_csv}")

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (rows_csv.parent / "plots_overlay")
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped = load_overlay_series(rows_csv)
    if not grouped:
        raise SystemExit(f"no overlay series found in: {rows_csv}")

    for workload, series in sorted(grouped.items()):
        out_path = out_dir / f"{slug(workload)}__overlay_sit.svg"
        write_overlay_plot(workload, series, out_path)
        print(f"wrote svg: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
