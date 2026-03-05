#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

FLAG_ORDER = ["none", "branch_mispredict", "cache_pressure", "both"]
FLAG_LABEL = {
    "none": "none",
    "branch_mispredict": "branch_mispredict",
    "cache_pressure": "cache_pressure",
    "both": "both",
}
PLATFORM_ORDER = ["qemu", "spike", "gem5"]
PLATFORM_LABEL = {
    "qemu": "QEMU",
    "spike": "Spike",
    "gem5": "gem5",
}
PLATFORM_COLORS = {
    "qemu": "#1f77b4",
    "spike": "#d62728",
    "gem5": "#2ca02c",
}


def to_float(raw: str | None) -> float:
    if raw is None:
        return float("nan")
    text = str(raw).strip()
    if not text:
        return float("nan")
    if text.lower() == "nan":
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def to_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def derive_flag_mode(row: Dict[str, str]) -> str:
    explicit = (row.get("flag_mode") or "").strip()
    if explicit:
        return explicit
    bm = to_bool(row.get("branch_mispredict"))
    cp = to_bool(row.get("cache_pressure"))
    if bm and cp:
        return "both"
    if bm:
        return "branch_mispredict"
    if cp:
        return "cache_pressure"
    return "none"


def load_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out: List[Dict[str, str]] = []
    for row in rows:
        r = dict(row)
        r["flag_mode"] = derive_flag_mode(r)
        out.append(r)
    return out


def workload_keys(rows: List[Dict[str, str]]) -> set[Tuple[str, str]]:
    keys: set[Tuple[str, str]] = set()
    for r in rows:
        workload = (r.get("workload") or "").strip()
        workload_size = (r.get("workload_size") or "").strip()
        if workload and workload_size:
            keys.add((workload, workload_size))
    return keys


def mean(values: List[float]) -> float:
    if not values:
        return float("nan")
    return sum(values) / float(len(values))


