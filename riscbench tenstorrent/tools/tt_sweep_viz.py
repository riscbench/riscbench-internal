#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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

WORKLOAD_ORDER = [
    "tt_matmul_single",
    "tt_matmul_multi",
    "tt_sfpu_chain",
    "tt_eltwise_sfpu",
    "tt_eltwise_binary",
    "tt_custom_sfpi_add",
    "tt_custom_sfpi_smoothstep",
]

WORKLOAD_COLORS = {
    "tt_matmul_single": "#2563eb",
    "tt_matmul_multi": "#0f766e",
    "tt_sfpu_chain": "#7c3aed",
    "tt_eltwise_sfpu": "#16a34a",
    "tt_eltwise_binary": "#ea580c",
    "tt_custom_sfpi_add": "#db2777",
    "tt_custom_sfpi_smoothstep": "#ca8a04",
}


def workload_rank(name: str) -> tuple[int, str]:
    if name in WORKLOAD_ORDER:
        return (WORKLOAD_ORDER.index(name), name)
    return (len(WORKLOAD_ORDER), name)


def parse_float(value: str) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return float("nan")


def finite_or_nan(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return parsed if math.isfinite(parsed) else float("nan")


def case_sort_key(size: str) -> tuple[int, int]:
    raw = str(size).strip()
    match = TT_MATMUL_SIZE_RE.match(raw)
    if match:
        return (0, int(match.group(1)))
    match = TT_TILE_SIZE_RE.match(raw)
    if match:
        return (1, int(match.group(1)))
    return (9, 0)


def display_case(size: str) -> str:
    raw = str(size).strip()
    match = TT_MATMUL_SIZE_RE.match(raw)
    if match:
        return f"M{match.group(1)}"
    match = TT_TILE_SIZE_RE.match(raw)
    if match:
        return f"{match.group(1)}t"
    return raw


def pretty_workload(name: str) -> str:
    raw = str(name).strip()
    if raw.startswith("tt_"):
        raw = raw[3:]
    return raw.replace("_", " ")


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def blend_hex(start: str, end: str, t: float) -> str:
    t = clamp(t, 0.0, 1.0)
    start_rgb = tuple(int(start[i : i + 2], 16) for i in (1, 3, 5))
    end_rgb = tuple(int(end[i : i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(round(a + (b - a) * t) for a, b in zip(start_rgb, end_rgb))
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def bounds(values: list[float]) -> tuple[float, float]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return 0.0, 1.0
    lo = min(clean)
    hi = max(clean)
    if hi <= lo:
        hi = lo + 1.0
    return lo, hi


def bounds_positive(values: list[float]) -> tuple[float, float]:
    clean = [value for value in values if math.isfinite(value) and value > 0.0]
    if not clean:
        return 1.0, 10.0
    lo = min(clean)
    hi = max(clean)
    if hi <= lo:
        hi = lo * 10.0
    return lo, hi


def normalized(value: float, lo: float, hi: float, *, log_scale: bool = False) -> float | None:
    if not math.isfinite(value):
        return None
    if log_scale:
        if value <= 0.0 or lo <= 0.0 or hi <= 0.0:
            return None
        denom = math.log10(hi) - math.log10(lo)
        if denom <= 0.0:
            return 0.5
        return clamp((math.log10(value) - math.log10(lo)) / denom, 0.0, 1.0)
    if hi <= lo:
        return 0.5
    return clamp((value - lo) / (hi - lo), 0.0, 1.0)


def cell_style(
    value: float,
    lo: float,
    hi: float,
    *,
    low_color: str,
    high_color: str,
    log_scale: bool = False,
) -> tuple[str, str]:
    t = normalized(value, lo, hi, log_scale=log_scale)
    if t is None:
        return "#e2e8f0", "#475569"
    fill = blend_hex(low_color, high_color, t)
    text = "#ffffff" if t >= 0.58 else "#0f172a"
    return fill, text


def fmt(value: float, digits: int = 2) -> str:
    if not math.isfinite(value):
        return "nan"
    return f"{value:.{digits}f}"


def fmt_pct(value: float) -> str:
    if not math.isfinite(value):
        return "nan"
    return f"{100.0 * value:.1f}%"


def svg_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def load_rows(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if str(row.get("status", "")).strip() != "ok":
                continue
            summary_path = Path(str(row.get("summary_path", "")).strip()).expanduser()
            audit = {}
            if summary_path.exists():
                try:
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                    audit = summary.get("tt_work_audit") or {}
                except (OSError, json.JSONDecodeError):
                    audit = {}
            workload = str(row.get("workload", "")).strip()
            workload_size = str(row.get("workload_size", "")).strip()
            observed_overall = parse_float(row.get("overall_observed_flops_per_us", ""))
            observed_median = parse_float(row.get("observed_flops_per_us_median", ""))
            ops_per_zone = resolve_auto_ops_per_zone(workload)
            expected_zone_count = resolve_size_active_boost(workload_size)
            ideal_total_ops = (
                float(ops_per_zone) * float(expected_zone_count)
                if ops_per_zone is not None and expected_zone_count is not None
                else float("nan")
            )
            trace_zone_equivalent = finite_or_nan(audit.get("raw_effective_zone_count"))
            if not math.isfinite(trace_zone_equivalent):
                trace_zone_equivalent = finite_or_nan(audit.get("effective_zone_count"))
            raw_expected = parse_float(row.get("expected_work_rate", ""))
            raw_ratio = (
                observed_median / raw_expected
                if math.isfinite(observed_median) and math.isfinite(raw_expected) and raw_expected > 0.0
                else float("nan")
            )
            raw_sit = parse_float(row.get("sit_median", ""))
            raw_sit_p95 = parse_float(row.get("sit_p95", ""))
            out.append(
                {
                    "label": str(row.get("label", "")).strip(),
                    "workload": workload,
                    "workload_size": workload_size,
                    "case": display_case(workload_size),
                    "observed_flops_per_us": observed_median,
                    "overall_observed_flops_per_us": observed_overall,
                    "observed_flops_per_us_median": observed_median,
                    "active": parse_float(row.get("residency_active_avg", "")),
                    "idle": parse_float(row.get("residency_idle_avg", "")),
                    "stall": parse_float(row.get("residency_stall_avg", "")),
                    "resident_windows": parse_float(row.get("resident_windows_total", "")),
                    "windows_total": parse_float(row.get("windows_total", "")),
                    "summary_path": str(summary_path),
                    "expected_work_rate": raw_expected,
                    "observed_vs_expected": raw_ratio,
                    "sit_median": raw_sit,
                    "sit_p95": raw_sit_p95,
                    "ops_per_zone": float(ops_per_zone) if ops_per_zone is not None else float("nan"),
                    "expected_zone_count": float(expected_zone_count) if expected_zone_count is not None else float("nan"),
                    "ideal_total_ops": ideal_total_ops,
                    "trace_zone_equivalent": trace_zone_equivalent,
                }
            )

    out.sort(key=lambda row: (workload_rank(row["workload"]), case_sort_key(row["workload_size"])))
    return out


def write_metrics_table(rows: list[dict], path: Path) -> None:
    fieldnames = [
        "workload",
        "case",
        "workload_size",
        "ops_per_zone",
        "expected_zone_count",
        "trace_zone_equivalent",
        "ideal_total_ops",
        "observed_flops_per_us",
        "observed_flops_per_us_median",
        "overall_observed_flops_per_us",
        "expected_work_rate",
        "observed_vs_expected",
        "sit_median",
        "sit_p95",
        "active",
        "stall",
        "idle",
        "resident_windows",
        "windows_total",
        "summary_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_heatmap_svg(rows: list[dict], path: Path) -> None:
    row_h = 42
    left = 34
    top = 128
    label_w = 250
    cols = [
        ("Obs FLOPs/us", "observed_flops_per_us", "#dbeafe", "#1d4ed8", True, lambda v: fmt(v, 1)),
        ("Expected", "expected_work_rate", "#ecfccb", "#3f6212", True, lambda v: fmt(v, 1)),
        ("Obs/Exp", "observed_vs_expected", "#fef3c7", "#c2410c", False, lambda v: fmt(v, 2)),
        ("SIT", "sit_median", "#cffafe", "#0f766e", False, lambda v: fmt(v, 3)),
        ("Active", "active", "#dcfce7", "#15803d", False, fmt_pct),
        ("Stall", "stall", "#fee2e2", "#dc2626", False, fmt_pct),
        ("Idle", "idle", "#e2e8f0", "#475569", False, fmt_pct),
        ("Res Win", "resident_windows", "#ede9fe", "#7c3aed", False, lambda v: fmt(v, 0)),
    ]
    col_w = 110
    width = left + label_w + (len(cols) * col_w) + 36
    height = top + (len(rows) * row_h) + 42
    values_by_key = {
        key: [float(row[key]) for row in rows]
        for _, key, *_ in cols
    }
    ranges = {}
    for _, key, _, _, log_scale, _ in cols:
        ranges[key] = bounds_positive(values_by_key[key]) if log_scale else bounds(values_by_key[key])

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="{left}" y="42" font-size="24" font-weight="700" fill="#0f172a">TT Sweep Metrics Heatmap</text>',
        f'<text x="{left}" y="66" font-size="13" fill="#475569">Expected uses the TT workload formula: ops_per_zone × expected zone count divided by the run&apos;s residency envelope time.</text>',
        f'<text x="{left}" y="90" font-size="12" fill="#64748b">Obs FLOPs/us uses the per-core median observed window rate so the ratio is not the tautological overall normalized total. Zone counts are exported in the CSV table.</text>',
        f'<text x="{left}" y="114" font-size="11" font-weight="700" fill="#334155">WORKLOAD / CASE</text>',
    ]
    for col_idx, (title, _, _, _, _, _) in enumerate(cols):
        x = left + label_w + (col_idx * col_w)
        svg.append(f'<text x="{x + (col_w / 2):.2f}" y="114" text-anchor="middle" font-size="11" font-weight="700" fill="#334155">{svg_escape(title)}</text>')

    for idx, row in enumerate(rows):
        y = top + (idx * row_h)
        cy = y + (row_h / 2.0)
        if idx % 2 == 0:
            svg.append(f'<rect x="{left - 8}" y="{y + 4}" width="{width - (2 * left) + 16}" height="{row_h - 8}" rx="14" fill="#ffffff"/>')
        workload = pretty_workload(row["workload"])
        fill = WORKLOAD_COLORS.get(row["workload"], "#334155")
        svg.append(f'<circle cx="{left + 10}" cy="{cy - 1:.2f}" r="6" fill="{fill}"/>')
        svg.append(f'<text x="{left + 24}" y="{cy + 4:.2f}" font-size="13" font-weight="700" fill="#0f172a">{svg_escape(workload)} / {svg_escape(row["case"])}</text>')
        for col_idx, (_, key, low_color, high_color, log_scale, formatter) in enumerate(cols):
            value = float(row[key])
            lo, hi = ranges[key]
            cell_x = left + label_w + (col_idx * col_w)
            fill_color, text_fill = cell_style(value, lo, hi, low_color=low_color, high_color=high_color, log_scale=log_scale)
            svg.append(f'<rect x="{cell_x + 6}" y="{y + 8}" width="{col_w - 12}" height="{row_h - 16}" rx="10" fill="{fill_color}"/>')
            svg.append(f'<text x="{cell_x + (col_w / 2):.2f}" y="{cy + 4:.2f}" text-anchor="middle" font-size="12" font-weight="700" fill="{text_fill}">{svg_escape(formatter(value))}</text>')
    svg.append("</svg>")
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_throughput_svg(rows: list[dict], path: Path) -> None:
    labels = [f'{pretty_workload(row["workload"])} {row["case"]}' for row in rows]
    values = [float(row["observed_flops_per_us"]) for row in rows]
    lo, hi = bounds_positive(values)
    width = max(1300, 90 + (len(rows) * 52))
    height = 620
    ml, mr, mt, mb = 80, 40, 70, 170
    pw = width - ml - mr
    ph = height - mt - mb

    def x_for(idx: int) -> float:
        step = pw / max(1, len(rows))
        return ml + (idx * step) + 10

    def bar_w() -> float:
        return max(16.0, (pw / max(1, len(rows))) - 20.0)

    def y_for(value: float) -> float:
        t = normalized(value, lo, hi, log_scale=True)
        if t is None:
            t = 0.0
        return mt + ph - (t * ph)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2:.1f}" y="34" text-anchor="middle" font-size="24" font-weight="700" fill="#0f172a">Observed FLOPs/us Across TT Sweep Cases</text>',
        f'<text x="{width/2:.1f}" y="56" text-anchor="middle" font-size="12" fill="#475569">Log-scaled bars help the small tile runs and large matmul runs stay visible on the same chart.</text>',
        f'<line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#0f172a"/>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#0f172a"/>',
    ]

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        value = 10 ** (math.log10(lo) + frac * (math.log10(hi) - math.log10(lo)))
        y = mt + ph - (frac * ph)
        svg.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml + pw}" y2="{y:.2f}" stroke="#e2e8f0"/>')
        svg.append(f'<text x="{ml - 8}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#475569">{svg_escape(fmt(value, 1))}</text>')

    bw = bar_w()
    for idx, row in enumerate(rows):
        value = float(row["observed_flops_per_us"])
        x = x_for(idx)
        y = y_for(value)
        h = (mt + ph) - y
        fill = WORKLOAD_COLORS.get(row["workload"], "#334155")
        svg.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{h:.2f}" rx="8" fill="{fill}"/>')
        svg.append(f'<text x="{x + (bw/2):.2f}" y="{y - 8:.2f}" text-anchor="middle" font-size="10" fill="#334155">{svg_escape(fmt(value, 1))}</text>')
        svg.append(
            f'<text x="{x + (bw/2):.2f}" y="{mt + ph + 14:.2f}" text-anchor="middle" font-size="10" fill="#334155" transform="rotate(28 {x + (bw/2):.2f} {mt + ph + 14:.2f})">{svg_escape(labels[idx])}</text>'
        )

    svg.append(f'<text x="24" y="{mt + ph/2:.1f}" transform="rotate(-90 24 {mt + ph/2:.1f})" text-anchor="middle" font-size="13" fill="#0f172a">Observed FLOPs/us (log scale)</text>')
    svg.append("</svg>")
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_residency_svg(rows: list[dict], path: Path) -> None:
    width = max(1220, 140 + (len(rows) * 44))
    height = 520
    ml, mr, mt, mb = 80, 40, 70, 150
    pw = width - ml - mr
    ph = height - mt - mb
    step = pw / max(1, len(rows))
    bar_w = max(14.0, step - 16.0)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2:.1f}" y="34" text-anchor="middle" font-size="24" font-weight="700" fill="#0f172a">Residency Mix By TT Sweep Case</text>',
        f'<text x="{width/2:.1f}" y="56" text-anchor="middle" font-size="12" fill="#475569">Stacked bars show active, stall, and idle fractions for each successful sweep run.</text>',
        f'<line x1="{ml}" y1="{mt + ph}" x2="{ml + pw}" y2="{mt + ph}" stroke="#0f172a"/>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ph}" stroke="#0f172a"/>',
    ]

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = mt + ph - (frac * ph)
        svg.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml + pw}" y2="{y:.2f}" stroke="#e2e8f0"/>')
        svg.append(f'<text x="{ml - 8}" y="{y + 4:.2f}" text-anchor="end" font-size="11" fill="#475569">{frac * 100:.0f}%</text>')

    for idx, row in enumerate(rows):
        x = ml + (idx * step) + 8
        base_y = mt + ph
        segments = [
            ("idle", "#94a3b8"),
            ("stall", "#f59e0b"),
            ("active", "#22c55e"),
        ]
        for key, color in segments:
            frac = clamp(float(row[key]), 0.0, 1.0) if math.isfinite(float(row[key])) else 0.0
            h = frac * ph
            y = base_y - h
            if h > 0.0:
                svg.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{h:.2f}" fill="{color}"/>')
            base_y = y
        label = f'{pretty_workload(row["workload"])} {row["case"]}'
        svg.append(
            f'<text x="{x + (bar_w/2):.2f}" y="{mt + ph + 14:.2f}" text-anchor="middle" font-size="10" fill="#334155" transform="rotate(28 {x + (bar_w/2):.2f} {mt + ph + 14:.2f})">{svg_escape(label)}</text>'
        )

    legend_y = 26
    svg.extend(
        [
            f'<rect x="{width - 290}" y="{legend_y}" width="14" height="14" fill="#22c55e"/>',
            f'<text x="{width - 270}" y="{legend_y + 12}" font-size="11" fill="#334155">Active</text>',
            f'<rect x="{width - 210}" y="{legend_y}" width="14" height="14" fill="#f59e0b"/>',
            f'<text x="{width - 190}" y="{legend_y + 12}" font-size="11" fill="#334155">Stall</text>',
            f'<rect x="{width - 130}" y="{legend_y}" width="14" height="14" fill="#94a3b8"/>',
            f'<text x="{width - 110}" y="{legend_y + 12}" font-size="11" fill="#334155">Idle</text>',
        ]
    )
    svg.append("</svg>")
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate SVG plots from TT sweep comparison_rows.csv.")
    ap.add_argument("--rows-csv", required=True)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    rows_csv = Path(args.rows_csv).expanduser().resolve()
    if not rows_csv.exists():
        raise SystemExit(f"rows csv not found: {rows_csv}")
    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (rows_csv.parent / "plots")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(rows_csv)
    if not rows:
        raise SystemExit(f"no successful rows found in: {rows_csv}")

    write_metrics_table(rows, out_dir / "tt_sweep_metrics_table.csv")
    write_heatmap_svg(rows, out_dir / "tt_sweep_heatmap.svg")
    write_throughput_svg(rows, out_dir / "tt_sweep_observed_flops.svg")
    write_residency_svg(rows, out_dir / "tt_sweep_residency_mix.svg")

    print(f"wrote table: {out_dir / 'tt_sweep_metrics_table.csv'}")
    print(f"wrote svg: {out_dir / 'tt_sweep_heatmap.svg'}")
    print(f"wrote svg: {out_dir / 'tt_sweep_observed_flops.svg'}")
    print(f"wrote svg: {out_dir / 'tt_sweep_residency_mix.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
