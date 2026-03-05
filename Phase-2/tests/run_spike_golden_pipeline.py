#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_SPIKE_WORKLOADS = ["fm_loopback", "fm_mm", "fm_sparse", "fm_read", "fm_write", "matmul"]
ALL_SIZES = ["test", "tiny", "small", "med", "large"]
FLAG_MODES = ["none", "branch_mispredict", "cache_pressure", "both"]
SIZE_ORDER = {name: i for i, name in enumerate(ALL_SIZES)}
WORKLOAD_ORDER = {name: i for i, name in enumerate(DEFAULT_SPIKE_WORKLOADS)}
FLAG_MODE_DISPLAY = {
    "none": "Workload/orchestration factors: baseline",
    "branch_mispredict": "Workload/orchestration factors: control-flow perturbation",
    "cache_pressure": "Workload/orchestration factors: memory-pressure perturbation",
    "both": "Workload/orchestration factors: combined perturbations",
}
METHODOLOGY_NOTE = "Spike and QEMU do not model microarchitectural timing; gem5 and hardware platforms may."


def run(cmd: List[str], cwd: Path) -> int:
    print("$", " ".join(cmd))
    p = subprocess.run(cmd, cwd=cwd)
    return int(p.returncode)


def build_manifest(repo: Path, traces: List[Path], window_us: float, dataset_version: str) -> dict:
    masks_dir = repo / "datasets" / "residency"
    return {
        "dataset_version": dataset_version,
        "window_us_default": float(window_us),
        "traces": [str(p.resolve()) for p in traces],
        "residency_masks": {
            "all": str((masks_dir / "all.csv").resolve()),
            "skip_w0": str((masks_dir / "skip_w0.csv").resolve()),
            "partial": str((masks_dir / "partial.csv").resolve()),
            "exact_boundary": str((masks_dir / "exact_boundary.csv").resolve()),
        },
    }


def bool_to_int(v: bool) -> str:
    return "1" if v else "0"


def parse_trace_id(filename: str) -> str:
    # format: trace_XXXX__<mode>_windows.csv
    if "__" in filename:
        return filename.split("__", 1)[0]
    return filename


def to_float(raw: str | None) -> float:
    if raw is None:
        return float("nan")
    s = raw.strip()
    if not s or s.lower() == "nan":
        return float("nan")
    return float(s)


def workload_sort_key(name: str) -> Tuple[int, str]:
    return (WORKLOAD_ORDER.get(name, 999), name)


def safe_name(name: str) -> str:
    out = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out)


