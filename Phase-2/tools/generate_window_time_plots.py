#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Tuple


def load_plotter(plotter_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("window_plotter", str(plotter_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load plotter: {plotter_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def generate_one(
    plotter: ModuleType,
    windows_csv: Path,
    out_dir: Path,
    platform_label: str,
    plot2_max_bars: int,
) -> Tuple[Path, Path, Path, str]:
    rows = plotter.parse_windows(windows_csv)
    if not rows:
        raise ValueError(f"no parseable rows in {windows_csv}")

    yvals, y_label, source_note = plotter.choose_sit_series(rows)
    pfx = plotter.output_prefix(windows_csv, None)

    plot1 = out_dir / f"{pfx}__plot1_sit_vs_time.svg"
    plot2 = out_dir / f"{pfx}__plot2_window_breakdown_stacked.svg"
    csv_out = out_dir / f"{pfx}__window_breakdown.csv"

    plotter.write_plot1_sit_vs_time(
        rows,
        yvals,
        y_label,
        source_note,
        plot1,
        platform_label=platform_label,
    )
    plotter.write_plot2_window_breakdown(
        rows,
        plot2,
        max_bars=max(100, int(plot2_max_bars)),
        platform_label=platform_label,
    )
    plotter.write_breakdown_csv(rows, csv_out, source_note, yvals)
    return (plot1, plot2, csv_out, source_note)


def write_report(rows: List[Dict[str, str]], report_csv: Path) -> None:
    fields = [
        "mode",
        "windows_csv",
        "status",
        "reason",
        "plot1_svg",
        "plot2_svg",
        "breakdown_csv",
        "sit_source",
    ]
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    with report_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate window-time visualizations for property-suite golden outputs."
    )
    ap.add_argument("--base-out", required=True, help="Property-suite output root directory.")
    ap.add_argument("--platform-label", required=True, help="Platform label used in plot titles.")
    ap.add_argument(
        "--out-root",
        default=None,
        help="Output root for generated visualizations (default: <base-out>/plots/window_time).",
    )
    ap.add_argument(
        "--plot2-max-bars",
        type=int,
        default=3500,
        help="Maximum bars in stacked Plot 2 before dense-mode binning.",
    )
    ap.add_argument(
        "--report-csv",
        default=None,
        help="CSV report path (default: <out-root>/window_time_generation_report.csv).",
    )
    args = ap.parse_args()

    base_out = Path(args.base_out).resolve()
    if not base_out.exists():
        raise SystemExit(f"base-out not found: {base_out}")

    out_root = Path(args.out_root).resolve() if args.out_root else (base_out / "plots" / "window_time")
    report_csv = Path(args.report_csv).resolve() if args.report_csv else (out_root / "window_time_generation_report.csv")

    plotter_path = (Path(__file__).resolve().parent.parent / "sweeps" / "plot_spike_window_diagnostics.py")
    if not plotter_path.exists():
        raise SystemExit(f"window plotter not found: {plotter_path}")
    plotter = load_plotter(plotter_path)

    mode_specs = [
        ("window_active", base_out / "golden_window_active"),
        ("global_active", base_out / "golden_global_active"),
    ]

    report_rows: List[Dict[str, str]] = []
    failures: List[str] = []
    generated = 0
    scanned = 0

    for mode, mode_dir in mode_specs:
        if not mode_dir.exists():
            report_rows.append(
                {
                    "mode": mode,
                    "windows_csv": "",
                    "status": "skip",
                    "reason": f"missing directory: {mode_dir}",
                    "plot1_svg": "",
                    "plot2_svg": "",
                    "breakdown_csv": "",
                    "sit_source": "",
                }
            )
            continue

        windows_files = sorted(mode_dir.glob("*_windows.csv"))
        if not windows_files:
            report_rows.append(
                {
                    "mode": mode,
                    "windows_csv": "",
                    "status": "skip",
                    "reason": f"no *_windows.csv files in {mode_dir}",
                    "plot1_svg": "",
                    "plot2_svg": "",
                    "breakdown_csv": "",
                    "sit_source": "",
                }
            )
            continue

        mode_out = out_root / mode
        mode_out.mkdir(parents=True, exist_ok=True)

        for windows_csv in windows_files:
            scanned += 1
            try:
                plot1, plot2, csv_out, sit_source = generate_one(
                    plotter=plotter,
                    windows_csv=windows_csv,
                    out_dir=mode_out,
                    platform_label=args.platform_label,
                    plot2_max_bars=int(args.plot2_max_bars),
                )
            except Exception as exc:
                failures.append(str(windows_csv))
                report_rows.append(
                    {
                        "mode": mode,
                        "windows_csv": str(windows_csv),
                        "status": "fail",
                        "reason": str(exc),
                        "plot1_svg": "",
                        "plot2_svg": "",
                        "breakdown_csv": "",
                        "sit_source": "",
                    }
                )
                continue

            generated += 1
            report_rows.append(
                {
                    "mode": mode,
                    "windows_csv": str(windows_csv),
                    "status": "pass",
                    "reason": "",
                    "plot1_svg": str(plot1),
                    "plot2_svg": str(plot2),
                    "breakdown_csv": str(csv_out),
                    "sit_source": sit_source,
                }
            )

    write_report(report_rows, report_csv)
    print(f"Wrote: {report_csv}")
    print(f"Scanned windows CSVs: {scanned}")
    print(f"Generated visualization sets: {generated}")

    if failures:
        print("FAIL window-time visualization generation:")
        for path in failures:
            print(f"  - {path}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
