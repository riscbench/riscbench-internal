#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


WORKLOAD_DATASETS: list[tuple[str, str]] = [
    ("custom_sfpi_add", "tt_custom_sfpi_add"),
    ("custom_sfpi_smoothstep", "tt_custom_sfpi_smoothstep"),
    ("eltwise_binary", "tt_eltwise_binary"),
    ("eltwise_sfpu", "tt_eltwise_sfpu"),
    ("loopback", "tt_loopback"),
    ("matmul_multi", "tt_matmul_multi"),
    ("matmul_single", "tt_matmul_single"),
    ("noc_transfer", "tt_noc_transfer"),
    ("sfpu_chain", "tt_sfpu_chain"),
    ("vecadd", "tt_vecadd"),
]

IMAGE_CALIBRATION: dict[str, dict[str, object]] = {
    "eltwise_sfpu": {
        "dataset_dir": "tt_eltwise_sfpu",
        "ops_per_zone": 1024.0,
        "scaling_mode": "size_scaled",
        "label": "eltwise_sfpu",
    },
    "custom_sfpi_add": {
        "dataset_dir": "tt_custom_sfpi_add",
        "ops_per_zone": 1024.0,
        "scaling_mode": "size_scaled",
        "label": "custom_sfpi_add",
    },
    "eltwise_binary": {
        "dataset_dir": "tt_eltwise_binary",
        "ops_per_zone": 1024.0,
        "scaling_mode": "size_scaled",
        "label": "eltwise_binary",
    },
    "custom_sfpi_smoothstep": {
        "dataset_dir": "tt_custom_sfpi_smoothstep",
        "ops_per_zone": 6144.0,
        "scaling_mode": "size_scaled",
        "label": "custom_sfpi_smoothstep",
    },
    "sfpu_chain": {
        "dataset_dir": "tt_sfpu_chain",
        "ops_per_zone": 3072.0,
        "scaling_mode": "fixed_single_tile",
        "label": "sfpu_chain",
    },
    "matmul_single": {
        "dataset_dir": "tt_matmul_single",
        "ops_per_zone": 65536.0,
        "scaling_mode": "size_scaled",
        "label": "matmul_single",
    },
}

TT_TILE_RE = re.compile(r"^tt_(\d+)tile$")


def parse_workloads(spec: str) -> list[tuple[str, str]]:
    if not spec.strip() or spec.strip().lower() == "all":
        return list(WORKLOAD_DATASETS)
    wanted = {tok.strip() for tok in spec.split(",") if tok.strip()}
    rows = [item for item in WORKLOAD_DATASETS if item[0] in wanted or item[1] in wanted]
    missing = sorted(wanted - {name for name, _ in rows} - {dataset for _, dataset in rows})
    if missing:
        raise SystemExit(f"unknown workloads: {', '.join(missing)}")
    return rows


def parse_calibrated_workloads(spec: str) -> list[tuple[str, str]]:
    if not spec.strip() or spec.strip().lower() == "all":
        return [
            (workload, str(cfg["dataset_dir"]))
            for workload, cfg in IMAGE_CALIBRATION.items()
        ]
    wanted = {tok.strip() for tok in spec.split(",") if tok.strip()}
    rows: list[tuple[str, str]] = []
    for workload, cfg in IMAGE_CALIBRATION.items():
        dataset_dir = str(cfg["dataset_dir"])
        if workload in wanted or dataset_dir in wanted:
            rows.append((workload, dataset_dir))
    missing = sorted(wanted - set(IMAGE_CALIBRATION.keys()) - {str(cfg["dataset_dir"]) for cfg in IMAGE_CALIBRATION.values()})
    if missing:
        raise SystemExit(f"unknown calibrated workloads: {', '.join(missing)}")
    return rows


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def dataset_paths(bundle_root: Path, dataset_dir: str) -> tuple[Path, Path]:
    base = bundle_root / "datasets" / "Tenstorrent_test_raw_files-main" / dataset_dir / "profiler_logs"
    profile_csv = base / "profile_log_device.csv"
    zone_log = base / "zone_src_locations.log"
    if not profile_csv.exists():
        raise SystemExit(f"missing profiler csv: {profile_csv}")
    if not zone_log.exists():
        raise SystemExit(f"missing zone log: {zone_log}")
    return profile_csv, zone_log


def run_tt_workload(
    bundle_root: Path,
    python_bin: str,
    workload: str,
    dataset_dir: str,
    size: str,
    ops_per_zone: float | None = None,
) -> Path:
    profile_csv, zone_log = dataset_paths(bundle_root, dataset_dir)
    cmd = [
        python_bin,
        str(bundle_root / "device_handler" / "backend_runner.py"),
        "--target",
        "tt_wormhole",
        "--workload",
        workload,
        "--workload_size",
        size,
        "--tt-profile-csv",
        str(profile_csv),
        "--tt-zone-log",
        str(zone_log),
    ]
    if ops_per_zone is not None:
        cmd += ["--tt-ops-per-zone", str(ops_per_zone)]
    subprocess.run(cmd, cwd=bundle_root, check=True)
    summary_path = bundle_root / "runs" / "tt_wormhole" / workload / size / "run_summary.json"
    if not summary_path.exists():
        raise SystemExit(f"missing summary after run: {summary_path}")
    return summary_path


