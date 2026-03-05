#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import math
from pathlib import Path
from typing import Dict, List, Tuple


CAPTION_REQUIRED = (
    "Caption: SIT variations reflect workload-level orchestration behavior and not hardware latency effects."
)

COLORS = {
    "line": "#1f77b4",
    "resident_compute": "#2ca02c",
    "idle": "#f2b701",
    "memory_attributed": "#d62728",
    "non_resident": "#7f7f7f",
}


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
                wid = int(float((raw.get("window_id") or "").strip()))
            except Exception:
                wid = idx

            start_us = to_float(raw.get("window_start_us"))
            end_us = to_float(raw.get("window_end_us"))
            if not (finite(start_us) and finite(end_us)):
                continue

            window_us = max(0.0, end_us - start_us)
            resident_us = to_float(raw.get("resident_us"), window_us)
            if not finite(resident_us):
                resident_us = window_us
            resident_us = clamp(resident_us, 0.0, window_us)

            active_frac = clamp(to_float(raw.get("active_frac"), 0.0), 0.0, 1.0)
            stall_frac = clamp(to_float(raw.get("stall_frac"), 0.0), 0.0, 1.0)
            idle_frac = clamp(to_float(raw.get("idle_frac"), 0.0), 0.0, 1.0)

            frac_sum = active_frac + stall_frac + idle_frac
            if frac_sum <= 0.0:
                active_frac = 0.0
                stall_frac = 0.0
                idle_frac = 1.0
            elif abs(frac_sum - 1.0) > 1e-9:
                active_frac /= frac_sum
                stall_frac /= frac_sum
                idle_frac /= frac_sum

            sit = to_float(raw.get("sit"))
            sit_window_active = to_float(raw.get("sit_no_work_window_active"))

            resident_compute_us = resident_us * active_frac
            memory_attributed_us = resident_us * stall_frac
            idle_us = resident_us * idle_frac
            non_resident_us = max(0.0, window_us - resident_us)

            rows.append(
                {
                    "window_id": float(wid),
                    "window_start_us": start_us,
                    "window_end_us": end_us,
                    "window_us": window_us,
                    "resident_us": resident_us,
                    "active_frac": active_frac,
                    "stall_frac": stall_frac,
                    "idle_frac": idle_frac,
                    "sit": sit,
                    "sit_no_work_window_active": sit_window_active,
                    "resident_compute_us": resident_compute_us,
                    "memory_attributed_us": memory_attributed_us,
                    "idle_us": idle_us,
                    "non_resident_us": non_resident_us,
                }
            )

    rows.sort(key=lambda r: (r["window_start_us"], r["window_id"]))
    return rows


def choose_sit_series(rows: List[Dict[str, float]]) -> Tuple[List[float], str, str]:
    vals_window_active = [r["sit_no_work_window_active"] for r in rows]
    if vals_window_active and all(finite(v) for v in vals_window_active):
        return (
            vals_window_active,
            "SIT (instructions/us)",
            "Source metric: sit_no_work_window_active",
        )

    vals_sit = [r["sit"] for r in rows]
    finite_sit = [v for v in vals_sit if finite(v)]
    if finite_sit and len(finite_sit) == len(rows):
        if (max(finite_sit) - min(finite_sit)) > 1e-12:
            return (
                vals_sit,
                "SIT (instructions/us)",
                "Source metric: sit",
            )

    # If sit is unavailable or flat under global-active no-work mode, use window-active
    # intensity as a normalized SIT proxy to expose temporal orchestration structure.
    proxy = [r["active_frac"] for r in rows]
    return (
        proxy,
        "SIT (normalized units)",
        "Source metric: active_frac (normalized window-active SIT proxy)",
    )


def ticks(vmin: float, vmax: float, n: int = 6) -> List[float]:
    if vmin == vmax:
        return [vmin]
    step = (vmax - vmin) / float(max(1, n - 1))
    return [vmin + i * step for i in range(n)]


def fmt_tick(v: float, decimals: int = 3) -> str:
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:.{decimals}f}"


