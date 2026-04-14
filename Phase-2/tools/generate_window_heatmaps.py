#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
from pathlib import Path
from typing import Dict, List, Tuple


def to_float(raw: str | None, default: float = float("nan")) -> float:
    if raw is None:
        return default
    s = raw.strip()
    if not s:
        return default
    if s.lower() == "nan":
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return default


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def finite(v: float) -> bool:
    return math.isfinite(v)


def parse_windows(path: Path) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, raw in enumerate(reader):
            try:
                core = int(float((raw.get("core") or "").strip()))
            except Exception:
                core = 0
            try:
                wid = int(float((raw.get("window_id") or "").strip()))
            except Exception:
                wid = idx

            rows.append(
                {
                    "core": float(core),
                    "window_id": float(wid),
                    "window_start_us": to_float(raw.get("window_start_us")),
                    "window_end_us": to_float(raw.get("window_end_us")),
                    "resident_frac_of_window": clamp(to_float(raw.get("resident_frac_of_window"), 0.0), 0.0, 1.0),
                    "active_frac": clamp(to_float(raw.get("active_frac"), 0.0), 0.0, 1.0),
                    "stall_frac": clamp(to_float(raw.get("stall_frac"), 0.0), 0.0, 1.0),
                    "idle_frac": clamp(to_float(raw.get("idle_frac"), 0.0), 0.0, 1.0),
                    "sit": to_float(raw.get("sit")),
                    "sit_no_work_window_active": to_float(raw.get("sit_no_work_window_active")),
                }
            )
    rows.sort(key=lambda r: (int(r["core"]), int(r["window_id"])))
    return rows


def choose_sit_value(row: Dict[str, float]) -> float:
    v = row.get("sit_no_work_window_active", float("nan"))
    if finite(v):
        return v
    return row.get("sit", float("nan"))


def interpolate_color(c0: Tuple[int, int, int], c1: Tuple[int, int, int], t: float) -> str:
    t = clamp(t, 0.0, 1.0)
    r = int(round(c0[0] + (c1[0] - c0[0]) * t))
    g = int(round(c0[1] + (c1[1] - c0[1]) * t))
    b = int(round(c0[2] + (c1[2] - c0[2]) * t))
    return f"#{r:02x}{g:02x}{b:02x}"


def metric_specs() -> List[Dict[str, object]]:
    return [
        {
            "key": "active_frac",
            "title": "Active Fraction Heatmap",
            "subtitle": "Fraction of resident window classified as active",
            "low": (244, 248, 244),
            "high": (44, 160, 44),
            "vmin": 0.0,
            "vmax": 1.0,
            "ticks": ["0.00", "0.25", "0.50", "0.75", "1.00"],
        },
        {
            "key": "stall_frac",
            "title": "Stall Fraction Heatmap",
            "subtitle": "Fraction of resident window classified as stall",
            "low": (255, 245, 245),
            "high": (214, 39, 40),
            "vmin": 0.0,
            "vmax": 1.0,
            "ticks": ["0.00", "0.25", "0.50", "0.75", "1.00"],
        },
        {
            "key": "idle_frac",
            "title": "Idle Fraction Heatmap",
            "subtitle": "Fraction of resident window classified as idle",
            "low": (255, 249, 233),
            "high": (242, 183, 1),
            "vmin": 0.0,
            "vmax": 1.0,
            "ticks": ["0.00", "0.25", "0.50", "0.75", "1.00"],
        },
        {
            "key": "resident_frac_of_window",
            "title": "Residency Fraction Heatmap",
            "subtitle": "Fraction of each window covered by residency",
            "low": (245, 245, 245),
            "high": (127, 127, 127),
            "vmin": 0.0,
            "vmax": 1.0,
            "ticks": ["0.00", "0.25", "0.50", "0.75", "1.00"],
        },
        {
            "key": "sit_metric",
            "title": "SIT Heatmap",
            "subtitle": "Per-window SIT value (prefers sit_no_work_window_active)",
            "low": (239, 246, 255),
            "high": (31, 119, 180),
            "vmin": None,
            "vmax": None,
            "ticks": None,
        },
    ]


def build_matrix(rows: List[Dict[str, float]], key: str) -> Tuple[List[int], List[int], Dict[Tuple[int, int], float]]:
    cores = sorted({int(r["core"]) for r in rows})
    windows = sorted({int(r["window_id"]) for r in rows})
    data: Dict[Tuple[int, int], float] = {}
    for row in rows:
        core = int(row["core"])
        wid = int(row["window_id"])
        if key == "sit_metric":
            data[(core, wid)] = choose_sit_value(row)
        else:
            data[(core, wid)] = float(row.get(key, float("nan")))
    return cores, windows, data


def format_tick(v: float) -> str:
    if abs(v) >= 1000.0:
        return f"{v:,.0f}"
    if abs(v) >= 10.0:
        return f"{v:.2f}"
    return f"{v:.3f}"