def load_summary(bundle_root: Path, workload: str, size: str) -> tuple[Path, dict]:
    for name in ("run_summary.json", "summary.json"):
        path = bundle_root / "runs" / "tt_wormhole" / workload / size / name
        if path.exists():
            return path, json.loads(path.read_text(encoding="utf-8"))
    raise SystemExit(f"missing summary for {workload}/{size}")


def load_fallback_flops(run_dir: Path) -> tuple[float, float, float]:
    state_csv = run_dir / "inputs" / "state_intervals.csv"
    resid_csv = run_dir / "inputs" / "residency_intervals.csv"
    if not state_csv.exists() or not resid_csv.exists():
        return float("nan"), float("nan"), float("nan")

    observed_flops_total = 0.0
    with state_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "work_done" not in (reader.fieldnames or []):
            return float("nan"), float("nan"), float("nan")
        for row in reader:
            try:
                observed_flops_total += float(row.get("work_done", "nan"))
            except (TypeError, ValueError):
                continue

    resident_us = 0.0
    with resid_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                resident_us += max(0.0, float(row["end_us"]) - float(row["start_us"]))
            except (KeyError, TypeError, ValueError):
                continue

    observed_flops_per_us = (
        observed_flops_total / resident_us if resident_us > 0.0 else float("nan")
    )
    return observed_flops_total, observed_flops_per_us, resident_us


def tile_count_from_size(size: str) -> float:
    if size == "tt_tile":
        return 1.0
    m = TT_TILE_RE.match(str(size))
    if not m:
        return float("nan")
    return float(m.group(1))


def calibrated_expected_flops_per_us(size: str, resident_us: float, calibration: dict[str, object] | None) -> float:
    if calibration is None or not math.isfinite(resident_us) or resident_us <= 0.0:
        return float("nan")
    ops_per_zone = float(calibration["ops_per_zone"])
    scaling_mode = str(calibration["scaling_mode"])
    if scaling_mode == "fixed_single_tile":
        total_ops = ops_per_zone
    else:
        tile_count = tile_count_from_size(size)
        if not math.isfinite(tile_count):
            return float("nan")
        total_ops = ops_per_zone * tile_count
    return total_ops / resident_us


def ensure_output_dir(bundle_root: Path, outdir: str | None, size: str) -> Path:
    if outdir:
        path = Path(outdir).expanduser().resolve()
    else:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = (bundle_root / "results" / f"tt_flops_{size}_{stamp}").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def fmt_value(value: float, digits: int = 2) -> str:
    if not math.isfinite(value):
        return "nan"
    return f"{value:.{digits}f}"