def compress_rows_for_plot2(
    rows: List[Dict[str, float]],
    max_bars: int,
) -> Tuple[List[Dict[str, float]], bool, int]:
    n = len(rows)
    if max_bars <= 0 or n <= max_bars:
        return (rows, False, 1)

    bin_size = int(math.ceil(n / float(max_bars)))
    out: List[Dict[str, float]] = []
    for start in range(0, n, bin_size):
        chunk = rows[start : start + bin_size]
        m = float(len(chunk))
        if m <= 0:
            continue
        first = chunk[0]
        last = chunk[-1]
        out.append(
            {
                "window_id": 0.5 * (first["window_id"] + last["window_id"]),
                "window_start_us": first["window_start_us"],
                "window_end_us": last["window_end_us"],
                "window_us": sum(r["window_us"] for r in chunk) / m,
                "resident_us": sum(r["resident_us"] for r in chunk) / m,
                "active_frac": sum(r["active_frac"] for r in chunk) / m,
                "stall_frac": sum(r["stall_frac"] for r in chunk) / m,
                "idle_frac": sum(r["idle_frac"] for r in chunk) / m,
                "sit": sum(r["sit"] for r in chunk if finite(r["sit"])) / max(
                    1.0, sum(1.0 for r in chunk if finite(r["sit"]))
                ),
                "sit_no_work_window_active": sum(
                    r["sit_no_work_window_active"] for r in chunk if finite(r["sit_no_work_window_active"])
                )
                / max(1.0, sum(1.0 for r in chunk if finite(r["sit_no_work_window_active"]))),
                "resident_compute_us": sum(r["resident_compute_us"] for r in chunk) / m,
                "memory_attributed_us": sum(r["memory_attributed_us"] for r in chunk) / m,
                "idle_us": sum(r["idle_us"] for r in chunk) / m,
                "non_resident_us": sum(r["non_resident_us"] for r in chunk) / m,
            }
        )
    return (out, True, bin_size)


