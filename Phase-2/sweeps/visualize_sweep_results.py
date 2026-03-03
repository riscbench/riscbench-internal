#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


METRIC_PATTERNS = {
    "sit_median": re.compile(r"sit_median\s+([0-9.]+|nan)", re.IGNORECASE),
    "sit_p95": re.compile(r"sit_p95\s+([0-9.]+|nan)", re.IGNORECASE),
    "residency_idle": re.compile(r"residency_idle\s+([0-9.]+)%", re.IGNORECASE),
    "residency_stall": re.compile(r"residency_stall\s+([0-9.]+)%", re.IGNORECASE),
}

COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
]

DEFAULT_WORKLOAD_SIZE_ORDER = ["test", "tiny", "small", "med", "large"]
FLAG_MODE_ORDER = {"none": 0, "branch_mispredict": 1, "cache_pressure": 2, "both": 3}


def to_float(raw: str | None) -> float:
    if raw is None:
        return float("nan")
    v = raw.strip()
    if not v:
        return float("nan")
    if v.lower() == "nan":
        return float("nan")
    try:
        return float(v)
    except ValueError:
        return float("nan")


def to_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    v = raw.strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def derive_flag_mode(row: Dict[str, str]) -> str:
    branch = to_bool(row.get("branch_mispredict"))
    cache = to_bool(row.get("cache_pressure"))
    if branch and cache:
        return "both"
    if branch:
        return "branch_mispredict"
    if cache:
        return "cache_pressure"
    return "none"


def load_sweep_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_case_metrics(case_log: Path) -> Dict[str, float]:
    out: Dict[str, float] = {k: float("nan") for k in METRIC_PATTERNS}
    if not case_log.exists():
        return out
    text = case_log.read_text(encoding="utf-8", errors="ignore")
    for key, pattern in METRIC_PATTERNS.items():
        m = pattern.search(text)
        if not m:
            continue
        raw = m.group(1)
        try:
            out[key] = float(raw)
        except ValueError:
            out[key] = float("nan")
    return out


def merge_rows(rows: List[Dict[str, str]], results_dir: Path) -> List[Dict[str, str]]:
    merged: List[Dict[str, str]] = []
    for row in rows:
        case_id = int(row["case_id"])
        case_log = results_dir / f"case_{case_id:04d}.log"
        metrics = parse_case_metrics(case_log)
        out = dict(row)
        for k, v in metrics.items():
            out[k] = "" if math.isnan(v) else f"{v:.6f}"
        out["flag_mode"] = derive_flag_mode(out)
        merged.append(out)
    return merged


def write_csv(rows: List[Dict[str, str]], out_path: Path) -> None:
    if not rows:
        return
    fieldnames = sorted({k for r in rows for k in r.keys()})
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _ticks(vmin: float, vmax: float, n: int = 5) -> List[float]:
    if vmin == vmax:
        return [vmin]
    step = (vmax - vmin) / float(max(1, n - 1))
    return [vmin + i * step for i in range(n)]