def fmt_compact(value: float) -> str:
    if not math.isfinite(value):
        return "nan"
    abs_value = abs(value)
    if abs_value >= 1_000_000.0:
        return f"{value / 1_000_000.0:.1f}M"
    if abs_value >= 1_000.0:
        return f"{value / 1_000.0:.1f}k"
    if abs_value >= 100.0:
        return f"{value:.0f}"
    if abs_value >= 10.0:
        return f"{value:.1f}"
    return f"{value:.2f}"


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def blend_hex(start: str, end: str, t: float) -> str:
    t = clamp(t, 0.0, 1.0)
    start_rgb = tuple(int(start[i : i + 2], 16) for i in (1, 3, 5))
    end_rgb = tuple(int(end[i : i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(round(a + (b - a) * t) for a, b in zip(start_rgb, end_rgb))
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def normalize_residency(active: float, stall: float, idle: float) -> tuple[float, float, float]:
    parts = []
    for value in (active, stall, idle):
        if not math.isfinite(value) or value < 0.0:
            parts.append(0.0)
        else:
            cleaned = float(value)
            if cleaned < 1e-9:
                cleaned = 0.0
            parts.append(cleaned)
    total = sum(parts)
    if total <= 0.0:
        return 0.0, 0.0, 0.0
    return tuple(part / total for part in parts)


def bounds_for_values(values: list[float], *, log_scale: bool = False) -> tuple[float, float]:
    filtered = [
        value
        for value in values
        if math.isfinite(value) and (value > 0.0 if log_scale else True)
    ]
    if not filtered:
        return (1.0, 10.0) if log_scale else (0.0, 1.0)
    lo = min(filtered)
    hi = max(filtered)
    if hi <= lo:
        if log_scale:
            hi = lo * 10.0
        else:
            hi = lo + 1.0
    return lo, hi


def normalized_value(value: float, lo: float, hi: float, *, log_scale: bool = False) -> float | None:
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


def cell_colors(
    value: float,
    lo: float,
    hi: float,
    *,
    low_color: str,
    high_color: str,
    log_scale: bool = False,
) -> tuple[str, str]:
    t = normalized_value(value, lo, hi, log_scale=log_scale)
    if t is None:
        return "#e2e8f0", "#64748b"
    fill = blend_hex(low_color, high_color, t)
    text = "#ffffff" if t >= 0.58 else "#0f172a"
    return fill, text


def write_csv(rows: Iterable[dict], path: Path) -> None:
    rows = list(rows)
    fieldnames = [
        "workload",
        "dataset_dir",
        "size",
        "ops_per_zone",
        "calibration_mode",
        "resident_us_total",
        "observed_flops_total",
        "overall_observed_flops_per_us",
        "calibrated_expected_flops_per_us",
        "calibrated_efficiency",
        "sit_median",
        "overall_window_sit_median",
        "resident_windows_total",
        "windows_total",
        "summary_expected_work_rate",
        "expected_work_rate",
        "observed_vs_expected_work_rate",
        "residency_active_avg",
        "residency_idle_avg",
        "residency_stall_avg",
        "summary_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def svg_escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_residency_svg(rows: list[dict], path: Path, title: str, size: str) -> None:
    ordered = list(rows)
    residency_parts = [
        normalize_residency(
            float(row.get("residency_active_avg", float("nan"))),
            float(row.get("residency_stall_avg", float("nan"))),
            float(row.get("residency_idle_avg", float("nan"))),
        )
        for row in ordered
    ]
    active_values = [100.0 * parts[0] for parts in residency_parts]
    stall_values = [100.0 * parts[1] for parts in residency_parts]
    idle_values = [100.0 * parts[2] for parts in residency_parts]
    resident_values = [float(row.get("resident_us_total", float("nan"))) for row in ordered]
    sit_values = [float(row.get("sit_median", float("nan"))) for row in ordered]

    resident_lo, resident_hi = bounds_for_values(resident_values)
    active_lo, active_hi = bounds_for_values(active_values)
    stall_lo, stall_hi = bounds_for_values(stall_values)
    idle_lo, idle_hi = bounds_for_values(idle_values)
    sit_lo, sit_hi = bounds_for_values(sit_values)

    row_h = 56
    outer_margin = 28
    table_x = 42
    workload_w = 230
    col_w = 142
    table_top = 150
    table_h = len(ordered) * row_h
    total_width = 1000
    total_height = table_top + table_h + 48
    col_x = [
        table_x + workload_w,
        table_x + workload_w + (1 * col_w),
        table_x + workload_w + (2 * col_w),
        table_x + workload_w + (3 * col_w),
        table_x + workload_w + (4 * col_w),
    ]

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{total_height}" viewBox="0 0 {total_width} {total_height}">',
        '<rect width="100%" height="100%" fill="#f8fafc" />',
        f'<rect x="{outer_margin}" y="{outer_margin}" width="{total_width - 2 * outer_margin}" height="{total_height - 2 * outer_margin}" rx="24" fill="#ffffff" stroke="#e2e8f0" />',
        f'<text x="52" y="58" font-size="24" font-weight="700" fill="#0f172a">{svg_escape(title)}: Residency Heatmap</text>',
        f'<text x="52" y="80" font-size="13" fill="#475569">Tenstorrent tt_wormhole summary for {svg_escape(size)}. Darker cells indicate larger values within each column.</text>',
        '<text x="52" y="102" font-size="12" fill="#64748b">Columns summarize resident time, active/stall/idle fractions, and median SIT for each workload.</text>',
        f'<text x="{table_x}" y="132" font-size="12" font-weight="700" fill="#334155">WORKLOAD</text>',
        f'<text x="{col_x[0] + (col_w / 2):.2f}" y="132" text-anchor="middle" font-size="12" font-weight="700" fill="#334155">Resident us</text>',
        f'<text x="{col_x[1] + (col_w / 2):.2f}" y="132" text-anchor="middle" font-size="12" font-weight="700" fill="#334155">Active %</text>',
        f'<text x="{col_x[2] + (col_w / 2):.2f}" y="132" text-anchor="middle" font-size="12" font-weight="700" fill="#334155">Stall %</text>',
        f'<text x="{col_x[3] + (col_w / 2):.2f}" y="132" text-anchor="middle" font-size="12" font-weight="700" fill="#334155">Idle %</text>',
        f'<text x="{col_x[4] + (col_w / 2):.2f}" y="132" text-anchor="middle" font-size="12" font-weight="700" fill="#334155">SIT Median</text>',
    ]

    for idx, row in enumerate(ordered):
        y = table_top + (idx * row_h)
        cy = y + (row_h / 2.0)
        if idx % 2 == 0:
            svg.append(
                f'<rect x="{table_x - 10}" y="{y + 4}" width="{total_width - 2 * table_x + 20}" height="{row_h - 8}" rx="16" fill="#f8fafc" />'
            )

        active, stall, idle = residency_parts[idx]
        cells = [
            (
                float(row.get("resident_us_total", float("nan"))),
                resident_lo,
                resident_hi,
                "#e0f2fe",
                "#0369a1",
                False,
                lambda v: f"{fmt_value(v, 1)} us",
            ),
            (
                active * 100.0,
                active_lo,
                active_hi,
                "#dcfce7",
                "#15803d",
                False,
                lambda v: f"{fmt_value(v, 1)}%",
            ),
            (
                stall * 100.0,
                stall_lo,
                stall_hi,
                "#fef3c7",
                "#b45309",
                False,
                lambda v: f"{fmt_value(v, 1)}%",
            ),
            (
                idle * 100.0,
                idle_lo,
                idle_hi,
                "#e2e8f0",
                "#475569",
                False,
                lambda v: f"{fmt_value(v, 1)}%",
            ),
            (
                float(row.get("sit_median", float("nan"))),
                sit_lo,
                sit_hi,
                "#ccfbf1",
                "#0f766e",
                False,
                lambda v: fmt_value(v, 3),
            ),
        ]

        svg.append(
            f'<text x="{table_x}" y="{cy + 5:.2f}" font-size="14" font-weight="600" fill="#0f172a">{svg_escape(str(row["workload"]))}</text>'
        )

        for cell_idx, (value, lo, hi, low_color, high_color, log_scale, formatter) in enumerate(cells):
            x = col_x[cell_idx]
            fill, text_fill = cell_colors(
                value,
                lo,
                hi,
                low_color=low_color,
                high_color=high_color,
                log_scale=log_scale,
            )
            svg.append(
                f'<rect x="{x + 8}" y="{y + 10}" width="{col_w - 16}" height="{row_h - 20}" rx="12" fill="{fill}" />'
            )
            label = formatter(value) if math.isfinite(value) else "nan"
            svg.append(
                f'<text x="{x + (col_w / 2):.2f}" y="{cy + 4:.2f}" text-anchor="middle" font-size="12" font-weight="700" fill="{text_fill}">{svg_escape(label)}</text>'
            )

    svg.append(
        f'<text x="{table_x}" y="{total_height - 18}" font-size="11" fill="#64748b">Active, stall, and idle values are column-normalized heat cells and still sum per row to roughly 100%.</text>'
    )
    svg.append("</svg>")
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def write_flops_svg(rows: list[dict], path: Path, title: str, size: str) -> None:
    ordered = sorted(
        rows,
        key=lambda row: float(row.get("overall_observed_flops_per_us", float("-inf"))),
        reverse=True,
    )
    throughput_values: list[float] = []
    total_values: list[float] = []
    stall_values: list[float] = []
    ratio_values: list[float] = []
    window_sit_values: list[float] = []
    window_counts: list[float] = []
    for row in ordered:
        observed = float(row.get("overall_observed_flops_per_us", float("nan")))
        reference = float(row.get("expected_work_rate", float("nan")))
        total_flops = float(row.get("observed_flops_total", float("nan")))
        stall_share = 100.0 * float(row.get("residency_stall_avg", float("nan")))
        burst_ratio = float(row.get("observed_vs_expected_work_rate", float("nan")))
        window_sit = float(row.get("overall_window_sit_median", float("nan")))
        resident_windows = float(row.get("resident_windows_total", float("nan")))
        for value in (observed, reference):
            if math.isfinite(value) and value > 0.0:
                throughput_values.append(value)
        if math.isfinite(total_flops) and total_flops > 0.0:
            total_values.append(total_flops)
        if math.isfinite(stall_share):
            stall_values.append(stall_share)
        if math.isfinite(burst_ratio):
            ratio_values.append(burst_ratio)
        if math.isfinite(window_sit):
            window_sit_values.append(window_sit)
        if math.isfinite(resident_windows):
            window_counts.append(resident_windows)

    throughput_lo, throughput_hi = bounds_for_values(throughput_values, log_scale=True)
    total_lo, total_hi = bounds_for_values(total_values, log_scale=True)
    stall_lo, stall_hi = bounds_for_values(stall_values)
    ratio_lo, ratio_hi = bounds_for_values(ratio_values)
    window_sit_lo, window_sit_hi = bounds_for_values(window_sit_values)
    max_window_count = max(int(value) for value in window_counts) if window_counts else 1

    total_width = 1500
    total_height = 1056
    outer_margin = 28
    plot_x = 72
    plot_y = 196
    plot_w = 840
    plot_h = 420
    legend_x = 970
    legend_y = 196
    legend_w = 460
    legend_h = 420
    summary_x = 72
    summary_y = 674
    summary_w = 1358
    summary_h = 330
    row_h = 34
    row_gap = 8
    resid_x = 286
    resid_w = 286
    ratio_x = 618
    ratio_w = 120
    window_sit_x = 776
    window_sit_w = 120
    dots_x = 934
    dots_w = 110

    def throughput_x(value: float) -> float | None:
        t = normalized_value(value, throughput_lo, throughput_hi, log_scale=True)
        if t is None:
            return None
        return plot_x + (t * plot_w)

    def throughput_y(value: float) -> float | None:
        t = normalized_value(value, throughput_lo, throughput_hi, log_scale=True)
        if t is None:
            return None
        return plot_y + plot_h - (t * plot_h)

    def point_radius(value: float) -> float:
        t = normalized_value(value, total_lo, total_hi, log_scale=True)
        if t is None:
            return 9.0
        return 9.0 + (t * 15.0)

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{total_height}" viewBox="0 0 {total_width} {total_height}">',
        "<defs>",
        '<linearGradient id="overviewField" x1="0%" y1="100%" x2="100%" y2="0%">',
        '<stop offset="0%" stop-color="#00c853" />',
        '<stop offset="42%" stop-color="#facc15" />',
        '<stop offset="70%" stop-color="#fb923c" />',
        '<stop offset="100%" stop-color="#ff2d55" />',
        "</linearGradient>",
        '<linearGradient id="plotShade" x1="0%" y1="0%" x2="0%" y2="100%">',
        '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.12" />',
        '<stop offset="100%" stop-color="#030712" stop-opacity="0.30" />',
        "</linearGradient>",
        '<linearGradient id="stallLegend" x1="0%" y1="0%" x2="100%" y2="0%">',
        '<stop offset="0%" stop-color="#34d399" />',
        '<stop offset="50%" stop-color="#fbbf24" />',
        '<stop offset="100%" stop-color="#ef4444" />',
        "</linearGradient>",
        '<linearGradient id="windowLegend" x1="0%" y1="0%" x2="100%" y2="0%">',
        '<stop offset="0%" stop-color="#164e63" />',
        '<stop offset="50%" stop-color="#0ea5e9" />',
        '<stop offset="100%" stop-color="#d946ef" />',
        "</linearGradient>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#0b1020" />',
        '<circle cx="1320" cy="100" r="280" fill="#1d4ed8" opacity="0.10" />',
        '<circle cx="180" cy="830" r="260" fill="#22c55e" opacity="0.06" />',
        f'<rect x="{outer_margin}" y="{outer_margin}" width="{total_width - 2 * outer_margin}" height="{total_height - 2 * outer_margin}" rx="30" fill="#0f172a" stroke="#1f2937" />',
        f'<text x="72" y="82" font-size="20" font-weight="700" fill="#f8fafc">TT FLOPs + Residency Overview</text>',
        f'<text x="72" y="114" font-size="31" font-weight="800" fill="#f8fafc">{svg_escape(title)}</text>',
        f'<text x="72" y="142" font-size="14" fill="#cbd5e1">Single-image presentation view for {svg_escape(size)}. Position shows manual reference work rate versus observed FLOPs/us.</text>',
        '<text x="72" y="162" font-size="14" fill="#cbd5e1">The lower strip compresses residency mix, burst ratio, window SIT, and resident-window density for every workload.</text>',
        f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" rx="30" fill="url(#overviewField)" />',
        f'<rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" rx="30" fill="url(#plotShade)" />',
        f'<text x="{plot_x}" y="{plot_y - 24}" font-size="16" font-weight="700" fill="#f8fafc">Observed vs Manual Reference Throughput Map</text>',
        f'<text x="{plot_x + plot_w}" y="{plot_y - 8}" text-anchor="end" font-size="12" fill="#cbd5e1">Warmer background regions indicate higher absolute throughput on both axes.</text>',
    ]

    for frac in (0.25, 0.5, 0.75):
        x = plot_x + (frac * plot_w)
        y = plot_y + (frac * plot_h)
        svg.append(
            f'<line x1="{x:.2f}" y1="{plot_y}" x2="{x:.2f}" y2="{plot_y + plot_h}" stroke="#ffffff" stroke-opacity="0.28" />'
        )
        svg.append(
            f'<line x1="{plot_x}" y1="{y:.2f}" x2="{plot_x + plot_w}" y2="{y:.2f}" stroke="#ffffff" stroke-opacity="0.28" />'
        )

    svg.extend(
        [
            f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y}" stroke="#f8fafc" stroke-opacity="0.55" stroke-dasharray="10 10" />',
            f'<text x="{plot_x + plot_w - 12}" y="{plot_y + 22}" text-anchor="end" font-size="11" fill="#f8fafc">Match line</text>',
            f'<text x="{plot_x}" y="{plot_y + plot_h + 28}" font-size="12" fill="#cbd5e1">Lower manual reference</text>',
            f'<text x="{plot_x + plot_w}" y="{plot_y + plot_h + 28}" text-anchor="end" font-size="12" fill="#cbd5e1">Higher manual reference</text>',
            f'<text x="{plot_x + (plot_w / 2):.2f}" y="{plot_y + plot_h + 54}" text-anchor="middle" font-size="14" font-weight="700" fill="#f8fafc">Manual Reference Work Rate</text>',
            f'<text x="{plot_x + 12}" y="{plot_y + plot_h - 8}" font-size="12" fill="#cbd5e1">Lower observed</text>',
            f'<text x="{plot_x + 12}" y="{plot_y + 18}" font-size="12" fill="#cbd5e1">Higher observed</text>',
            f'<text x="{plot_x - 48}" y="{plot_y + (plot_h / 2):.2f}" transform="rotate(-90 {plot_x - 48} {plot_y + (plot_h / 2):.2f})" text-anchor="middle" font-size="14" font-weight="700" fill="#f8fafc">Observed FLOPs/us</text>',
        ]
    )

    for idx, row in enumerate(ordered):
        workload = str(row["workload"])
        observed = float(row.get("overall_observed_flops_per_us", float("nan")))
        reference = float(row.get("expected_work_rate", float("nan")))
        total_flops = float(row.get("observed_flops_total", float("nan")))
        stall_share = 100.0 * float(row.get("residency_stall_avg", float("nan")))
        cx = throughput_x(reference)
        cy = throughput_y(observed)
        if cx is None or cy is None:
            continue
        radius = point_radius(total_flops)
        stall_t = normalized_value(stall_share, stall_lo, stall_hi)
        stall_fill = blend_hex("#34d399", "#ef4444", stall_t if stall_t is not None else 0.35)
        label_anchor = "end" if cx > plot_x + (plot_w * 0.64) else "start"
        label_dx = -(radius + 16.0) if label_anchor == "end" else (radius + 16.0)
        label_dy = -(radius + 10.0) if cy > plot_y + 80.0 else (radius + 20.0)
        label_x = cx + label_dx
        label_y = cy + label_dy
        label_y = max(plot_y + 22.0, min(plot_y + plot_h - 8.0, label_y))
        leader_x = cx + (-(radius + 4.0) if label_anchor == "end" else (radius + 4.0))
        leader_y = cy + (-(radius * 0.55) if label_dy < 0 else (radius * 0.55))
        label_w = max(88.0, (len(workload) * 7.2) + 18.0)
        label_h = 22.0
        if label_anchor == "end":
            label_box_x = label_x - label_w + 4.0
        else:
            label_box_x = label_x - 4.0
        label_box_y = label_y - 15.0
        svg.extend(
            [
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius + 8:.2f}" fill="{stall_fill}" opacity="0.16" />',
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" fill="{stall_fill}" stroke="#f8fafc" stroke-width="2.4" />',
                f'<line x1="{leader_x:.2f}" y1="{leader_y:.2f}" x2="{label_x:.2f}" y2="{label_y - 6:.2f}" stroke="#f8fafc" stroke-opacity="0.60" />',
                f'<rect x="{label_box_x:.2f}" y="{label_box_y:.2f}" width="{label_w:.2f}" height="{label_h:.2f}" rx="11" fill="#0f172a" fill-opacity="0.84" stroke="#cbd5e1" stroke-opacity="0.35" />',
                f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="{label_anchor}" font-size="12" font-weight="700" fill="#f8fafc">{svg_escape(workload)}</text>',
            ]
        )

    svg.extend(
        [
            f'<rect x="{legend_x}" y="{legend_y}" width="{legend_w}" height="{legend_h}" rx="28" fill="#111827" stroke="#1f2937" />',
            f'<text x="{legend_x + 28}" y="{legend_y + 34}" font-size="16" font-weight="700" fill="#f8fafc">How To Read</text>',
            f'<text x="{legend_x + 28}" y="{legend_y + 64}" font-size="12" fill="#cbd5e1">Position: x = manual reference, y = observed FLOPs/us.</text>',
            f'<text x="{legend_x + 28}" y="{legend_y + 84}" font-size="12" fill="#cbd5e1">Points above the match line outperform the manual reference.</text>',
            f'<text x="{legend_x + 28}" y="{legend_y + 122}" font-size="13" font-weight="700" fill="#f8fafc">Marker Size = Observed FLOPs Total</text>',
            f'<circle cx="{legend_x + 54}" cy="{legend_y + 158}" r="8" fill="#93c5fd" stroke="#f8fafc" stroke-width="2" />',
            f'<circle cx="{legend_x + 94}" cy="{legend_y + 158}" r="13" fill="#60a5fa" stroke="#f8fafc" stroke-width="2" />',
            f'<circle cx="{legend_x + 150}" cy="{legend_y + 158}" r="19" fill="#2563eb" stroke="#f8fafc" stroke-width="2" />',
            f'<text x="{legend_x + 188}" y="{legend_y + 150}" font-size="11" fill="#cbd5e1">Smaller</text>',
            f'<text x="{legend_x + 188}" y="{legend_y + 168}" font-size="11" fill="#cbd5e1">total work</text>',
            f'<text x="{legend_x + 188}" y="{legend_y + 188}" font-size="11" fill="#cbd5e1">Larger</text>',
            f'<text x="{legend_x + 188}" y="{legend_y + 206}" font-size="11" fill="#cbd5e1">total work</text>',
            f'<text x="{legend_x + 28}" y="{legend_y + 244}" font-size="13" font-weight="700" fill="#f8fafc">Marker Color = Stall Share</text>',
            f'<rect x="{legend_x + 28}" y="{legend_y + 258}" width="240" height="14" rx="7" fill="url(#stallLegend)" />',
            f'<text x="{legend_x + 28}" y="{legend_y + 292}" font-size="11" fill="#cbd5e1">Mostly active</text>',
            f'<text x="{legend_x + 268}" y="{legend_y + 292}" text-anchor="end" font-size="11" fill="#cbd5e1">Mostly stalled</text>',
            f'<text x="{legend_x + 28}" y="{legend_y + 330}" font-size="13" font-weight="700" fill="#f8fafc">Bottom Strip</text>',
            f'<rect x="{legend_x + 28}" y="{legend_y + 346}" width="92" height="14" rx="7" fill="#1f2937" />',
            f'<rect x="{legend_x + 28}" y="{legend_y + 346}" width="50" height="14" rx="7" fill="#22c55e" />',
            f'<rect x="{legend_x + 78}" y="{legend_y + 346}" width="24" height="14" fill="#f59e0b" />',
            f'<rect x="{legend_x + 102}" y="{legend_y + 346}" width="18" height="14" rx="7" fill="#475569" />',
            f'<text x="{legend_x + 136}" y="{legend_y + 357}" font-size="11" fill="#cbd5e1">Residency mix</text>',
            f'<rect x="{legend_x + 28}" y="{legend_y + 376}" width="92" height="22" rx="10" fill="#1d4ed8" />',
            f'<text x="{legend_x + 136}" y="{legend_y + 392}" font-size="11" fill="#cbd5e1">Burst ratio heat</text>',
            f'<rect x="{legend_x + 28}" y="{legend_y + 410}" width="92" height="22" rx="10" fill="url(#windowLegend)" />',
            f'<text x="{legend_x + 136}" y="{legend_y + 426}" font-size="11" fill="#cbd5e1">Window SIT heat</text>',
            f'<circle cx="{legend_x + 44}" cy="{legend_y + 462}" r="5" fill="#f8fafc" />',
            f'<circle cx="{legend_x + 66}" cy="{legend_y + 462}" r="5" fill="#f8fafc" opacity="0.8" />',
            f'<circle cx="{legend_x + 88}" cy="{legend_y + 462}" r="5" fill="#f8fafc" opacity="0.6" />',
            f'<circle cx="{legend_x + 110}" cy="{legend_y + 462}" r="5" fill="#f8fafc" opacity="0.35" />',
            f'<text x="{legend_x + 136}" y="{legend_y + 467}" font-size="11" fill="#cbd5e1">Resident window count</text>',
        ]
    )

    svg.extend(
        [
            f'<rect x="{summary_x}" y="{summary_y}" width="{summary_w}" height="{summary_h}" rx="28" fill="#111827" stroke="#1f2937" />',
            f'<text x="{summary_x + 24}" y="{summary_y + 30}" font-size="16" font-weight="700" fill="#f8fafc">Workload Heat Strip</text>',
            f'<text x="{summary_x + 24}" y="{summary_y + 52}" font-size="12" fill="#cbd5e1">Each row keeps the same workload ordering as the throughput map: residency mix, burst ratio, window SIT, and resident-window density.</text>',
            f'<text x="{summary_x + 24}" y="{summary_y + 84}" font-size="11" font-weight="700" fill="#94a3b8">WORKLOAD</text>',
            f'<text x="{resid_x}" y="{summary_y + 84}" font-size="11" font-weight="700" fill="#94a3b8">RESIDENCY MIX</text>',
            f'<text x="{ratio_x}" y="{summary_y + 84}" font-size="11" font-weight="700" fill="#94a3b8">BURST RATIO</text>',
            f'<text x="{window_sit_x}" y="{summary_y + 84}" font-size="11" font-weight="700" fill="#94a3b8">WINDOW SIT</text>',
            f'<text x="{dots_x}" y="{summary_y + 84}" font-size="11" font-weight="700" fill="#94a3b8">RESIDENT WINDOWS</text>',
        ]
    )

    for idx, row in enumerate(ordered):
        y = summary_y + 102 + (idx * (row_h + row_gap))
        cy = y + (row_h / 2.0)
        if idx % 2 == 0:
            svg.append(
                f'<rect x="{summary_x + 14}" y="{y - 2}" width="{summary_w - 28}" height="{row_h + 4}" rx="16" fill="#0f172a" />'
            )
        workload = str(row["workload"])
        active, stall, idle = normalize_residency(
            float(row.get("residency_active_avg", float("nan"))),
            float(row.get("residency_stall_avg", float("nan"))),
            float(row.get("residency_idle_avg", float("nan"))),
        )
        burst_ratio = float(row.get("observed_vs_expected_work_rate", float("nan")))
        window_sit = float(row.get("overall_window_sit_median", float("nan")))
        resident_windows = int(float(row.get("resident_windows_total", float("nan")))) if math.isfinite(float(row.get("resident_windows_total", float("nan")))) else 0
        svg.append(
            f'<text x="{summary_x + 24}" y="{cy + 5:.2f}" font-size="14" font-weight="700" fill="#f8fafc">{svg_escape(workload)}</text>'
        )
        bar_y = cy - 9.0
        svg.append(
            f'<rect x="{resid_x}" y="{bar_y:.2f}" width="{resid_w}" height="18" rx="9" fill="#1f2937" />'
        )
        segment_x = resid_x
        for fraction, color in ((active, "#22c55e"), (stall, "#f59e0b"), (idle, "#475569")):
            segment_w = resid_w * fraction
            if segment_w <= 0.0:
                continue
            svg.append(
                f'<rect x="{segment_x:.2f}" y="{bar_y:.2f}" width="{segment_w:.2f}" height="18" fill="{color}" />'
            )
            segment_x += segment_w

        ratio_t = normalized_value(burst_ratio, ratio_lo, ratio_hi)
        ratio_fill = blend_hex("#172554", "#38bdf8", ratio_t if ratio_t is not None else 0.35)
        svg.append(
            f'<rect x="{ratio_x}" y="{cy - 12:.2f}" width="{ratio_w}" height="24" rx="12" fill="{ratio_fill}" />'
        )
        window_t = normalized_value(window_sit, window_sit_lo, window_sit_hi)
        window_fill = blend_hex("#164e63", "#d946ef", window_t if window_t is not None else 0.35)
        svg.append(
            f'<rect x="{window_sit_x}" y="{cy - 12:.2f}" width="{window_sit_w}" height="24" rx="12" fill="{window_fill}" />'
        )
        for dot_idx in range(max_window_count):
            opacity = 0.95 if dot_idx < resident_windows else 0.18
            cx = dots_x + 14 + (dot_idx * min(22, max(12, dots_w // max_window_count)))
            svg.append(
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="5.2" fill="#f8fafc" opacity="{opacity:.2f}" />'
            )

    svg.append("</svg>")
    path.write_text("\n".join(svg) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(prog="tt_flops_report")
    ap.add_argument("--size", default="tt_64tile", help="Workload size label to run/read, e.g. tt_64tile")
    ap.add_argument("--workloads", default="all", help="Comma-separated workload names or 'all'")
    ap.add_argument(
        "--python",
        dest="python_bin",
        default=sys.executable,
        help="Python executable used to run device_handler/backend_runner.py",
    )
    ap.add_argument("--skip-run", action="store_true", help="Reuse existing TT run summaries instead of rerunning workloads")
    ap.add_argument(
        "--calibration-profile",
        choices=["none", "image"],
        default="none",
        help="Optional workload-specific FLOPs calibration profile",
    )
    ap.add_argument(
        "--title",
        default="Observed FLOPs Across Tenstorrent Workloads (64 Tiles)",
        help="Chart title written into the SVG",
    )
    ap.add_argument("--outdir", default=None, help="Optional output directory for CSV/SVG/JSON summary")
    args = ap.parse_args()

    bundle_root = repo_root()
    output_dir = ensure_output_dir(bundle_root, args.outdir, str(args.size))
    if args.calibration_profile == "image":
        selected = parse_calibrated_workloads(str(args.workloads))
    else:
        selected = parse_workloads(str(args.workloads))
    rows: list[dict] = []

    for workload, dataset_dir in selected:
        calibration = IMAGE_CALIBRATION.get(workload) if args.calibration_profile == "image" else None
        ops_per_zone = float(calibration["ops_per_zone"]) if calibration is not None else None
        if args.skip_run:
            summary_path, summary = load_summary(bundle_root, workload, str(args.size))
        else:
            summary_path = run_tt_workload(
                bundle_root,
                str(args.python_bin),
                workload,
                dataset_dir,
                str(args.size),
                ops_per_zone=ops_per_zone,
            )
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        run_dir = summary_path.parent
        fallback_total, fallback_rate, resident_us_total = load_fallback_flops(run_dir)
        calibrated_expected = calibrated_expected_flops_per_us(str(args.size), resident_us_total, calibration)
        calibrated_efficiency = (
            fallback_rate / calibrated_expected
            if math.isfinite(fallback_rate) and math.isfinite(calibrated_expected) and calibrated_expected > 0.0
            else float("nan")
        )
        summary_expected_work_rate = float(summary.get("expected_work_rate", float("nan")))
        expected_work_rate = (
            calibrated_expected
            if math.isfinite(calibrated_expected) and calibrated_expected > 0.0
            else summary_expected_work_rate
        )
        observed_vs_expected_work_rate = (
            fallback_rate / expected_work_rate
            if math.isfinite(fallback_rate) and math.isfinite(expected_work_rate) and expected_work_rate > 0.0
            else float("nan")
        )
        rows.append(
            {
                "workload": workload,
                "dataset_dir": dataset_dir,
                "size": str(args.size),
                "ops_per_zone": ops_per_zone,
                "calibration_mode": str(calibration["scaling_mode"]) if calibration is not None else "summary_default",
                "resident_us_total": resident_us_total,
                "observed_flops_total": float(summary.get("observed_flops_total", fallback_total)),
                "overall_observed_flops_per_us": float(summary.get("overall_observed_flops_per_us", fallback_rate)),
                "calibrated_expected_flops_per_us": calibrated_expected,
                "calibrated_efficiency": calibrated_efficiency,
                "sit_median": float(summary.get("sit_median", float("nan"))),
                "overall_window_sit_median": float(summary.get("overall_window_sit_median", float("nan"))),
                "resident_windows_total": float(summary.get("resident_windows_total", float("nan"))),
                "windows_total": float(summary.get("windows_total", float("nan"))),
                "summary_expected_work_rate": summary_expected_work_rate,
                "expected_work_rate": expected_work_rate,
                "observed_vs_expected_work_rate": observed_vs_expected_work_rate,
                "residency_active_avg": float(summary.get("residency_active_avg", float("nan"))),
                "residency_idle_avg": float(summary.get("residency_idle_avg", float("nan"))),
                "residency_stall_avg": float(summary.get("residency_stall_avg", float("nan"))),
                "summary_path": str(summary_path),
            }
        )

    csv_path = output_dir / "tt_flops_summary.csv"
    json_path = output_dir / "tt_flops_summary.json"
    flops_svg_path = output_dir / "tt_flops_summary.svg"
    residency_svg_path = output_dir / "tt_residency_heatmap.svg"
    write_csv(rows, csv_path)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    write_flops_svg(rows, flops_svg_path, str(args.title), str(args.size))
    write_residency_svg(rows, residency_svg_path, str(args.title), str(args.size))

    print(f"wrote csv: {csv_path}")
    print(f"wrote json: {json_path}")
    print(f"wrote flops svg: {flops_svg_path}")
    print(f"wrote residency svg: {residency_svg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
