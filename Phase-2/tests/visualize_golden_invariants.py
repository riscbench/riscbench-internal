#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

import check_invariants as inv


INVARIANTS = [
    "sit_bounds",
    "fracs_sum_to_one",
    "nonresident_nan",
    "mode_specific",
]

MODES = ["base", "all", "skip_w0", "partial", "exact_boundary"]


def infer_mode(path: Path) -> str | None:
    name = path.name
    for mode in MODES:
        suffix = f"__{mode}_windows.csv"
        if name.endswith(suffix):
            return mode
    return None


def _run_check(df: pd.DataFrame, mode: str, window_us: float) -> Dict[str, Tuple[bool, str]]:
    out: Dict[str, Tuple[bool, str]] = {}

    checks = [
        ("sit_bounds", lambda: inv.check_sit_bounds(df)),
        ("fracs_sum_to_one", lambda: inv.check_fracs_sum_to_one(df)),
        ("nonresident_nan", lambda: inv.check_nonresident_are_nan(df)),
    ]
    for name, fn in checks:
        try:
            fn()
            out[name] = (True, "")
        except Exception as e:  # noqa: BLE001
            out[name] = (False, str(e))

    # Mode-specific
    try:
        if mode == "skip_w0":
            inv.check_skip_w0(df)
        elif mode == "partial":
            inv.check_partial_expected_resident_us(df, window_us=window_us)
        elif mode == "exact_boundary":
            inv.check_exact_boundary(df, window_us=window_us)
        out["mode_specific"] = (True, "")
    except Exception as e:  # noqa: BLE001
        out["mode_specific"] = (False, str(e))

    return out


def _ticks(vmax: float, n: int = 5) -> List[float]:
    if vmax <= 0:
        return [0.0, 1.0]
    step = vmax / float(max(1, n - 1))
    return [i * step for i in range(n)]


def _bar_svg(out_path: Path, title: str, labels: List[str], values: List[float], y_label: str) -> None:
    if not labels:
        return

    W, H = 920, 520
    ml, mr, mt, mb = 80, 40, 40, 100
    pw, ph = W - ml - mr, H - mt - mb

    vmax = max(1.0, max(values))
    if vmax <= 100.0 and all(v <= 100.0 for v in values):
        vmax = max(100.0, vmax)

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{W/2:.1f}" y="24" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>',
        f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#222"/>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#222"/>',
    ]

    for t in _ticks(vmax):
        y = mt + ph - (t / vmax) * ph
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" stroke="#eee"/>')
        lines.append(f'<text x="{ml-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{t:.1f}</text>')

    n = len(labels)
    gap = 12
    bar_w = max(14.0, (pw - (n + 1) * gap) / max(1, n))
    x = ml + gap
    for label, val in zip(labels, values):
        h = (val / vmax) * ph
        y = mt + ph - h
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="#1f77b4"/>')
        lines.append(f'<text x="{x+bar_w/2:.1f}" y="{mt+ph+14}" text-anchor="middle" font-family="sans-serif" font-size="11" transform="rotate(25 {x+bar_w/2:.1f} {mt+ph+14})">{label}</text>')
        lines.append(f'<text x="{x+bar_w/2:.1f}" y="{y-6:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{val:.1f}</text>')
        x += bar_w + gap

    lines.append(f'<text x="24" y="{mt + ph/2:.1f}" transform="rotate(-90 24 {mt + ph/2:.1f})" text-anchor="middle" font-family="sans-serif" font-size="13">{y_label}</text>')
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Visualize golden invariant outcomes from *_windows.csv artifacts.")
    ap.add_argument("--golden-out", required=True, help="Directory containing *_windows.csv outputs")
    ap.add_argument("--window-us", type=float, default=256.0)
    ap.add_argument("--out-dir", default=None, help="Default: <golden-out>/plots")
    args = ap.parse_args()

    golden_out = Path(args.golden_out).resolve()
    if not golden_out.exists():
        raise SystemExit(f"golden-out path not found: {golden_out}")

    out_dir = Path(args.out_dir).resolve() if args.out_dir else (golden_out / "plots")
    out_dir.mkdir(parents=True, exist_ok=True)

    windows_files = sorted(golden_out.glob("*_windows.csv"))
    if not windows_files:
        raise SystemExit(f"No *_windows.csv files found in {golden_out}")

    report_rows: List[Dict[str, str]] = []
    agg_pass = {name: 0 for name in INVARIANTS}
    agg_total = {name: 0 for name in INVARIANTS}
    mode_sit: Dict[str, List[float]] = {m: [] for m in MODES}

    for wp in windows_files:
        mode = infer_mode(wp)
        if mode is None:
            continue

        try:
            df = inv.load_windows(str(wp))
        except Exception as e:  # noqa: BLE001
            row = {"file": wp.name, "mode": mode, "load_error": str(e)}
            for name in INVARIANTS:
                row[name] = "0"
                row[f"{name}_msg"] = "load failed"
            report_rows.append(row)
            for name in INVARIANTS:
                agg_total[name] += 1
            continue

        checks = _run_check(df, mode, args.window_us)
        resident = df[df["is_resident_window"] == 1]
        sit_median = float("nan")
        if len(resident) > 0:
            sit_series = resident["sit"].astype(float).dropna()
            if len(sit_series) > 0:
                sit_median = float(sit_series.median())
                mode_sit[mode].append(sit_median)

        row = {
            "file": wp.name,
            "mode": mode,
            "rows": str(len(df)),
            "resident_windows": str(len(resident)),
            "sit_median": "" if math.isnan(sit_median) else f"{sit_median:.6f}",
        }
        for name in INVARIANTS:
            ok, msg = checks[name]
            row[name] = "1" if ok else "0"
            row[f"{name}_msg"] = msg
            agg_total[name] += 1
            if ok:
                agg_pass[name] += 1
        report_rows.append(row)

    report_csv = out_dir / "invariant_report.csv"
    fields = sorted({k for r in report_rows for k in r.keys()})
    with report_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(report_rows)

    labels = list(INVARIANTS)
    rates = []
    for name in labels:
        total = max(1, agg_total[name])
        rates.append((agg_pass[name] * 100.0) / total)
    _bar_svg(out_dir / "invariant_pass_rate.svg", "Invariant Pass Rate", labels, rates, "pass rate (%)")

    mode_labels = []
    mode_values = []
    for mode in MODES:
        vals = mode_sit.get(mode, [])
        if not vals:
            continue
        mode_labels.append(mode)
        mode_values.append(sum(vals) / float(len(vals)))
    _bar_svg(out_dir / "sit_median_by_mode.svg", "SIT Median by Mode", mode_labels, mode_values, "sit_median")

    print(f"Wrote: {report_csv}")
    for p in ["invariant_pass_rate.svg", "sit_median_by_mode.svg"]:
        fp = out_dir / p
        if fp.exists():
            print(f"Wrote: {fp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