def write_csv(rows: List[Dict[str, str]], out_path: Path) -> None:
    if not rows:
        return
    fieldnames = [
        "platform",
        "platform_label",
        "flag_mode",
        "cases",
        "sit_median_mean",
        "residency_stall_mean",
        "sit_drop_vs_none",
        "stall_rise_vs_none",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def approx_text_width_px(text: str, font_size: int = 12) -> int:
    return int(math.ceil(len(text) * font_size * 0.62))


def line_chart_svg(
    out_path: Path,
    title: str,
    x_label: str,
    y_label: str,
    categories: List[str],
    series: Dict[str, List[Tuple[str, float]]],
) -> None:
    valid_series: Dict[str, List[Tuple[str, float]]] = {}
    cat_index = {c: i for i, c in enumerate(categories)}
    for platform, pts in series.items():
        pts2 = [(c, y) for c, y in pts if c in cat_index and math.isfinite(y)]
        if pts2:
            valid_series[platform] = sorted(pts2, key=lambda item: cat_index[item[0]])
    if not valid_series:
        return

    y_vals = [y for pts in valid_series.values() for _, y in pts]
    ymin = min(y_vals)
    ymax = max(y_vals)
    if ymin == ymax:
        ymax = ymin + 1.0

    height = 560
    margin_left, margin_top, margin_bottom = 90, 44, 110
    plot_w = 680
    legend_w = max(180, 70 + max(approx_text_width_px(PLATFORM_LABEL.get(p, p)) for p in valid_series))
    width = margin_left + plot_w + legend_w + 30
    plot_h = height - margin_top - margin_bottom

    step = plot_w / max(1, len(categories) - 1) if len(categories) > 1 else 1.0

    def sx(cat: str) -> float:
        idx = cat_index[cat]
        if len(categories) == 1:
            return margin_left + plot_w / 2.0
        return margin_left + idx * step

    def sy(v: float) -> float:
        return margin_top + plot_h - ((v - ymin) / (ymax - ymin)) * plot_h

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2:.1f}" y="24" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>',
        f'<line x1="{margin_left}" y1="{margin_top+plot_h}" x2="{margin_left+plot_w}" y2="{margin_top+plot_h}" stroke="#222"/>',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}" stroke="#222"/>',
    ]

    for i in range(5):
        t = ymin + (ymax - ymin) * (i / 4.0)
        y = sy(t)
        lines.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left+plot_w}" y2="{y:.1f}" stroke="#eee"/>'
        )
        lines.append(
            f'<text x="{margin_left-10}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{t:.3f}</text>'
        )

    for cat in categories:
        x = sx(cat)
        lines.append(f'<line x1="{x:.1f}" y1="{margin_top+plot_h}" x2="{x:.1f}" y2="{margin_top+plot_h+5}" stroke="#222"/>')
        lines.append(
            f'<text x="{x:.1f}" y="{margin_top+plot_h+24}" text-anchor="middle" font-family="sans-serif" font-size="11" '
            f'transform="rotate(18 {x:.1f} {margin_top+plot_h+24})">{FLAG_LABEL.get(cat, cat)}</text>'
        )

    legend_x = margin_left + plot_w + 20
    legend_y = margin_top + 24
    for idx, platform in enumerate(PLATFORM_ORDER):
        pts = valid_series.get(platform)
        if not pts:
            continue
        color = PLATFORM_COLORS.get(platform, "#555555")
        poly = " ".join(f"{sx(cat):.1f},{sy(val):.1f}" for cat, val in pts)
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.4" points="{poly}"/>')
        for cat, val in pts:
            lines.append(f'<circle cx="{sx(cat):.1f}" cy="{sy(val):.1f}" r="4.0" fill="{color}"/>')
        ly = legend_y + idx * 24
        lines.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x+24}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        lines.append(
            f'<text x="{legend_x+30}" y="{ly+4}" font-family="sans-serif" font-size="12">{PLATFORM_LABEL.get(platform, platform)}</text>'
        )

    lines.append(
        f'<text x="{margin_left + plot_w / 2:.1f}" y="{height-20}" text-anchor="middle" font-family="sans-serif" font-size="13">{x_label}</text>'
    )
    lines.append(
        f'<text x="26" y="{margin_top + plot_h / 2:.1f}" transform="rotate(-90 26 {margin_top + plot_h / 2:.1f})" '
        f'text-anchor="middle" font-family="sans-serif" font-size="13">{y_label}</text>'
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build cross-platform flag comparison graphs for pinned sweep bundles.")
    ap.add_argument(
        "--qemu-csv",
        default="sweeps/pinned/qemu_exec_reduced_matrix_20260304_v3/plots/sweep_results_with_metrics.csv",
    )
    ap.add_argument(
        "--spike-csv",
        default="sweeps/pinned/spike_exec_reduced_matrix_20260304_v4/plots/sweep_results_with_metrics.csv",
    )
    ap.add_argument(
        "--gem5-csv",
        default="sweeps/pinned/gem5_exec_reduced_matrix_20260304_v2/plots/sweep_results_with_metrics.csv",
    )
    ap.add_argument("--out-dir", default="docs/platforms/plots")
    args = ap.parse_args()

    csv_paths = {
        "qemu": Path(args.qemu_csv).resolve(),
        "spike": Path(args.spike_csv).resolve(),
        "gem5": Path(args.gem5_csv).resolve(),
    }
    for path in csv_paths.values():
        if not path.exists():
            raise SystemExit(f"missing input csv: {path}")

    platform_rows = {platform: load_rows(path) for platform, path in csv_paths.items()}
    key_sets = [workload_keys(rows) for rows in platform_rows.values()]
    common_keys = set.intersection(*key_sets) if key_sets else set()

    filtered_rows: Dict[str, List[Dict[str, str]]] = {}
    for platform, rows in platform_rows.items():
        if common_keys:
            filtered_rows[platform] = [
                r
                for r in rows
                if ((r.get("workload") or "").strip(), (r.get("workload_size") or "").strip()) in common_keys
            ]
        else:
            filtered_rows[platform] = list(rows)

    values: Dict[Tuple[str, str], Dict[str, List[float]]] = {}
    for platform, rows in filtered_rows.items():
        for flag in FLAG_ORDER:
            values[(platform, flag)] = {"sit_median": [], "residency_stall": []}
        for row in rows:
            flag = (row.get("flag_mode") or "").strip()
            if flag not in FLAG_ORDER:
                continue
            sit = to_float(row.get("sit_median"))
            stall = to_float(row.get("residency_stall"))
            if math.isfinite(sit):
                values[(platform, flag)]["sit_median"].append(sit)
            if math.isfinite(stall):
                values[(platform, flag)]["residency_stall"].append(stall)

    summary_rows: List[Dict[str, str]] = []
    for platform in PLATFORM_ORDER:
        base_sit = mean(values[(platform, "none")]["sit_median"])
        base_stall = mean(values[(platform, "none")]["residency_stall"])
        for flag in FLAG_ORDER:
            sit_avg = mean(values[(platform, flag)]["sit_median"])
            stall_avg = mean(values[(platform, flag)]["residency_stall"])
            sit_drop = base_sit - sit_avg if math.isfinite(base_sit) and math.isfinite(sit_avg) else float("nan")
            stall_rise = stall_avg - base_stall if math.isfinite(base_stall) and math.isfinite(stall_avg) else float("nan")
            summary_rows.append(
                {
                    "platform": platform,
                    "platform_label": PLATFORM_LABEL.get(platform, platform),
                    "flag_mode": flag,
                    "cases": str(len(values[(platform, flag)]["sit_median"])),
                    "sit_median_mean": f"{sit_avg:.6f}" if math.isfinite(sit_avg) else "",
                    "residency_stall_mean": f"{stall_avg:.6f}" if math.isfinite(stall_avg) else "",
                    "sit_drop_vs_none": f"{sit_drop:.6f}" if math.isfinite(sit_drop) else "",
                    "stall_rise_vs_none": f"{stall_rise:.6f}" if math.isfinite(stall_rise) else "",
                }
            )

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = out_dir / "platform_flag_gradient_summary.csv"
    write_csv(summary_rows, summary_csv)

    sit_series: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    stall_series: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    sit_drop_series: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    stall_rise_series: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    by_platform_flag = {(r["platform"], r["flag_mode"]): r for r in summary_rows}
    for platform in PLATFORM_ORDER:
        for flag in FLAG_ORDER:
            row = by_platform_flag.get((platform, flag))
            if not row:
                continue
            sit_series[platform].append((flag, to_float(row.get("sit_median_mean"))))
            stall_series[platform].append((flag, to_float(row.get("residency_stall_mean"))))
            sit_drop_series[platform].append((flag, to_float(row.get("sit_drop_vs_none"))))
            stall_rise_series[platform].append((flag, to_float(row.get("stall_rise_vs_none"))))

    line_chart_svg(
        out_dir / "cross_platform_sit_median_by_flag.svg",
        "Cross-Platform SIT Median by Flag Mode",
        "flag_mode",
        "sit_median",
        FLAG_ORDER,
        sit_series,
    )
    line_chart_svg(
        out_dir / "cross_platform_residency_stall_by_flag.svg",
        "Cross-Platform Residency Stall by Flag Mode",
        "flag_mode",
        "residency_stall (%)",
        FLAG_ORDER,
        stall_series,
    )
    line_chart_svg(
        out_dir / "cross_platform_sit_drop_vs_none.svg",
        "Cross-Platform SIT Drop vs Baseline",
        "flag_mode",
        "sit_drop_vs_none",
        FLAG_ORDER,
        sit_drop_series,
    )
    line_chart_svg(
        out_dir / "cross_platform_stall_rise_vs_none.svg",
        "Cross-Platform Stall Rise vs Baseline",
        "flag_mode",
        "stall_rise_vs_none (%)",
        FLAG_ORDER,
        stall_rise_series,
    )

    print(f"Wrote: {summary_csv}")
    for name in [
        "cross_platform_sit_median_by_flag.svg",
        "cross_platform_residency_stall_by_flag.svg",
        "cross_platform_sit_drop_vs_none.svg",
        "cross_platform_stall_rise_vs_none.svg",
    ]:
        p = out_dir / name
        if p.exists():
            print(f"Wrote: {p}")
    if common_keys:
        print(f"Compared common workload/workload_size keys: {len(common_keys)}")
    else:
        print("No common workload/workload_size intersection found; used full rows per platform.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