def _line_chart_svg(
    out_path: Path,
    title: str,
    x_label: str,
    y_label: str,
    series: Dict[str, List[Tuple[float, float]]],
) -> None:
    valid_series = {}
    for name, pts in series.items():
        pts2 = sorted([(x, y) for x, y in pts if math.isfinite(x) and math.isfinite(y)], key=lambda p: p[0])
        if pts2:
            valid_series[name] = pts2

    if not valid_series:
        return

    all_x = [x for pts in valid_series.values() for x, _ in pts]
    all_y = [y for pts in valid_series.values() for _, y in pts]
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    if xmin == xmax:
        xmax = xmin + 1.0
    if ymin == ymax:
        ymax = ymin + 1.0

    W, H = 920, 520
    ml, mr, mt, mb = 80, 220, 40, 70
    pw, ph = W - ml - mr, H - mt - mb

    def sx(x: float) -> float:
        return ml + ((x - xmin) / (xmax - xmin)) * pw

    def sy(y: float) -> float:
        return mt + ph - ((y - ymin) / (ymax - ymin)) * ph

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">')
    lines.append('<rect width="100%" height="100%" fill="white"/>')
    lines.append(f'<text x="{W/2:.1f}" y="24" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>')

    # Axes
    lines.append(f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#222"/>')
    lines.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#222"/>')

    # Grid + ticks
    for t in _ticks(xmin, xmax):
        x = sx(t)
        lines.append(f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt+ph}" stroke="#eee"/>')
        lines.append(f'<line x1="{x:.1f}" y1="{mt+ph}" x2="{x:.1f}" y2="{mt+ph+5}" stroke="#222"/>')
        lines.append(f'<text x="{x:.1f}" y="{mt+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="11">{t:.2f}</text>')

    for t in _ticks(ymin, ymax):
        y = sy(t)
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" stroke="#eee"/>')
        lines.append(f'<line x1="{ml-5}" y1="{y:.1f}" x2="{ml}" y2="{y:.1f}" stroke="#222"/>')
        lines.append(f'<text x="{ml-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{t:.3f}</text>')

    # Series
    legend_y = mt + 20
    for idx, (name, pts) in enumerate(valid_series.items()):
        color = COLORS[idx % len(COLORS)]
        poly = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{poly}"/>')
        for x, y in pts:
            lines.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.5" fill="{color}"/>')

        ly = legend_y + idx * 22
        lx = ml + pw + 20
        lines.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+24}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{lx+30}" y="{ly+4}" font-family="sans-serif" font-size="12">{name}</text>')

    lines.append(f'<text x="{ml + pw/2:.1f}" y="{H-24}" text-anchor="middle" font-family="sans-serif" font-size="13">{x_label}</text>')
    lines.append(
        f'<text x="24" y="{mt + ph/2:.1f}" transform="rotate(-90 24 {mt + ph/2:.1f})" '
        f'text-anchor="middle" font-family="sans-serif" font-size="13">{y_label}</text>'
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _categorical_line_chart_svg(
    out_path: Path,
    title: str,
    x_label: str,
    y_label: str,
    x_labels: List[str],
    series: Dict[str, List[Tuple[str, float]]],
) -> None:
    valid_series: Dict[str, List[Tuple[str, float]]] = {}
    x_map = {name: i for i, name in enumerate(x_labels)}
    for name, pts in series.items():
        pts2 = [(x, y) for x, y in pts if x in x_map and math.isfinite(y)]
        if pts2:
            valid_series[name] = sorted(pts2, key=lambda p: x_map[p[0]])

    if not valid_series:
        return

    all_y = [y for pts in valid_series.values() for _, y in pts]
    ymin, ymax = min(all_y), max(all_y)
    if ymin == ymax:
        ymax = ymin + 1.0

    W, H = 980, 560
    ml, mr, mt, mb = 80, 260, 44, 90
    pw, ph = W - ml - mr, H - mt - mb

    step = pw / max(1, len(x_labels) - 1) if len(x_labels) > 1 else 1.0

    def sx(label: str) -> float:
        idx = x_map[label]
        if len(x_labels) == 1:
            return ml + pw / 2.0
        return ml + idx * step

    def sy(v: float) -> float:
        return mt + ph - ((v - ymin) / (ymax - ymin)) * ph

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{W/2:.1f}" y="24" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>',
        f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#222"/>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#222"/>',
    ]

    for i in range(5):
        t = ymin + (ymax - ymin) * (i / 4.0)
        y = sy(t)
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" stroke="#eee"/>')
        lines.append(f'<text x="{ml-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{t:.3f}</text>')

    for xl in x_labels:
        x = sx(xl)
        lines.append(f'<line x1="{x:.1f}" y1="{mt+ph}" x2="{x:.1f}" y2="{mt+ph+5}" stroke="#222"/>')
        lines.append(
            f'<text x="{x:.1f}" y="{mt+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="11" '
            f'transform="rotate(20 {x:.1f} {mt+ph+22})">{xl}</text>'
        )

    legend_x = ml + pw + 20
    legend_y = mt + 24
    for idx, (name, pts) in enumerate(valid_series.items()):
        color = COLORS[idx % len(COLORS)]
        poly = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{poly}"/>')
        for x, y in pts:
            lines.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.8" fill="{color}"/>')

        ly = legend_y + idx * 22
        lines.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x+24}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        lines.append(f'<text x="{legend_x+30}" y="{ly+4}" font-family="sans-serif" font-size="12">{name}</text>')

    lines.append(f'<text x="{ml + pw/2:.1f}" y="{H-18}" text-anchor="middle" font-family="sans-serif" font-size="13">{x_label}</text>')
    lines.append(
        f'<text x="24" y="{mt + ph/2:.1f}" transform="rotate(-90 24 {mt + ph/2:.1f})" '
        f'text-anchor="middle" font-family="sans-serif" font-size="13">{y_label}</text>'
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _pass_fail_svg(out_path: Path, pass_count: int, fail_count: int) -> None:
    total = max(1, pass_count + fail_count)
    pass_frac = pass_count / total
    W, H = 520, 260
    x0, y0, bw, bh = 80, 90, 360, 40
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="260" y="28" text-anchor="middle" font-family="sans-serif" font-size="18">Sweep Pass/Fail</text>',
        f'<rect x="{x0}" y="{y0}" width="{bw}" height="{bh}" fill="#f2f2f2" stroke="#888"/>',
        f'<rect x="{x0}" y="{y0}" width="{bw*pass_frac:.1f}" height="{bh}" fill="#2ca02c"/>',
        f'<text x="{x0}" y="{y0-10}" font-family="sans-serif" font-size="12">pass: {pass_count}</text>',
        f'<text x="{x0+140}" y="{y0-10}" font-family="sans-serif" font-size="12">fail: {fail_count}</text>',
        f'<text x="{x0+bw/2}" y="{y0+bh+24}" text-anchor="middle" font-family="sans-serif" font-size="12">pass rate: {100*pass_frac:.1f}%</text>',
        "</svg>",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_series(
    rows: List[Dict[str, str]],
    x_field: str,
    y_field: str,
    group_field: str,
) -> Dict[str, List[Tuple[float, float]]]:
    grouped: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    for row in rows:
        x = to_float(row.get(x_field))
        y = to_float(row.get(y_field))
        if not (math.isfinite(x) and math.isfinite(y)):
            continue
        g = row.get(group_field, "") or "all"
        grouped[g].append((x, y))
    return grouped


def parse_order(raw: str | None) -> List[str]:
    if raw is None:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def build_categorical_mean_series(
    rows: List[Dict[str, str]],
    x_field: str,
    y_field: str,
    group_field: str,
    preferred_order: List[str] | None = None,
) -> Tuple[List[str], Dict[str, List[Tuple[str, float]]]]:
    preferred_order = preferred_order or []
    present_categories: set[str] = set()
    grouped: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    for row in rows:
        x = (row.get(x_field, "") or "").strip()
        y = to_float(row.get(y_field))
        g = (row.get(group_field, "") or "all").strip()
        if not x or not g or not math.isfinite(y):
            continue
        present_categories.add(x)
        grouped[g][x].append(y)

    ordered: List[str] = [x for x in preferred_order if x in present_categories]
    leftovers = sorted(present_categories - set(ordered))
    ordered.extend(leftovers)
    if not ordered:
        return ([], {})

    series: Dict[str, List[Tuple[str, float]]] = {}
    sorted_groups = sorted(grouped.keys(), key=lambda k: (FLAG_MODE_ORDER.get(k, 999), k))
    for g in sorted_groups:
        pts: List[Tuple[str, float]] = []
        for x in ordered:
            vals = grouped[g].get(x, [])
            if vals:
                pts.append((x, sum(vals) / float(len(vals))))
        if pts:
            series[g] = pts
    return (ordered, series)


def main() -> int:
    ap = argparse.ArgumentParser(description="Visualize sweep_results.csv and case logs.")
    ap.add_argument("--results-dir", required=True, help="Phase-2/sweeps/results/<timestamp> directory")
    ap.add_argument("--x-field", default="time_us", help="X axis field from sweep_results.csv")
    ap.add_argument("--group-field", default="workload", help="Grouping field for series")
    ap.add_argument(
        "--workload-size-order",
        default="test,tiny,small,med,large",
        help="Order for workload_size categorical charts (comma-separated)",
    )
    ap.add_argument("--workload-filter", default=None, help="Optional workload name for common SIT chart")
    ap.add_argument("--out-dir", default=None, help="Output dir (default: <results-dir>/plots)")
    args = ap.parse_args()

    results_dir = Path(args.results_dir).resolve()
    sweep_csv = results_dir / "sweep_results.csv"
    if not sweep_csv.exists():
        raise SystemExit(f"sweep_results.csv not found in {results_dir}")

    rows = load_sweep_rows(sweep_csv)
    merged = merge_rows(rows, results_dir)

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (results_dir / "plots")
    out_dir.mkdir(parents=True, exist_ok=True)

    merged_csv = out_dir / "sweep_results_with_metrics.csv"
    write_csv(merged, merged_csv)

    # Charts
    elapsed_series = build_series(merged, args.x_field, "elapsed_s", args.group_field)
    _line_chart_svg(
        out_dir / "elapsed_vs_x.svg",
        "Sweep Runtime",
        args.x_field,
        "elapsed_s",
        elapsed_series,
    )

    sit_median_series = build_series(merged, args.x_field, "sit_median", args.group_field)
    _line_chart_svg(
        out_dir / "sit_median_vs_x.svg",
        "SIT Median",
        args.x_field,
        "sit_median",
        sit_median_series,
    )

    sit_p95_series = build_series(merged, args.x_field, "sit_p95", args.group_field)
    _line_chart_svg(
        out_dir / "sit_p95_vs_x.svg",
        "SIT P95",
        args.x_field,
        "sit_p95",
        sit_p95_series,
    )

    pass_count = sum(1 for r in merged if int(to_float(r.get("returncode"))) == 0)
    fail_count = len(merged) - pass_count
    _pass_fail_svg(out_dir / "pass_fail.svg", pass_count, fail_count)

    common_rows = merged
    if args.workload_filter:
        common_rows = [r for r in merged if (r.get("workload", "") == args.workload_filter)]
    size_order = parse_order(args.workload_size_order) or list(DEFAULT_WORKLOAD_SIZE_ORDER)
    x_labels, sit_common_series = build_categorical_mean_series(
        common_rows,
        x_field="workload_size",
        y_field="sit_median",
        group_field="flag_mode",
        preferred_order=size_order,
    )
    if x_labels and sit_common_series:
        title = "Common SIT Median" if not args.workload_filter else f"Common SIT Median - {args.workload_filter}"
        _categorical_line_chart_svg(
            out_dir / "common_sit_median_by_workload_size.svg",
            title,
            "workload_size",
            "sit_median",
            x_labels,
            sit_common_series,
        )
        summary_rows: List[Dict[str, str]] = []
        for group_name in sorted(sit_common_series.keys(), key=lambda k: (FLAG_MODE_ORDER.get(k, 999), k)):
            values_by_size = {x: y for x, y in sit_common_series[group_name]}
            for sz in x_labels:
                y = values_by_size.get(sz)
                if y is None:
                    continue
                summary_rows.append(
                    {
                        "group": group_name,
                        "workload_size": sz,
                        "sit_median_mean": f"{y:.6f}",
                    }
                )
        write_csv(summary_rows, out_dir / "common_sit_median_by_workload_size.csv")

    print(f"Wrote: {merged_csv}")
    for name in [
        "elapsed_vs_x.svg",
        "sit_median_vs_x.svg",
        "sit_p95_vs_x.svg",
        "pass_fail.svg",
        "common_sit_median_by_workload_size.svg",
    ]:
        p = out_dir / name
        if p.exists():
            print(f"Wrote: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
