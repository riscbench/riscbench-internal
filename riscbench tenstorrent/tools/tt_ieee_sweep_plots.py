#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sit_classifier.workload_calibration import resolve_auto_ops_per_zone, resolve_size_active_boost


TT_MATMUL_SIZE_RE = re.compile(r"^tt_m(\d+)_n(\d+)_k(\d+)$")
TT_TILE_SIZE_RE = re.compile(r"^tt_(\d+)tile$")
SERIF = "Times New Roman, Times, serif"


def svg_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def parse_float(value: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return float("nan")


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
        return "fixed"
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
    pad = 0.08 * (hi - lo)
    if pad <= 0.0:
        pad = 1.0
    return lo - pad, hi + pad


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


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


def slug(text: str) -> str:
    out = []
    for ch in str(text).lower():
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_") or "plot"


def marker_circle(cx: float, cy: float, r: float, *, fill: str = "#000000") -> str:
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{fill}" stroke="#000000" stroke-width="1"/>'


def marker_square(cx: float, cy: float, r: float, *, fill: str = "#ffffff") -> str:
    return f'<rect x="{cx-r:.2f}" y="{cy-r:.2f}" width="{2*r:.2f}" height="{2*r:.2f}" fill="{fill}" stroke="#000000" stroke-width="1"/>'


def marker_triangle(cx: float, cy: float, r: float, *, fill: str = "#000000") -> str:
    points = [
        (cx, cy - r),
        (cx - (0.866 * r), cy + (0.5 * r)),
        (cx + (0.866 * r), cy + (0.5 * r)),
    ]
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="#000000" stroke-width="1"/>'


def load_rows(path: Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if str(row.get("status", "")).strip() != "ok":
                continue
            workload = str(row.get("workload", "")).strip()
            workload_size = str(row.get("workload_size", "")).strip()
            observed = parse_float(row.get("observed_flops_per_us_median", ""))
            observed_median = parse_float(row.get("observed_flops_per_us_median", ""))
            ops_per_zone = resolve_auto_ops_per_zone(workload)
            expected_zone_count = resolve_size_active_boost(workload_size)
            ideal_total_ops = (
                float(ops_per_zone) * float(expected_zone_count)
                if ops_per_zone is not None and expected_zone_count is not None
                else float("nan")
            )
            item = {
                "workload": workload,
                "workload_size": workload_size,
                "case": case_label(workload_size),
                "observed_flops_per_us": observed,
                "observed_flops_per_us_median": observed_median,
                "ideal_total_ops": ideal_total_ops,
                "expected_work_rate": parse_float(row.get("expected_work_rate", "")),
                "sit_median": parse_float(row.get("sit_median", "")),
                "obs_exp_ratio": (
                    observed / parse_float(row.get("expected_work_rate", ""))
                    if parse_float(row.get("expected_work_rate", "")) > 0.0
                    else float("nan")
                ),
                "summary_path": str(row.get("summary_path", "")).strip(),
            }
            grouped.setdefault(workload, []).append(item)

    for workload_rows in grouped.values():
        workload_rows.sort(key=lambda row: case_sort_key(row["workload_size"]))
    return grouped


def write_ieee_plot(workload: str, rows: list[dict], out_path: Path) -> None:
    width = 760
    height = 460
    ml = 72
    mr = 28
    mt = 56
    mb = 56
    panel_gap = 38
    panel_h = 140
    top_y = mt
    bottom_y = mt + panel_h + panel_gap
    panel_w = width - ml - mr

    x_count = len(rows)
    step = panel_w / max(1, x_count - 1) if x_count > 1 else 0.0

    def x_for(idx: int) -> float:
        if x_count == 1:
            return ml + (panel_w / 2.0)
        return ml + (idx * step)

    top_vals = [float(row["observed_flops_per_us"]) for row in rows] + [float(row["expected_work_rate"]) for row in rows]
    top_lo, top_hi = bounds(top_vals, include_zero=True)
    bottom_vals = [float(row["sit_median"]) for row in rows] + [float(row["obs_exp_ratio"]) for row in rows]
    bottom_lo, bottom_hi = bounds(bottom_vals, include_zero=True)
    bottom_lo = min(bottom_lo, 0.0)

    def y_for(value: float, lo: float, hi: float, panel_top: float) -> float:
        if not math.isfinite(value):
            return panel_top + panel_h
        frac = 0.5 if hi <= lo else (value - lo) / (hi - lo)
        frac = clamp(frac, 0.0, 1.0)
        return panel_top + panel_h - (frac * panel_h)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2:.1f}" y="26" text-anchor="middle" font-family="{SERIF}" font-size="15" font-weight="700">IEEE-Style Sweep Plot: {svg_escape(pretty_workload(workload))}</text>',
        f'<text x="{width/2:.1f}" y="42" text-anchor="middle" font-family="{SERIF}" font-size="10">Expected uses the TT formula-based run expectation. Bottom shows window SIT and median observed/expected ratio.</text>',
    ]

    def draw_axes(panel_top: float, lo: float, hi: float, y_label: str, tag: str) -> None:
        svg.extend(
            [
                f'<line x1="{ml}" y1="{panel_top}" x2="{ml}" y2="{panel_top + panel_h}" stroke="#000000" stroke-width="1"/>',
                f'<line x1="{ml}" y1="{panel_top + panel_h}" x2="{ml + panel_w}" y2="{panel_top + panel_h}" stroke="#000000" stroke-width="1"/>',
                f'<text x="{ml - 54}" y="{panel_top + (panel_h/2):.1f}" transform="rotate(-90 {ml - 54} {panel_top + (panel_h/2):.1f})" text-anchor="middle" font-family="{SERIF}" font-size="11">{svg_escape(y_label)}</text>',
                f'<text x="{ml}" y="{panel_top - 10}" font-family="{SERIF}" font-size="11" font-weight="700">({tag})</text>',
            ]
        )
        for tick in ticks(lo, hi):
            y = y_for(tick, lo, hi, panel_top)
            svg.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml + panel_w}" y2="{y:.2f}" stroke="#d1d5db" stroke-width="0.8"/>')
            svg.append(f'<text x="{ml - 8}" y="{y + 3:.2f}" text-anchor="end" font-family="{SERIF}" font-size="10">{svg_escape(fmt_tick(tick))}</text>')

    draw_axes(top_y, top_lo, top_hi, "FLOPs/us", "a")
    draw_axes(bottom_y, bottom_lo, bottom_hi, "Normalized Metric", "b")

    for idx, row in enumerate(rows):
        x = x_for(idx)
        label_y = bottom_y + panel_h + 16
        svg.append(f'<line x1="{x:.2f}" y1="{top_y + panel_h}" x2="{x:.2f}" y2="{top_y + panel_h + 4}" stroke="#000000" stroke-width="1"/>')
        svg.append(f'<line x1="{x:.2f}" y1="{bottom_y + panel_h}" x2="{x:.2f}" y2="{bottom_y + panel_h + 4}" stroke="#000000" stroke-width="1"/>')
        svg.append(
            f'<text x="{x:.2f}" y="{label_y:.2f}" text-anchor="middle" font-family="{SERIF}" font-size="10">{svg_escape(row["case"])}</text>'
        )

    if len(rows) > 1:
        obs_points = []
        exp_points = []
        sit_points = []
        ratio_points = []
        for idx, row in enumerate(rows):
            x = x_for(idx)
            obs_points.append((x, y_for(float(row["observed_flops_per_us"]), top_lo, top_hi, top_y)))
            exp_points.append((x, y_for(float(row["expected_work_rate"]), top_lo, top_hi, top_y)))
            sit_points.append((x, y_for(float(row["sit_median"]), bottom_lo, bottom_hi, bottom_y)))
            ratio_points.append((x, y_for(float(row["obs_exp_ratio"]), bottom_lo, bottom_hi, bottom_y)))
        svg.append(
            '<polyline fill="none" stroke="#000000" stroke-width="1.4" points="'
            + " ".join(f"{x:.2f},{y:.2f}" for x, y in obs_points)
            + '"/>'
        )
        svg.append(
            '<polyline fill="none" stroke="#000000" stroke-width="1.1" stroke-dasharray="5 3" points="'
            + " ".join(f"{x:.2f},{y:.2f}" for x, y in exp_points)
            + '"/>'
        )
        svg.append(
            '<polyline fill="none" stroke="#000000" stroke-width="1.2" points="'
            + " ".join(f"{x:.2f},{y:.2f}" for x, y in sit_points)
            + '"/>'
        )
        svg.append(
            '<polyline fill="none" stroke="#6b7280" stroke-width="1.1" stroke-dasharray="2 2" points="'
            + " ".join(f"{x:.2f},{y:.2f}" for x, y in ratio_points)
            + '"/>'
        )

    for idx, row in enumerate(rows):
        x = x_for(idx)
        svg.append(marker_circle(x, y_for(float(row["observed_flops_per_us"]), top_lo, top_hi, top_y), 3.8, fill="#000000"))
        svg.append(marker_square(x, y_for(float(row["expected_work_rate"]), top_lo, top_hi, top_y), 3.5, fill="#ffffff"))
        svg.append(marker_triangle(x, y_for(float(row["sit_median"]), bottom_lo, bottom_hi, bottom_y), 4.0, fill="#000000"))
        svg.append(marker_square(x, y_for(float(row["obs_exp_ratio"]), bottom_lo, bottom_hi, bottom_y), 3.2, fill="#9ca3af"))

    legend_x = width - 235
    legend_y = 18
    svg.extend(
        [
            f'<rect x="{legend_x}" y="{legend_y}" width="210" height="68" fill="#ffffff" stroke="#000000" stroke-width="0.8"/>',
            marker_circle(legend_x + 16, legend_y + 18, 3.8, fill="#000000"),
            f'<text x="{legend_x + 28}" y="{legend_y + 22}" font-family="{SERIF}" font-size="10">Observed FLOPs/us</text>',
            marker_square(legend_x + 16, legend_y + 36, 3.5, fill="#ffffff"),
            f'<text x="{legend_x + 28}" y="{legend_y + 40}" font-family="{SERIF}" font-size="10">Expected</text>',
            marker_triangle(legend_x + 16, legend_y + 54, 4.0, fill="#000000"),
            f'<text x="{legend_x + 28}" y="{legend_y + 58}" font-family="{SERIF}" font-size="10">SIT median</text>',
            marker_square(legend_x + 116, legend_y + 54, 3.2, fill="#9ca3af"),
            f'<text x="{legend_x + 128}" y="{legend_y + 58}" font-family="{SERIF}" font-size="10">Obs/Exp</text>',
        ]
    )

    svg.append(
        f'<text x="{ml + panel_w/2:.1f}" y="{height - 12}" text-anchor="middle" font-family="{SERIF}" font-size="11">Sweep case</text>'
    )
    svg.append("</svg>")
    out_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Render IEEE-style per-workload SVG plots from TT sweep results.")
    ap.add_argument("--rows-csv", required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    rows_csv = Path(args.rows_csv).expanduser().resolve()
    if not rows_csv.exists():
        raise SystemExit(f"rows csv not found: {rows_csv}")

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (rows_csv.parent / "plots_ieee")
    out_dir.mkdir(parents=True, exist_ok=True)

    grouped = load_rows(rows_csv)
    if not grouped:
        raise SystemExit(f"no successful rows found in: {rows_csv}")

    for workload, rows in sorted(grouped.items()):
        out_path = out_dir / f"{slug(workload)}__ieee.svg"
        write_ieee_plot(workload, rows, out_path)
        print(f"wrote svg: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