def write_plot1_sit_vs_time(
    rows: List[Dict[str, float]],
    yvals: List[float],
    y_label: str,
    source_note: str,
    out_path: Path,
    platform_label: str = "Spike",
) -> None:
    xvals = [r["window_start_us"] for r in rows]
    xmin, xmax = min(xvals), max(xvals)
    ymin, ymax = min(yvals), max(yvals)

    if xmin == xmax:
        xmax = xmin + 1.0
    if ymin == ymax:
        pad = 0.05 * (abs(ymin) if ymin != 0.0 else 1.0)
        ymin -= pad
        ymax += pad

    width = 1450
    height = 720
    ml, mr = 90, 260
    mt, mb = 72, 205
    pw = width - ml - mr
    ph = height - mt - mb

    def sx(x: float) -> float:
        return ml + ((x - xmin) / (xmax - xmin)) * pw

    def sy(y: float) -> float:
        return mt + ph - ((y - ymin) / (ymax - ymin)) * ph

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append('<rect width="100%" height="100%" fill="white"/>')
    lines.append(
        '<text x="{x}" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">'
        "{title}"
        "</text>".format(
            x=width / 2.0,
            title=html.escape(f"Plot 1 - SIT vs Elapsed Time ({platform_label})"),
        )
    )
    lines.append(
        '<text x="{x}" y="46" text-anchor="middle" font-family="sans-serif" font-size="12">'
        "{t}"
        "</text>".format(x=width / 2.0, t=html.escape(source_note))
    )

    lines.append(f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#222"/>')
    lines.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#222"/>')

    for t in ticks(xmin, xmax, 7):
        x = sx(t)
        lines.append(f'<line x1="{x:.2f}" y1="{mt}" x2="{x:.2f}" y2="{mt+ph}" stroke="#ededed"/>')
        lines.append(f'<line x1="{x:.2f}" y1="{mt+ph}" x2="{x:.2f}" y2="{mt+ph+6}" stroke="#222"/>')
        lines.append(
            '<text x="{x:.2f}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="11">{t}</text>'.format(
                x=x, y=mt + ph + 24, t=fmt_tick(t, 1)
            )
        )

    for t in ticks(ymin, ymax, 6):
        y = sy(t)
        lines.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml+pw}" y2="{y:.2f}" stroke="#ededed"/>')
        lines.append(f'<line x1="{ml-6}" y1="{y:.2f}" x2="{ml}" y2="{y:.2f}" stroke="#222"/>')
        lines.append(
            '<text x="{x}" y="{y:.2f}" text-anchor="end" font-family="sans-serif" font-size="11">{t}</text>'.format(
                x=ml - 10, y=y + 4, t=fmt_tick(t, 4)
            )
        )

    poly = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in zip(xvals, yvals))
    lines.append(
        f'<polyline fill="none" stroke="{COLORS["line"]}" stroke-width="1.6" points="{poly}"/>'
    )

    lines.append(f'<line x1="{ml+pw+24}" y1="{mt+24}" x2="{ml+pw+46}" y2="{mt+24}" stroke="{COLORS["line"]}" stroke-width="2.2"/>')
    lines.append(
        '<text x="{x}" y="{y}" font-family="sans-serif" font-size="12">SIT timeline</text>'.format(
            x=ml + pw + 52, y=mt + 28
        )
    )

    lines.append(
        '<text x="{x}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="13">Elapsed time (us)</text>'.format(
            x=ml + pw / 2.0, y=height - 132
        )
    )
    lines.append(
        '<text x="24" y="{y}" transform="rotate(-90 24 {y})" text-anchor="middle" font-family="sans-serif" font-size="13">{label}</text>'.format(
            y=mt + ph / 2.0, label=html.escape(y_label)
        )
    )
    lines.append(
        '<text x="{x}" y="{y}" text-anchor="start" font-family="sans-serif" font-size="12" fill="#111">{cap}</text>'.format(
            x=ml, y=height - 78, cap=html.escape(CAPTION_REQUIRED)
        )
    )
    lines.append(
        '<text x="{x}" y="{y}" text-anchor="start" font-family="sans-serif" font-size="11" fill="#444">'
        "Expected in this view: residency bursts in active windows and orchestration gaps between phases."
        "</text>".format(x=ml, y=height - 56)
    )
    lines.append("</svg>")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_plot2_window_breakdown(
    rows: List[Dict[str, float]],
    out_path: Path,
    max_bars: int = 3500,
    platform_label: str = "Spike",
) -> None:
    original_n = len(rows)
    rows_plot, binned, bin_size = compress_rows_for_plot2(rows, max_bars=max_bars)
    n = len(rows_plot)
    pitch = 1.20
    bar_w = max(0.85, pitch * 0.86)
    pw = max(980, int(math.ceil(n * pitch)))

    ml, mr = 90, 320
    mt, mb = 72, 122
    width = ml + pw + mr
    height = 640
    ph = height - mt - mb

    totals = [
        r["resident_compute_us"] + r["idle_us"] + r["memory_attributed_us"] + r["non_resident_us"]
        for r in rows_plot
    ]
    ymax = max(totals) if totals else 1.0
    if ymax <= 0.0:
        ymax = 1.0

    def sx_idx(i: int) -> float:
        return ml + i * pitch + (pitch - bar_w) / 2.0

    def sy(v: float) -> float:
        return mt + ph - (v / ymax) * ph

    lines: List[str] = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append('<rect width="100%" height="100%" fill="white"/>')
    lines.append(
        '<text x="{x}" y="28" text-anchor="middle" font-family="sans-serif" font-size="20">'
        "{title}"
        "</text>".format(
            x=width / 2.0,
            title=html.escape(f"Plot 2 - Window Breakdown (Stacked Bar) ({platform_label})"),
        )
    )
    subtitle = "Stacked categories: resident compute, idle, memory-attributed, non-resident (time in us)"
    if binned:
        subtitle += f" | dense mode: {original_n} windows binned to {n} bars (bin={bin_size})"
    lines.append(
        '<text x="{x}" y="46" text-anchor="middle" font-family="sans-serif" font-size="12">{subtitle}</text>'.format(
            x=width / 2.0, subtitle=html.escape(subtitle)
        )
    )

    lines.append(f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#222"/>')
    lines.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#222"/>')

    for t in ticks(0.0, ymax, 6):
        y = sy(t)
        lines.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml+pw}" y2="{y:.2f}" stroke="#ededed"/>')
        lines.append(f'<line x1="{ml-6}" y1="{y:.2f}" x2="{ml}" y2="{y:.2f}" stroke="#222"/>')
        lines.append(
            '<text x="{x}" y="{y:.2f}" text-anchor="end" font-family="sans-serif" font-size="11">{t}</text>'.format(
                x=ml - 10, y=y + 4, t=fmt_tick(t, 1)
            )
        )

    tick_count = 8
    for i in range(tick_count + 1):
        idx = int(round((n - 1) * (i / tick_count))) if n > 1 else 0
        x = sx_idx(idx) + bar_w / 2.0
        wid = int(rows_plot[idx]["window_id"]) if rows_plot else 0
        lines.append(f'<line x1="{x:.2f}" y1="{mt+ph}" x2="{x:.2f}" y2="{mt+ph+6}" stroke="#222"/>')
        lines.append(
            '<text x="{x:.2f}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="11">{wid}</text>'.format(
                x=x, y=mt + ph + 24, wid=wid
            )
        )

    for i, r in enumerate(rows_plot):
        x = sx_idx(i)
        levels = [
            ("resident_compute_us", COLORS["resident_compute"]),
            ("idle_us", COLORS["idle"]),
            ("memory_attributed_us", COLORS["memory_attributed"]),
            ("non_resident_us", COLORS["non_resident"]),
        ]
        y_top = mt + ph
        for key, color in levels:
            v = r[key]
            if v <= 0.0:
                continue
            h = (v / ymax) * ph
            y_top -= h
            lines.append(
                '<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{c}" />'.format(
                    x=x, y=y_top, w=bar_w, h=h, c=color
                )
            )

    legend_x = ml + pw + 26
    legend_y = mt + 36
    legend = [
        ("resident compute", COLORS["resident_compute"]),
        ("idle", COLORS["idle"]),
        ("memory-attributed", COLORS["memory_attributed"]),
        ("non-resident", COLORS["non_resident"]),
    ]
    for i, (label, color) in enumerate(legend):
        yy = legend_y + i * 24
        lines.append(f'<rect x="{legend_x}" y="{yy-10}" width="18" height="12" fill="{color}" />')
        lines.append(
            '<text x="{x}" y="{y}" font-family="sans-serif" font-size="12">{label}</text>'.format(
                x=legend_x + 26, y=yy, label=html.escape(label)
            )
        )

    max_non_resident = max((r["non_resident_us"] for r in rows_plot), default=0.0)
    if max_non_resident <= 1e-9:
        lines.append(
            '<text x="{x}" y="{y}" font-family="sans-serif" font-size="11" fill="#444">'
            "Trace note: non-resident component is zero across windows for this residency mode."
            "</text>".format(x=legend_x, y=legend_y + 120)
        )

    lines.append(
        '<text x="{x}" y="{y}" text-anchor="middle" font-family="sans-serif" font-size="13">{label}</text>'.format(
            x=ml + pw / 2.0,
            y=height - 34,
            label="Window index (binned)" if binned else "Window index",
        )
    )
    lines.append(
        '<text x="24" y="{y}" transform="rotate(-90 24 {y})" text-anchor="middle" font-family="sans-serif" font-size="13">Time (us)</text>'.format(
            y=mt + ph / 2.0
        )
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_breakdown_csv(rows: List[Dict[str, float]], out_path: Path, sit_source_note: str, yvals: List[float]) -> None:
    fieldnames = [
        "window_id",
        "window_start_us",
        "window_end_us",
        "window_us",
        "resident_us",
        "resident_compute_us",
        "idle_us",
        "memory_attributed_us",
        "non_resident_us",
        "sit_timeline_value",
        "sit_timeline_source",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r, y in zip(rows, yvals):
            w.writerow(
                {
                    "window_id": int(r["window_id"]),
                    "window_start_us": f'{r["window_start_us"]:.6f}',
                    "window_end_us": f'{r["window_end_us"]:.6f}',
                    "window_us": f'{r["window_us"]:.6f}',
                    "resident_us": f'{r["resident_us"]:.6f}',
                    "resident_compute_us": f'{r["resident_compute_us"]:.6f}',
                    "idle_us": f'{r["idle_us"]:.6f}',
                    "memory_attributed_us": f'{r["memory_attributed_us"]:.6f}',
                    "non_resident_us": f'{r["non_resident_us"]:.6f}',
                    "sit_timeline_value": f"{y:.9f}",
                    "sit_timeline_source": sit_source_note,
                }
            )


def output_prefix(windows_csv: Path, prefix: str | None) -> str:
    if prefix:
        return prefix
    stem = windows_csv.stem
    if stem.endswith("_windows"):
        return stem[: -len("_windows")]
    return stem


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate Plot 1/2 window diagnostics as SVG.")
    ap.add_argument("--windows-csv", required=True, help="Path to *_windows.csv")
    ap.add_argument("--out-dir", default=None, help="Output directory (default: <windows-csv-dir>/plots)")
    ap.add_argument("--prefix", default=None, help="Output filename prefix")
    ap.add_argument("--platform-label", default="Spike", help="Platform label shown in plot titles.")
    ap.add_argument(
        "--plot2-max-bars",
        type=int,
        default=3500,
        help="Maximum bars in stacked Plot 2 before binning (dense mode).",
    )
    args = ap.parse_args()

    windows_csv = Path(args.windows_csv).resolve()
    if not windows_csv.exists():
        raise SystemExit(f"windows csv not found: {windows_csv}")

    rows = parse_windows(windows_csv)
    if not rows:
        raise SystemExit(f"no parseable rows in {windows_csv}")

    yvals, y_label, source_note = choose_sit_series(rows)

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (windows_csv.parent / "plots")
    out_dir.mkdir(parents=True, exist_ok=True)

    pfx = output_prefix(windows_csv, args.prefix)
    plot1 = out_dir / f"{pfx}__plot1_sit_vs_time.svg"
    plot2 = out_dir / f"{pfx}__plot2_window_breakdown_stacked.svg"
    csv_out = out_dir / f"{pfx}__window_breakdown.csv"

    write_plot1_sit_vs_time(
        rows,
        yvals,
        y_label,
        source_note,
        plot1,
        platform_label=str(args.platform_label),
    )
    write_plot2_window_breakdown(
        rows,
        plot2,
        max_bars=max(100, int(args.plot2_max_bars)),
        platform_label=str(args.platform_label),
    )
    write_breakdown_csv(rows, csv_out, source_note, yvals)

    print(f"Wrote: {plot1}")
    print(f"Wrote: {plot2}")
    print(f"Wrote: {csv_out}")
    print(f"SIT timeline source: {source_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
