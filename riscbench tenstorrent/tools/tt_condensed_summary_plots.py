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

WORKLOAD_LABELS = {
    "tt_eltwise_sfpu": "Eltwise SFPU",
    "tt_eltwise_binary": "Eltwise Binary",
    "tt_custom_sfpi_add": "SFPI Add",
    "tt_custom_sfpi_smoothstep": "SFPI Smoothstep",
    "tt_sfpu_chain": "SFPU Chain",
    "tt_matmul_single": "MatMul Single",
    "tt_matmul_multi": "MatMul Multi",
}

COLORS = {
    "tt_eltwise_sfpu": "#ff7f0e",
    "tt_eltwise_binary": "#2ca02c",
    "tt_custom_sfpi_add": "#1f77b4",
    "tt_custom_sfpi_smoothstep": "#d62728",
    "tt_sfpu_chain": "#9467bd",
    "tt_matmul_single": "#8c564b",
    "tt_matmul_multi": "#17becf",
}

LINE_STYLES = {
    "tt_eltwise_sfpu": None,
    "tt_eltwise_binary": "8 4",
    "tt_custom_sfpi_add": "4 3",
    "tt_custom_sfpi_smoothstep": "12 4 3 4",
    "tt_sfpu_chain": "2 3",
    "tt_matmul_single": None,
    "tt_matmul_multi": "8 4",
}

MARKERS = {
    "tt_eltwise_sfpu": "circle",
    "tt_eltwise_binary": "triangle",
    "tt_custom_sfpi_add": "square",
    "tt_custom_sfpi_smoothstep": "diamond",
    "tt_sfpu_chain": "circle_open",
    "tt_matmul_single": "circle",
    "tt_matmul_multi": "square",
}

REPRESENTATIVE_CASES = {
    "tt_matmul_single": "M640",
    "tt_matmul_multi": "M640",
    "tt_sfpu_chain": "1t",
    "tt_eltwise_sfpu": "64t",
    "tt_eltwise_binary": "64t",
    "tt_custom_sfpi_add": "64t",
    "tt_custom_sfpi_smoothstep": "64t",
}


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


def pretty_name(workload: str) -> str:
    return WORKLOAD_LABELS.get(workload, workload.replace("tt_", "").replace("_", " ").title())


def parse_case(size: str) -> tuple[str, int | None]:
    raw = str(size).strip()
    match = TT_MATMUL_SIZE_RE.match(raw)
    if match:
        return (f"M{match.group(1)}", int(match.group(1)))
    match = TT_TILE_SIZE_RE.match(raw)
    if match:
        return (f"{match.group(1)}t", int(match.group(1)))
    if raw == "tt_1tile":
        return ("1t", 1)
    return (raw, None)


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
    return f"{value:.4f}"


def draw_marker(cx: float, cy: float, color: str, marker: str, r: float = 8.0) -> str:
    if marker == "square":
        return f'<rect x="{cx-r:.2f}" y="{cy-r:.2f}" width="{2*r:.2f}" height="{2*r:.2f}" fill="{color}" stroke="#ffffff" stroke-width="1.2"/>'
    if marker == "diamond":
        pts = f"{cx:.2f},{cy-r:.2f} {cx+r:.2f},{cy:.2f} {cx:.2f},{cy+r:.2f} {cx-r:.2f},{cy:.2f}"
        return f'<polygon points="{pts}" fill="{color}" stroke="#ffffff" stroke-width="1.2"/>'
    if marker == "triangle":
        pts = f"{cx:.2f},{cy-r:.2f} {cx+r:.2f},{cy+r:.2f} {cx-r:.2f},{cy+r:.2f}"
        return f'<polygon points="{pts}" fill="{color}" stroke="#ffffff" stroke-width="1.2"/>'
    if marker == "circle_open":
        return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="#ffffff" stroke="{color}" stroke-width="2.4"/>'
    return f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="{color}" stroke="#ffffff" stroke-width="1.2"/>'


def load_rows(metrics_csv: Path) -> list[dict]:
    with metrics_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            case, case_num = parse_case(str(row.get("workload_size", "")))
            rows.append(
                {
                    "workload": str(row.get("workload", "")).strip(),
                    "case": case,
                    "case_num": case_num,
                    "sit_median": parse_float(row.get("sit_median", "")),
                    "active": parse_float(row.get("active", "")),
                    "stall": parse_float(row.get("stall", "")),
                    "idle": parse_float(row.get("idle", "")),
                    "ops_per_zone": parse_float(row.get("ops_per_zone", "")),
                }
            )
    return rows