def write_heatmap_svg(
    *,
    rows: List[Dict[str, float]],
    spec: Dict[str, object],
    out_path: Path,
    prefix: str,
    platform_label: str,
) -> None:
    cores, windows, data = build_matrix(rows, str(spec["key"]))
    if not cores or not windows:
        return

    finite_values = [v for v in data.values() if finite(v)]
    if not finite_values:
        return

    vmin = spec["vmin"]
    vmax = spec["vmax"]
    if vmin is None or vmax is None:
        vmin = min(finite_values)
        vmax = max(finite_values)
        if vmin == vmax:
            pad = 0.05 * (abs(vmin) if vmin != 0.0 else 1.0)
            vmin -= pad
            vmax += pad
        ticks = [format_tick(vmin + (vmax - vmin) * (i / 4.0)) for i in range(5)]
    else:
        ticks = list(spec["ticks"])

    cell_w = 16
    cell_h = 16
    left = 92
    right = 160
    top = 84
    bottom = 120
    legend_h = 14
    heat_w = max(220, cell_w * len(windows))
    heat_h = max(48, cell_h * len(cores))
    width = left + heat_w + right
    height = top + heat_h + bottom

    low = spec["low"]
    high = spec["high"]

    def color_for(v: float) -> str:
        if not finite(v):
            return "#f4f4f4"
        if vmax <= vmin:
            t = 0.0
        else:
            t = (v - float(vmin)) / (float(vmax) - float(vmin))
        return interpolate_color(low, high, t)

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2:.1f}" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">{html.escape(str(spec["title"]))}</text>',
        f'<text x="{width/2:.1f}" y="48" text-anchor="middle" font-family="sans-serif" font-size="12">{html.escape(prefix)} | {html.escape(platform_label)}</text>',
        f'<text x="{width/2:.1f}" y="64" text-anchor="middle" font-family="sans-serif" font-size="11">{html.escape(str(spec["subtitle"]))}</text>',
        f'<rect x="{left}" y="{top}" width="{heat_w}" height="{heat_h}" fill="white" stroke="#222"/>',
    ]

    for ridx, core in enumerate(cores):
        y = top + ridx * cell_h
        if ridx < len(cores) - 1:
            lines.append(f'<line x1="{left}" y1="{y+cell_h}" x2="{left+heat_w}" y2="{y+cell_h}" stroke="#f1f1f1"/>')
        lines.append(
            f'<text x="{left-10}" y="{y + cell_h/2 + 4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">core {core}</text>'
        )

    label_step = max(1, int(math.ceil(len(windows) / 16.0)))
    for cidx, wid in enumerate(windows):
        x = left + cidx * cell_w
        if cidx < len(windows) - 1:
            lines.append(f'<line x1="{x+cell_w}" y1="{top}" x2="{x+cell_w}" y2="{top+heat_h}" stroke="#f7f7f7"/>')
        if cidx % label_step == 0 or cidx == len(windows) - 1:
            lines.append(
                f'<text x="{x + cell_w/2:.1f}" y="{top + heat_h + 18:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10" transform="rotate(25 {x + cell_w/2:.1f} {top + heat_h + 18:.1f})">{wid}</text>'
            )

    for ridx, core in enumerate(cores):
        y = top + ridx * cell_h
        for cidx, wid in enumerate(windows):
            x = left + cidx * cell_w
            value = data.get((core, wid), float("nan"))
            lines.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{color_for(value)}"/>'
            )

    legend_x = left
    legend_y = top + heat_h + 52
    legend_w = min(320, heat_w)
    steps = max(40, legend_w)
    for i in range(steps):
        x = legend_x + i
        t = i / float(max(1, steps - 1))
        lines.append(
            f'<line x1="{x}" y1="{legend_y}" x2="{x}" y2="{legend_y + legend_h}" stroke="{interpolate_color(low, high, t)}"/>'
        )
    lines.append(f'<rect x="{legend_x}" y="{legend_y}" width="{legend_w}" height="{legend_h}" fill="none" stroke="#444"/>')
    for i, tick in enumerate(ticks):
        x = legend_x + (legend_w * (i / float(max(1, len(ticks) - 1))))
        lines.append(f'<line x1="{x:.1f}" y1="{legend_y + legend_h}" x2="{x:.1f}" y2="{legend_y + legend_h + 4}" stroke="#444"/>')
        lines.append(
            f'<text x="{x:.1f}" y="{legend_y + legend_h + 18:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{html.escape(str(tick))}</text>'
        )

    lines.append(
        f'<text x="{left + heat_w/2:.1f}" y="{height - 24:.1f}" text-anchor="middle" font-family="sans-serif" font-size="13">window_id</text>'
    )
    lines.append(
        f'<text x="26" y="{top + heat_h/2:.1f}" transform="rotate(-90 26 {top + heat_h/2:.1f})" text-anchor="middle" font-family="sans-serif" font-size="13">core</text>'
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(rows: List[Dict[str, str]], out_path: Path) -> None:
    if not rows:
        return
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate report-friendly active/stall/idle/SIT heatmaps from Phase-1 or Phase-2 windows.csv files."
    )
    ap.add_argument("--windows-csv", required=True, help="Path to windows.csv or run_windows.csv")
    ap.add_argument("--out-dir", required=True, help="Directory to write SVG heatmaps")
    ap.add_argument("--prefix", default="trace", help="Output filename prefix")
    ap.add_argument("--platform-label", default="SIT", help="Platform label for chart titles")
    args = ap.parse_args()

    windows_csv = Path(args.windows_csv).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = parse_windows(windows_csv)
    if not rows:
        raise SystemExit(f"no rows parsed from {windows_csv}")

    manifest_rows: List[Dict[str, str]] = []
    for spec in metric_specs():
        out_path = out_dir / f"{args.prefix}__heatmap_{spec['key']}.svg"
        write_heatmap_svg(
            rows=rows,
            spec=spec,
            out_path=out_path,
            prefix=args.prefix,
            platform_label=args.platform_label,
        )
        manifest_rows.append(
            {
                "metric": str(spec["key"]),
                "svg": str(out_path),
            }
        )

    write_manifest(manifest_rows, out_dir / f"{args.prefix}__heatmap_manifest.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