def workloads_title_suffix(workloads: List[str], max_names: int = 4) -> str:
    if not workloads:
        return ""
    if len(workloads) <= max_names:
        return " - workloads: " + ", ".join(workloads)
    shown = ", ".join(workloads[:max_names])
    return f" - workloads: {shown} +{len(workloads) - max_names} more"


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    fields = sorted({k for r in rows for k in r.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def display_flag_mode(name: str) -> str:
    return FLAG_MODE_DISPLAY.get(name, name)


def _line_svg(
    out_path: Path,
    title: str,
    x_labels: List[str],
    y_label: str,
    series: Dict[str, List[Tuple[str, float]]],
    x_label: str = "workload_size",
) -> None:
    # Categorical x-axis chart in plain SVG (no external deps).
    valid_series: Dict[str, List[Tuple[str, float]]] = {}
    for name, pts in series.items():
        pts2 = [(x, y) for x, y in pts if math.isfinite(y)]
        if pts2:
            valid_series[name] = pts2
    if not valid_series:
        return

    yvals = [y for pts in valid_series.values() for _, y in pts]
    ymin, ymax = min(yvals), max(yvals)
    if ymin == ymax:
        ymax = ymin + 1.0

    W, H = 980, 560
    ml, mr, mt, mb = 80, 260, 44, 90
    pw, ph = W - ml - mr, H - mt - mb
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    x_map = {name: i for i, name in enumerate(x_labels)}
    step = pw / max(1, (len(x_labels) - 1)) if len(x_labels) > 1 else 1.0

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
        f'<text x="{W/2:.1f}" y="40" text-anchor="middle" font-family="sans-serif" font-size="11">{METHODOLOGY_NOTE}</text>',
        f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#222"/>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#222"/>',
    ]

    # y ticks
    for i in range(5):
        t = ymin + (ymax - ymin) * (i / 4.0)
        y = sy(t)
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" stroke="#eee"/>')
        lines.append(f'<text x="{ml-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{t:.3f}</text>')

    # x ticks
    for xl in x_labels:
        x = sx(xl)
        lines.append(f'<line x1="{x:.1f}" y1="{mt+ph}" x2="{x:.1f}" y2="{mt+ph+5}" stroke="#222"/>')
        lines.append(
            f'<text x="{x:.1f}" y="{mt+ph+22}" text-anchor="middle" font-family="sans-serif" font-size="11" '
            f'transform="rotate(20 {x:.1f} {mt+ph+22})">{xl}</text>'
        )

    # series
    legend_x = ml + pw + 20
    legend_y = mt + 24
    for idx, (name, pts) in enumerate(valid_series.items()):
        color = colors[idx % len(colors)]
        pts_sorted = sorted(pts, key=lambda p: x_map[p[0]])
        poly = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts_sorted)
        lines.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{poly}"/>')
        for x, y in pts_sorted:
            lines.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.8" fill="{color}"/>')

        ly = legend_y + idx * 22
        lines.append(f'<line x1="{legend_x}" y1="{ly}" x2="{legend_x+24}" y2="{ly}" stroke="{color}" stroke-width="3"/>')
        lines.append(
            f'<text x="{legend_x+30}" y="{ly+4}" font-family="sans-serif" font-size="12">{display_flag_mode(name)}</text>'
        )

    lines.append(f'<text x="{ml + pw/2:.1f}" y="{H-18}" text-anchor="middle" font-family="sans-serif" font-size="13">{x_label}</text>')
    lines.append(
        f'<text x="24" y="{mt + ph/2:.1f}" transform="rotate(-90 24 {mt + ph/2:.1f})" '
        f'text-anchor="middle" font-family="sans-serif" font-size="13">{y_label}</text>'
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_common_outputs(outdir: Path, common_mode: str) -> int:
    plots_dir = outdir / "plots"
    inv_report = plots_dir / "invariant_report.csv"
    trace_index_csv = outdir / "trace_index.csv"
    if not inv_report.exists():
        print(f"warning: invariant report missing: {inv_report}")
        return 0
    if not trace_index_csv.exists():
        print(f"warning: trace index missing: {trace_index_csv}")
        return 0

    id_meta: Dict[str, Dict[str, str]] = {}
    with trace_index_csv.open("r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            id_meta[r["trace_id"]] = r

    enriched_rows: List[Dict[str, str]] = []
    with inv_report.open("r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tid = parse_trace_id(r.get("file", ""))
            meta = id_meta.get(tid)
            if meta is None:
                continue
            out = dict(r)
            out.update(
                {
                    "trace_id": tid,
                    "workload": meta["workload"],
                    "workload_size": meta["workload_size"],
                    "flag_mode": meta["flag_mode"],
                    "branch_mispredict": meta["branch_mispredict"],
                    "cache_pressure": meta["cache_pressure"],
                }
            )
            all_ok = (
                out.get("sit_bounds") == "1"
                and out.get("fracs_sum_to_one") == "1"
                and out.get("nonresident_nan") == "1"
                and out.get("mode_specific") == "1"
            )
            out["all_invariants_ok"] = "1" if all_ok else "0"
            enriched_rows.append(out)

    enriched_csv = plots_dir / "invariant_report_enriched.csv"
    write_csv(enriched_csv, enriched_rows)
    print(f"✓ wrote: {enriched_csv}")

    # Aggregate for common mode graph: y = mean sit_median per size grouped by flag_mode.
    sit_by_flag_size: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    pass_by_flag_size: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    # Workload-aware aggregation: workload -> flag -> size -> values.
    sit_by_workload_flag_size: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    pass_by_workload_flag_size: Dict[str, Dict[str, Dict[str, List[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for r in enriched_rows:
        if r.get("mode") != common_mode:
            continue
        size = r.get("workload_size", "")
        flag = r.get("flag_mode", "")
        workload = r.get("workload", "")
        if size not in SIZE_ORDER:
            continue
        sit = to_float(r.get("sit_median"))
        if math.isfinite(sit):
            sit_by_flag_size[flag][size].append(sit)
            sit_by_workload_flag_size[workload][flag][size].append(sit)
        pass_by_flag_size[flag][size].append(1.0 if r.get("all_invariants_ok") == "1" else 0.0)
        pass_by_workload_flag_size[workload][flag][size].append(1.0 if r.get("all_invariants_ok") == "1" else 0.0)

    sizes_present = sorted(
        {sz for f in sit_by_flag_size.values() for sz in f.keys()} | {sz for f in pass_by_flag_size.values() for sz in f.keys()},
        key=lambda s: SIZE_ORDER.get(s, 999),
    )
    if not sizes_present:
        print(f"warning: no rows for common mode '{common_mode}'")
        return 0

    workloads_present = sorted(
        {
            wl
            for wl in (set(sit_by_workload_flag_size.keys()) | set(pass_by_workload_flag_size.keys()))
            if wl
        },
        key=workload_sort_key,
    )
    workloads_suffix = workloads_title_suffix(workloads_present)

    sit_series: Dict[str, List[Tuple[str, float]]] = {}
    for flag, mp in sit_by_flag_size.items():
        pts: List[Tuple[str, float]] = []
        for sz in sizes_present:
            vals = mp.get(sz, [])
            if vals:
                pts.append((sz, sum(vals) / float(len(vals))))
        if pts:
            sit_series[flag] = pts
    mode_suffix = "" if common_mode == "base" else f" ({common_mode})"
    _line_svg(
        plots_dir / f"common_sit_median_{common_mode}.svg",
        f"Common SIT Median{mode_suffix}{workloads_suffix}",
        sizes_present,
        "sit_median",
        sit_series,
    )

    pass_series: Dict[str, List[Tuple[str, float]]] = {}
    for flag, mp in pass_by_flag_size.items():
        pts = []
        for sz in sizes_present:
            vals = mp.get(sz, [])
            if vals:
                pts.append((sz, 100.0 * (sum(vals) / float(len(vals)))))
        if pts:
            pass_series[flag] = pts
    _line_svg(
        plots_dir / f"common_invariant_pass_rate_{common_mode}.svg",
        f"Common Invariant Pass Rate{mode_suffix}{workloads_suffix}",
        sizes_present,
        "pass rate (%)",
        pass_series,
    )

    summary_rows: List[Dict[str, str]] = []
    for flag in sorted(set(sit_by_flag_size.keys()) | set(pass_by_flag_size.keys())):
        for sz in sizes_present:
            svals = sit_by_flag_size.get(flag, {}).get(sz, [])
            pvals = pass_by_flag_size.get(flag, {}).get(sz, [])
            summary_rows.append(
                {
                    "mode": common_mode,
                    "flag_mode": flag,
                    "workload_size": sz,
                    "sit_median_mean": "" if not svals else f"{sum(svals)/len(svals):.6f}",
                    "invariant_pass_rate_pct": "" if not pvals else f"{100.0*sum(pvals)/len(pvals):.2f}",
                    "sample_count": str(len(pvals)),
                }
            )
    common_csv = plots_dir / f"common_summary_{common_mode}.csv"
    write_csv(common_csv, summary_rows)
    print(f"✓ wrote: {common_csv}")

    if not workloads_present:
        return 0

    summary_by_workload_rows: List[Dict[str, str]] = []
    all_flags = sorted(set(sit_by_flag_size.keys()) | set(pass_by_flag_size.keys()))

    # Per-workload plots: x=size, legend=flag.
    for workload in workloads_present:
        sit_series_workload: Dict[str, List[Tuple[str, float]]] = {}
        pass_series_workload: Dict[str, List[Tuple[str, float]]] = {}
        for flag in all_flags:
            sit_pts: List[Tuple[str, float]] = []
            pass_pts: List[Tuple[str, float]] = []
            for sz in sizes_present:
                svals = sit_by_workload_flag_size.get(workload, {}).get(flag, {}).get(sz, [])
                pvals = pass_by_workload_flag_size.get(workload, {}).get(flag, {}).get(sz, [])
                if svals:
                    sit_pts.append((sz, sum(svals) / float(len(svals))))
                if pvals:
                    pass_pts.append((sz, 100.0 * (sum(pvals) / float(len(pvals)))))
                summary_by_workload_rows.append(
                    {
                        "mode": common_mode,
                        "workload": workload,
                        "flag_mode": flag,
                        "workload_size": sz,
                        "sit_median_mean": "" if not svals else f"{sum(svals)/len(svals):.6f}",
                        "invariant_pass_rate_pct": "" if not pvals else f"{100.0*sum(pvals)/len(pvals):.2f}",
                        "sample_count": str(len(pvals)),
                    }
                )
            if sit_pts:
                sit_series_workload[flag] = sit_pts
            if pass_pts:
                pass_series_workload[flag] = pass_pts

        wl_suffix = safe_name(workload)
        _line_svg(
            plots_dir / f"common_sit_median_{common_mode}__{wl_suffix}.svg",
            f"Common SIT Median - {workload}{mode_suffix}",
            sizes_present,
            "sit_median",
            sit_series_workload,
            x_label="workload_size",
        )
        _line_svg(
            plots_dir / f"common_invariant_pass_rate_{common_mode}__{wl_suffix}.svg",
            f"Common Invariant Pass Rate - {workload}{mode_suffix}",
            sizes_present,
            "pass rate (%)",
            pass_series_workload,
            x_label="workload_size",
        )

    summary_by_workload_csv = plots_dir / f"common_summary_by_workload_{common_mode}.csv"
    write_csv(summary_by_workload_csv, summary_by_workload_rows)
    print(f"✓ wrote: {summary_by_workload_csv}")

    # Cross-workload plots: x=workload, legend=flag (aggregated across sizes).
    sit_series_by_workload: Dict[str, List[Tuple[str, float]]] = {}
    pass_series_by_workload: Dict[str, List[Tuple[str, float]]] = {}
    for flag in all_flags:
        sit_pts: List[Tuple[str, float]] = []
        pass_pts: List[Tuple[str, float]] = []
        for workload in workloads_present:
            flat_svals: List[float] = []
            flat_pvals: List[float] = []
            for sz in sizes_present:
                flat_svals.extend(sit_by_workload_flag_size.get(workload, {}).get(flag, {}).get(sz, []))
                flat_pvals.extend(pass_by_workload_flag_size.get(workload, {}).get(flag, {}).get(sz, []))
            if flat_svals:
                sit_pts.append((workload, sum(flat_svals) / float(len(flat_svals))))
            if flat_pvals:
                pass_pts.append((workload, 100.0 * (sum(flat_pvals) / float(len(flat_pvals)))))
        if sit_pts:
            sit_series_by_workload[flag] = sit_pts
        if pass_pts:
            pass_series_by_workload[flag] = pass_pts

    _line_svg(
        plots_dir / f"common_sit_median_by_workload_{common_mode}.svg",
        f"Common SIT Median by Workload{mode_suffix}",
        workloads_present,
        "sit_median",
        sit_series_by_workload,
        x_label="workload",
    )
    _line_svg(
        plots_dir / f"common_invariant_pass_rate_by_workload_{common_mode}.svg",
        f"Common Invariant Pass Rate by Workload{mode_suffix}",
        workloads_present,
        "pass rate (%)",
        pass_series_by_workload,
        x_label="workload",
    )
    return 0


def parse_sizes(args: argparse.Namespace) -> List[str]:
    if args.all_sizes:
        return list(ALL_SIZES)
    if args.workload_sizes:
        return list(args.workload_sizes)
    return [args.workload_size]


def run_monotonic_matrix_checks(
    *,
    repo: Path,
    outdir: Path,
    trace_index_rows: List[Dict[str, str]],
    python_exec: str,
    min_sit_drop: float,
    min_stall_rise: float,
    max_idle_rise: float,
) -> int:
    grouped: Dict[Tuple[str, str], Dict[str, str]] = defaultdict(dict)
    for row in trace_index_rows:
        workload = row.get("workload", "")
        workload_size = row.get("workload_size", "")
        flag_mode = row.get("flag_mode", "")
        trace_id = row.get("trace_id", "")
        if workload and workload_size and flag_mode and trace_id:
            grouped[(workload, workload_size)][flag_mode] = trace_id

    checker = repo / "tests" / "check_flag_monotonicity.py"
    if not checker.exists():
        print(f"FAIL: monotonic checker not found: {checker}")
        return 2

    report_rows: List[Dict[str, str]] = []
    failures: List[str] = []
    total_run = 0

    for (workload, workload_size), flag_to_tid in sorted(
        grouped.items(), key=lambda kv: (workload_sort_key(kv[0][0]), SIZE_ORDER.get(kv[0][1], 999))
    ):
        base_tid = flag_to_tid.get("none")
        if not base_tid:
            report_rows.append(
                {
                    "workload": workload,
                    "workload_size": workload_size,
                    "variants_checked": "",
                    "status": "skip",
                    "reason": "missing baseline flag_mode=none",
                }
            )
            continue

        base_summary = outdir / f"{base_tid}__base_summary.json"
        if not base_summary.exists():
            msg = f"{workload}/{workload_size}: missing baseline summary {base_summary}"
            failures.append(msg)
            report_rows.append(
                {
                    "workload": workload,
                    "workload_size": workload_size,
                    "variants_checked": "",
                    "status": "fail",
                    "reason": msg,
                }
            )
            continue

        cmd = [
            python_exec,
            str(checker),
            "--baseline",
            str(base_summary),
            "--min-sit-drop",
            str(min_sit_drop),
            "--min-stall-rise",
            str(min_stall_rise),
            "--max-idle-rise",
            str(max_idle_rise),
        ]
        variants_checked: List[str] = []
        for arg_name, flag_mode in [
            ("--branch", "branch_mispredict"),
            ("--cache", "cache_pressure"),
            ("--both", "both"),
        ]:
            tid = flag_to_tid.get(flag_mode)
            if not tid:
                continue
            summary = outdir / f"{tid}__base_summary.json"
            if not summary.exists():
                continue
            cmd += [arg_name, str(summary)]
            variants_checked.append(flag_mode)

        if not variants_checked:
            report_rows.append(
                {
                    "workload": workload,
                    "workload_size": workload_size,
                    "variants_checked": "",
                    "status": "skip",
                    "reason": "no variant summaries found",
                }
            )
            continue

        print("$", " ".join(cmd))
        p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
        total_run += 1
        output = ((p.stdout or "") + (p.stderr or "")).strip()
        if output:
            print(output)

        status = "pass" if p.returncode == 0 else "fail"
        report_rows.append(
            {
                "workload": workload,
                "workload_size": workload_size,
                "variants_checked": ",".join(variants_checked),
                "status": status,
                "reason": "" if p.returncode == 0 else f"rc={p.returncode}",
            }
        )
        if p.returncode != 0:
            failures.append(f"{workload}/{workload_size}: monotonic check failed")

    plots_dir = outdir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    report_csv = plots_dir / "monotonic_report.csv"
    write_csv(report_csv, report_rows)
    print(f"✓ wrote: {report_csv}")

    if failures:
        print("\nFAILURES during monotonic checks:")
        for f in failures:
            print(" -", f)
        return 2

    print(f"✓ monotonic checks passed ({total_run} groups)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Run Spike workloads across size/flag matrix -> build Spike manifest -> "
            "run golden suite -> visualize invariants -> emit common combined graph."
        )
    )
    ap.add_argument("--python", default=sys.executable, help="Python executable")
    ap.add_argument("--pk", required=True, help="Path to riscv-pk for Spike")
    ap.add_argument("--workloads", nargs="+", default=DEFAULT_SPIKE_WORKLOADS)
    ap.add_argument("--workload-size", default="small", choices=["test", "tiny", "small", "med", "large"])
    ap.add_argument("--workload-sizes", nargs="+", choices=ALL_SIZES, help="Optional list of sizes (overrides --workload-size)")
    ap.add_argument("--all-sizes", action="store_true", help="Run all sizes: test,tiny,small,med,large")
    ap.add_argument("--emulated-flags", nargs="+", choices=FLAG_MODES, default=["none"])
    ap.add_argument("--time-us", type=float, default=256.0, help="time_us passed to riscvbench")
    ap.add_argument("--window-us", type=float, default=None, help="window_us for golden suite (default: --time-us)")
    ap.add_argument("--expected-work-rate", type=float, default=1.0)
    ap.add_argument("--inst-us", type=float, default=1.0)
    ap.add_argument("--resident-pc-ge", default="0x80000000")
    ap.add_argument("--isa", default="RV64GC")
    ap.add_argument("--outdir", default="golden_out_spike", help="Output directory for golden suite artifacts")
    ap.add_argument(
        "--manifest-out",
        default=None,
        help="Path to write generated Spike manifest JSON (default: <outdir>/spike_manifest.json)",
    )
    ap.add_argument("--skip-visualize", action="store_true", help="Skip visualization step")
    ap.add_argument("--skip-common-visualize", action="store_true", help="Skip common combined graph output")
    ap.add_argument("--skip-monotonic-check", action="store_true", help="Skip monotonic flag behavior checks")
    ap.add_argument("--monotonic-min-sit-drop", type=float, default=0.02, help="Minimum sit_median drop vs baseline")
    ap.add_argument("--monotonic-min-stall-rise", type=float, default=0.02, help="Minimum residency_stall_avg rise vs baseline")
    ap.add_argument("--monotonic-max-idle-rise", type=float, default=0.20, help="Maximum residency_idle_avg rise vs baseline")
    ap.add_argument("--common-mode", default="base", choices=["base", "all", "skip_w0", "partial", "exact_boundary"])
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    window_us = float(args.window_us) if args.window_us is not None else float(args.time_us)
    sizes = parse_sizes(args)
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    traces_out = outdir / "traces"
    traces_out.mkdir(parents=True, exist_ok=True)
    manifest_out = Path(args.manifest_out).resolve() if args.manifest_out else (outdir / "spike_manifest.json")

    traces: List[Path] = []
    trace_index_rows: List[Dict[str, str]] = []
    failures: List[str] = []

    # 1) Generate Spike traces through the standard pipeline.
    case_id = 0
    total_cases = len(args.workloads) * len(sizes) * len(args.emulated_flags)
    print(f"Running Spike cases sequentially: total={total_cases}")
    for wl in args.workloads:
        for sz in sizes:
            for flag_mode in args.emulated_flags:
                branch_mispredict = flag_mode in {"branch_mispredict", "both"}
                cache_pressure = flag_mode in {"cache_pressure", "both"}
                case_id += 1
                trace_id = f"trace_{case_id:04d}"
                print(
                    f">>> case {case_id}/{total_cases}: "
                    f"workload={wl} size={sz} flag={flag_mode}"
                )

                cmd = [
                    args.python,
                    str(repo / "riscvbench.py"),
                    "--target",
                    "spike",
                    "--workload",
                    wl,
                    "--workload_size",
                    sz,
                    "--time_us",
                    str(args.time_us),
                    "--expected-work-rate",
                    str(args.expected_work_rate),
                    "--pk",
                    args.pk,
                    "--isa",
                    str(args.isa),
                    "--inst_us",
                    str(args.inst_us),
                    "--resident_pc_ge",
                    str(args.resident_pc_ge),
                ]
                if branch_mispredict:
                    cmd.append("--branch-mispredict")
                if cache_pressure:
                    cmd.append("--cache-pressure")

                rc = run(cmd, cwd=repo)
                if rc != 0:
                    failures.append(f"spike run failed workload={wl} size={sz} flags={flag_mode} rc={rc}")
                    continue

                trace_csv = repo / "runs" / "spike" / wl / sz / "trace.csv"
                if not trace_csv.exists():
                    failures.append(f"missing trace.csv workload={wl} size={sz} flags={flag_mode}: {trace_csv}")
                    continue

                dst = traces_out / f"{trace_id}.csv"
                shutil.copyfile(trace_csv, dst)
                traces.append(dst)
                trace_index_rows.append(
                    {
                        "trace_id": trace_id,
                        "trace_path": str(dst.resolve()),
                        "workload": wl,
                        "workload_size": sz,
                        "flag_mode": flag_mode,
                        "branch_mispredict": bool_to_int(branch_mispredict),
                        "cache_pressure": bool_to_int(cache_pressure),
                    }
                )

    if failures:
        print("\nFAILURES during Spike generation:")
        for f in failures:
            print(" -", f)
        return 2
    if not traces:
        print("No Spike traces generated; aborting.")
        return 2

    trace_index_csv = outdir / "trace_index.csv"
    write_csv(trace_index_csv, trace_index_rows)
    print(f"✓ wrote trace index: {trace_index_csv}")

    # 2) Build manifest pinned to generated Spike traces.
    manifest = build_manifest(
        repo,
        traces,
        window_us=window_us,
        dataset_version=f"spike-golden-v1-{len(traces)}traces",
    )
    manifest_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"✓ wrote manifest: {manifest_out}")

    # 3) Run golden suite over Spike-generated traces.
    cmd_golden = [
        args.python,
        str(repo / "tests" / "run_golden_suite.py"),
        "--manifest",
        str(manifest_out),
        "--outdir",
        str(outdir),
        "--window-us",
        str(window_us),
    ]
    rc = run(cmd_golden, cwd=repo)
    if rc != 0:
        return rc

    # 4) Monotonic flag-behavior checks on base mode summaries.
    if not args.skip_monotonic_check:
        rc = run_monotonic_matrix_checks(
            repo=repo,
            outdir=outdir,
            trace_index_rows=trace_index_rows,
            python_exec=args.python,
            min_sit_drop=float(args.monotonic_min_sit_drop),
            min_stall_rise=float(args.monotonic_min_stall_rise),
            max_idle_rise=float(args.monotonic_max_idle_rise),
        )
        if rc != 0:
            return rc

    # 5) Optional invariant visualization.
    if not args.skip_visualize:
        cmd_vis = [
            args.python,
            str(repo / "tests" / "visualize_golden_invariants.py"),
            "--golden-out",
            str(outdir),
            "--window-us",
            str(window_us),
        ]
        rc = run(cmd_vis, cwd=repo)
        if rc != 0:
            return rc

    # 6) Common aggregated outputs across all sizes/flags/workloads.
    if not args.skip_common_visualize:
        rc = build_common_outputs(outdir=outdir, common_mode=args.common_mode)
        if rc != 0:
            return rc

    print("\n✓ Spike golden pipeline complete")
    print(f"  outdir: {outdir}")
    print(f"  manifest: {manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