def write_tile_sit(rows: list[dict], out_path: Path) -> None:
    workloads = [
        "tt_custom_sfpi_add",
        "tt_custom_sfpi_smoothstep",
        "tt_eltwise_binary",
        "tt_eltwise_sfpu",
        "tt_sfpu_chain",
    ]
    tile_points = {1: "1", 32: "32", 64: "64", 128: "128"}
    x_values = list(tile_points.keys())
    x_pos = {value: idx for idx, value in enumerate(x_values)}
    width, height = 1240, 820
    ml, mr, mt, mb = 150, 280, 90, 120
    pw, ph = width - ml - mr, height - mt - mb

    y_vals = [row["sit_median"] for row in rows if row["workload"] in workloads and math.isfinite(row["sit_median"])]
    y_lo = min(y_vals) - 0.0005
    y_hi = max(y_vals) + 0.0005
    offsets = {
        workload: ((idx - ((len(workloads) - 1) / 2.0)) * 14.0)
        for idx, workload in enumerate(workloads)
    }
    label_offsets = {
        "tt_custom_sfpi_add": -10,
        "tt_custom_sfpi_smoothstep": -26,
        "tt_eltwise_binary": 12,
        "tt_eltwise_sfpu": 28,
        "tt_sfpu_chain": -6,
    }

    def x_for(tile_count: int) -> float:
        idx = x_pos[tile_count]
        return ml + (idx * (pw / max(1, len(x_values) - 1)))

    def y_for(value: float) -> float:
        frac = 0.5 if y_hi <= y_lo else (value - y_lo) / (y_hi - y_lo)
        return mt + ph - (frac * ph)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2:.1f}" y="44" text-anchor="middle" font-family="{SERIF}" font-size="30" font-weight="700">Style SIT Summary for Tile Workloads</text>',
    ]
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        value = y_lo + frac * (y_hi - y_lo)
        y = y_for(value)
        svg.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml + pw}" y2="{y:.2f}" stroke="#d1d5db" stroke-dasharray="4 4"/>')
        svg.append(f'<text x="{ml - 16}" y="{y + 6:.2f}" text-anchor="end" font-family="{SERIF}" font-size="18">{value:.4f}</text>')
    for tile_count, label in tile_points.items():
        x = x_for(tile_count)
        svg.append(f'<line x1="{x:.2f}" y1="{mt}" x2="{x:.2f}" y2="{mt + ph}" stroke="#e5e7eb" stroke-dasharray="4 4"/>')
        svg.append(f'<text x="{x:.2f}" y="{mt + ph + 42:.2f}" text-anchor="middle" font-family="{SERIF}" font-size="22">{label}</text>')
    svg.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#111827" stroke-width="2"/>')
    svg.append(f'<line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#111827" stroke-width="2"/>')

    for workload in workloads:
        pts = []
        for row in rows:
            if row["workload"] != workload or row["case_num"] not in x_pos or not math.isfinite(row["sit_median"]):
                continue
            pts.append((row["case_num"], row["sit_median"]))
        pts.sort()
        if not pts:
            continue
        color = COLORS[workload]
        dash = LINE_STYLES.get(workload)
        marker = MARKERS.get(workload, "circle")
        plotted = [(x_for(x) + offsets[workload], y_for(y), x, y) for x, y in pts]
        svg.append(
            '<polyline fill="none" stroke="{}" stroke-width="3"{} points="{}"/>'.format(
                color,
                f' stroke-dasharray="{dash}"' if dash else "",
                " ".join(f"{px:.2f},{py:.2f}" for px, py, _, _ in plotted),
            )
        )
        for px, py, _, _ in plotted:
            svg.append(draw_marker(px, py, color, marker, r=8.5))
        end_x, end_y, _, _ = plotted[-1]
        svg.append(f'<text x="{end_x + 16:.2f}" y="{end_y + label_offsets.get(workload, 0):.2f}" font-family="{SERIF}" font-size="20" fill="{color}">{svg_escape(pretty_name(workload))}</text>')

    legend_x = width - 245
    legend_y = mt + 210
    for idx, workload in enumerate(workloads):
        y = legend_y + idx * 56
        color = COLORS[workload]
        dash = LINE_STYLES.get(workload)
        marker = MARKERS.get(workload, "circle")
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        svg.append(f'<line x1="{legend_x}" y1="{y:.2f}" x2="{legend_x + 70}" y2="{y:.2f}" stroke="{color}" stroke-width="4"{dash_attr}/>')
        svg.append(draw_marker(legend_x + 35, y, color, marker, r=8.0))
        svg.append(f'<text x="{legend_x + 96}" y="{y + 8:.2f}" font-family="{SERIF}" font-size="22">{svg_escape(pretty_name(workload))}</text>')

    svg.extend(
        [
            f'<text x="{ml - 88}" y="{mt + ph/2:.1f}" transform="rotate(-90 {ml - 88} {mt + ph/2:.1f})" text-anchor="middle" font-family="{SERIF}" font-size="30">SIT Median</text>',
            f'<text x="{ml + pw/2:.1f}" y="{height - 22}" text-anchor="middle" font-family="{SERIF}" font-size="30">Tile Count</text>',
            "</svg>",
        ]
    )
    out_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_matmul_sit(rows: list[dict], out_path: Path) -> None:
    workloads = ["tt_matmul_single", "tt_matmul_multi"]
    sizes = [320, 640, 960, 1280]
    width, height = 1080, 720
    ml, mr, mt, mb = 130, 230, 90, 110
    pw, ph = width - ml - mr, height - mt - mb
    y_vals = [row["sit_median"] for row in rows if row["workload"] in workloads and math.isfinite(row["sit_median"])]
    y_lo = min(y_vals) - 0.02
    y_hi = max(y_vals) + 0.01
    offsets = {
        "tt_matmul_single": -10.0,
        "tt_matmul_multi": 10.0,
    }

    def x_for(size: int) -> float:
        idx = sizes.index(size)
        return ml + idx * (pw / max(1, len(sizes) - 1))

    def y_for(value: float) -> float:
        frac = 0.5 if y_hi <= y_lo else (value - y_lo) / (y_hi - y_lo)
        return mt + ph - frac * ph

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2:.1f}" y="44" text-anchor="middle" font-family="{SERIF}" font-size="30" font-weight="700">SIT Summary for MatMul Sweeps</text>',
    ]
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        value = y_lo + frac * (y_hi - y_lo)
        y = y_for(value)
        svg.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml + pw}" y2="{y:.2f}" stroke="#d1d5db" stroke-dasharray="4 4"/>')
        svg.append(f'<text x="{ml - 16}" y="{y + 6:.2f}" text-anchor="end" font-family="{SERIF}" font-size="18">{value:.3f}</text>')
    for size in sizes:
        x = x_for(size)
        svg.append(f'<text x="{x:.2f}" y="{mt + ph + 38:.2f}" text-anchor="middle" font-family="{SERIF}" font-size="22">M{size}</text>')
    svg.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#111827" stroke-width="2"/>')
    svg.append(f'<line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#111827" stroke-width="2"/>')

    for workload in workloads:
        pts = sorted((row["case_num"], row["sit_median"]) for row in rows if row["workload"] == workload and row["case_num"] in sizes)
        color = COLORS[workload]
        dash = LINE_STYLES.get(workload)
        marker = MARKERS.get(workload, "circle")
        plotted = [(x_for(x) + offsets[workload], y_for(y), x, y) for x, y in pts]
        svg.append(
            '<polyline fill="none" stroke="{}" stroke-width="3"{} points="{}"/>'.format(
                color,
                f' stroke-dasharray="{dash}"' if dash else "",
                " ".join(f"{px:.2f},{py:.2f}" for px, py, _, _ in plotted),
            )
        )
        for px, py, _, _ in plotted:
            svg.append(draw_marker(px, py, color, marker, r=8.0))
    legend_x = width - 180
    legend_y = mt + 90
    for idx, workload in enumerate(workloads):
        y = legend_y + idx * 48
        color = COLORS[workload]
        dash = LINE_STYLES.get(workload)
        marker = MARKERS.get(workload, "circle")
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        svg.append(f'<line x1="{legend_x - 10}" y1="{y:.2f}" x2="{legend_x + 56}" y2="{y:.2f}" stroke="{color}" stroke-width="4"{dash_attr}/>')
        svg.append(draw_marker(legend_x + 23, y, color, marker, r=7.5))
        svg.append(f'<text x="{legend_x + 78}" y="{y + 8:.2f}" font-family="{SERIF}" font-size="22">{svg_escape(pretty_name(workload))}</text>')
    svg.extend(
        [
            f'<text x="{ml - 86}" y="{mt + ph/2:.1f}" transform="rotate(-90 {ml - 86} {mt + ph/2:.1f})" text-anchor="middle" font-family="{SERIF}" font-size="28">SIT Median</text>',
            f'<text x="{ml + pw/2:.1f}" y="{height - 18}" text-anchor="middle" font-family="{SERIF}" font-size="28">MatMul Size</text>',
            '</svg>',
        ]
    )
    out_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_ops_per_zone(rows: list[dict], out_path: Path) -> None:
    workloads = [
        "tt_matmul_single",
        "tt_custom_sfpi_smoothstep",
        "tt_sfpu_chain",
        "tt_eltwise_binary",
        "tt_custom_sfpi_add",
        "tt_eltwise_sfpu",
    ]
    data = []
    seen = set()
    for row in rows:
        workload = row["workload"]
        if workload in workloads and workload not in seen and math.isfinite(row["ops_per_zone"]):
            data.append((workload, row["ops_per_zone"]))
            seen.add(workload)
    width, height = 1080, 760
    ml, mr, mt, mb = 320, 80, 40, 80
    pw, ph = width - ml - mr, height - mt - mb
    max_v = max(v for _, v in data) * 1.08
    bar_h = ph / max(1, len(data))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="#ffffff"/>']
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        x = ml + frac * pw
        value = frac * max_v
        svg.append(f'<line x1="{x:.2f}" y1="{mt}" x2="{x:.2f}" y2="{mt + ph}" stroke="#d1d5db" stroke-dasharray="4 4"/>')
        svg.append(f'<text x="{x:.2f}" y="{mt + ph + 34:.2f}" text-anchor="middle" font-family="{SERIF}" font-size="22">{fmt_tick(value)}</text>')
    svg.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#111827" stroke-width="2"/>')
    for idx, (workload, value) in enumerate(data):
        y = mt + idx * bar_h + 18
        w = (value / max_v) * pw
        color = COLORS[workload]
        svg.append(f'<rect x="{ml}" y="{y:.2f}" width="{w:.2f}" height="{bar_h - 26:.2f}" fill="{color}"/>')
        svg.append(f'<text x="{ml - 18}" y="{y + (bar_h - 26)/2 + 10:.2f}" text-anchor="end" font-family="{SERIF}" font-size="26">{svg_escape(pretty_name(workload))}</text>')
        svg.append(f'<text x="{ml + w + 12:.2f}" y="{y + (bar_h - 26)/2 + 10:.2f}" font-family="{SERIF}" font-size="24">{int(value):,}</text>')
    svg.append(f'<text x="{ml + pw/2:.1f}" y="{height - 12}" text-anchor="middle" font-family="{SERIF}" font-size="30">Ops per Zone (--tt-ops-per-zone)</text>')
    svg.append('</svg>')
    out_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_residency_summary(rows: list[dict], out_path: Path) -> None:
    workloads = [
        "tt_matmul_single",
        "tt_matmul_multi",
        "tt_sfpu_chain",
        "tt_eltwise_sfpu",
        "tt_eltwise_binary",
        "tt_custom_sfpi_add",
        "tt_custom_sfpi_smoothstep",
    ]
    selected = []
    for workload in workloads:
        case = REPRESENTATIVE_CASES[workload]
        for row in rows:
            if row["workload"] == workload and row["case"] == case:
                selected.append(row)
                break
    width, height = 1620, 1100
    left_x, left_w = 250, 930
    right_x, right_w = 1240, 280
    mt, mb = 90, 90
    ph = height - mt - mb
    bar_h = ph / max(1, len(selected))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">', '<rect width="100%" height="100%" fill="#ffffff"/>']
    title = "TT-Wormhole Workload Residency and SIT (Representative Cases)"
    svg.append(f'<text x="{width/2:.1f}" y="46" text-anchor="middle" font-family="{SERIF}" font-size="30" font-weight="700">{svg_escape(title)}</text>')

    for frac in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        x = left_x + frac * left_w
        svg.append(f'<line x1="{x:.2f}" y1="{mt}" x2="{x:.2f}" y2="{mt + ph}" stroke="#d1d5db" stroke-dasharray="4 4"/>')
        svg.append(f'<text x="{x:.2f}" y="{mt + ph + 36:.2f}" text-anchor="middle" font-family="{SERIF}" font-size="22">{int(frac*100)}</text>')
    for frac in [0.0, 0.5, 1.0]:
        x = right_x + frac * right_w
        svg.append(f'<line x1="{x:.2f}" y1="{mt}" x2="{x:.2f}" y2="{mt + ph}" stroke="#d1d5db" stroke-dasharray="4 4"/>')
        svg.append(f'<text x="{x:.2f}" y="{mt + ph + 36:.2f}" text-anchor="middle" font-family="{SERIF}" font-size="22">{frac:.1f}</text>')

    svg.append(f'<line x1="{left_x}" y1="{mt}" x2="{left_x}" y2="{mt + ph}" stroke="#111827" stroke-width="2"/>')
    svg.append(f'<line x1="{right_x}" y1="{mt}" x2="{right_x}" y2="{mt + ph}" stroke="#111827" stroke-width="2"/>')

    for idx, row in enumerate(selected):
        y = mt + idx * bar_h + 14
        h = bar_h - 24
        label = pretty_name(row["workload"])
        if row["case"]:
            label = f"{label} ({row['case']})"
        svg.append(f'<text x="{left_x - 20}" y="{y + h/2 + 10:.2f}" text-anchor="end" font-family="{SERIF}" font-size="24">{svg_escape(label)}</text>')
        active_w = max(0.0, row["active"]) * left_w
        stall_w = max(0.0, row["stall"]) * left_w
        idle_w = max(0.0, row["idle"]) * left_w
        svg.append(f'<rect x="{left_x}" y="{y:.2f}" width="{active_w:.2f}" height="{h:.2f}" fill="#2ca02c"/>')
        svg.append(f'<rect x="{left_x + active_w:.2f}" y="{y:.2f}" width="{stall_w:.2f}" height="{h:.2f}" fill="#ff7f0e"/>')
        svg.append(f'<rect x="{left_x + active_w + stall_w:.2f}" y="{y:.2f}" width="{idle_w:.2f}" height="{h:.2f}" fill="#94b6df"/>')
        sit_w = max(0.0, row["sit_median"]) * right_w
        svg.append(f'<rect x="{right_x}" y="{y:.2f}" width="{sit_w:.2f}" height="{h:.2f}" fill="#2f7db6"/>')

    legend_y = height - 26
    svg.extend(
        [
            f'<rect x="720" y="{legend_y - 18}" width="42" height="18" fill="#2ca02c"/>',
            f'<text x="778" y="{legend_y - 2}" font-family="{SERIF}" font-size="18">Active</text>',
            f'<rect x="900" y="{legend_y - 18}" width="42" height="18" fill="#ff7f0e"/>',
            f'<text x="958" y="{legend_y - 2}" font-family="{SERIF}" font-size="18">Stall</text>',
            f'<rect x="1070" y="{legend_y - 18}" width="42" height="18" fill="#94b6df"/>',
            f'<text x="1128" y="{legend_y - 2}" font-family="{SERIF}" font-size="18">Idle</text>',
            f'<text x="{left_x + left_w/2:.1f}" y="{height - 18}" text-anchor="middle" font-family="{SERIF}" font-size="28">Residency (%)</text>',
            f'<text x="{right_x + right_w/2:.1f}" y="{height - 18}" text-anchor="middle" font-family="{SERIF}" font-size="28">SIT Median</text>',
        ]
    )
    svg.append('</svg>')
    out_path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate condensed TT summary plots.")
    ap.add_argument("--metrics-csv", required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    metrics_csv = Path(args.metrics_csv).expanduser().resolve()
    if not metrics_csv.exists():
        raise SystemExit(f"metrics csv not found: {metrics_csv}")
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (metrics_csv.parent / "plots_condensed")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(metrics_csv)
    write_tile_sit(rows, out_dir / "tt_tile_workload_sit_summary.svg")
    write_matmul_sit(rows, out_dir / "tt_matmul_sit_summary.svg")
    write_ops_per_zone(rows, out_dir / "tt_ops_per_zone_summary.svg")
    write_residency_summary(rows, out_dir / "tt_residency_sit_summary.svg")
    print(f"wrote svg: {out_dir / 'tt_tile_workload_sit_summary.svg'}")
    print(f"wrote svg: {out_dir / 'tt_matmul_sit_summary.svg'}")
    print(f"wrote svg: {out_dir / 'tt_ops_per_zone_summary.svg'}")
    print(f"wrote svg: {out_dir / 'tt_residency_sit_summary.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
