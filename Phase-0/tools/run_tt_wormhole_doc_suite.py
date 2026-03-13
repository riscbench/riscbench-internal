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
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


REPO_ROOT = repo_root()
PHASE2_ROOT = REPO_ROOT / "Phase-2"
CLI_PY = PHASE2_ROOT / "cli.py"
PLOTTER_PY = PHASE2_ROOT / "sweeps" / "plot_spike_window_diagnostics.py"
VIS_PY = PHASE2_ROOT / "sweeps" / "visualize_sweep_results.py"
HEATMAP_PY = PHASE2_ROOT / "tools" / "generate_window_heatmaps.py"


def now_stamp() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


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


def rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def infer_family(case_name: str) -> str:
    name = case_name.lower()
    if "loopback" in name:
        return "loopback"
    if "matmul" in name:
        return "matmul"
    if "vecadd" in name or "noc_transfer" in name:
        return "streaming"
    if "sfpu" in name or "sfpi" in name:
        return "sfpu"
    if "eltwise" in name:
        return "eltwise"
    return "other"


def infer_proxy_workload(case_name: str) -> str:
    name = case_name.lower()
    if "loopback" in name:
        return "fm_loopback"
    if "matmul" in name:
        return "matmul"
    if "vecadd" in name:
        return "streaming_proxy"
    if "noc_transfer" in name:
        return "streaming_stall_control"
    if "sfpu" in name or "sfpi" in name:
        return "sfpu_proxy"
    if "eltwise" in name:
        return "eltwise_proxy"
    return "other"


def infer_size(case_name: str) -> str:
    name = case_name.lower()
    if name.endswith("_single"):
        return "single"
    if name.endswith("_multi"):
        return "multi"
    return "native"


def is_compute_family(family: str) -> bool:
    return family in {"matmul", "sfpu", "eltwise"}


def extract_console_status(console_log: Path) -> str:
    if not console_log.exists():
        return "missing_console"
    text = console_log.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"PCC\s*=\s*([0-9.]+)", text)
    if m:
        return f"PCC={m.group(1)}"
    m = re.search(r"Result\s*=\s*([^\s:]+)\s*:\s*Expected\s*=\s*([^\s:]+)", text)
    if m and m.group(1) == m.group(2):
        return f"result_matches_expected({m.group(1)})"
    if "All results match expected values within tolerance." in text:
        return "results_match_expected"
    if "Test Passed" in text:
        return "test_passed"
    if "Kernel execution finished" in text:
        return "kernel_execution_finished"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return "empty_console"
    return lines[-1][:120]


def run_cmd(
    *,
    cmd: List[str],
    cwd: Path,
    label: str,
    verbose: bool,
) -> Tuple[int, str, float]:
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0
    out = (p.stdout or "") + (p.stderr or "")
    rc = int(p.returncode)
    if verbose:
        print(f"[{label}] rc={rc} elapsed={elapsed:.3f}s")
        print("  $ " + " ".join(cmd))
        if out.strip():
            print(out.rstrip())
    return rc, out, elapsed


def discover_cases(dataset_root: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    runnable: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    for case_dir in sorted(p for p in dataset_root.iterdir() if p.is_dir()):
        name = case_dir.name
        profile_csv = case_dir / "profiler_logs" / "profile_log_device.csv"
        zone_log = case_dir / "profiler_logs" / "zone_src_locations.log"
        zone_log_alt = case_dir / "profiler_logs" / "new_zone_src_locations.log"
        console_log = case_dir / "console.log"

        if not profile_csv.exists():
            skipped.append({"case": name, "status": "skip", "reason": "missing profile_log_device.csv"})
            continue

        chosen_zone = zone_log if zone_log.exists() else zone_log_alt
        if not chosen_zone.exists():
            skipped.append({"case": name, "status": "skip", "reason": "missing zone_src_locations.log"})
            continue

        runnable.append(
            {
                "case": name,
                "profile_csv": str(profile_csv.resolve()),
                "zone_log": str(chosen_zone.resolve()),
                "console_log": str(console_log.resolve()),
                "tt_family": infer_family(name),
                "proxy_workload": infer_proxy_workload(name),
                "workload_size": infer_size(name),
            }
        )
    return runnable, skipped


def load_summary(summary_json: Path) -> Dict[str, object]:
    return json.loads(summary_json.read_text(encoding="utf-8"))


def aggregate_windows(raw_windows: Path, aggregate_out: Path) -> Dict[str, int]:
    with raw_windows.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    cores = sorted({int(float(r["core"])) for r in rows if (r.get("core") or "").strip()})
    total_cores = max(1, len(cores))

    acc: Dict[int, Dict[str, float]] = {}
    for raw in rows:
        wid = int(float(raw["window_id"]))
        start_us = to_float(raw.get("window_start_us"), 0.0)
        end_us = to_float(raw.get("window_end_us"), start_us)
        resident_us = max(0.0, to_float(raw.get("resident_us"), 0.0))
        active_frac = max(0.0, min(1.0, to_float(raw.get("active_frac"), 0.0)))
        stall_frac = max(0.0, min(1.0, to_float(raw.get("stall_frac"), 0.0)))
        idle_frac = max(0.0, min(1.0, to_float(raw.get("idle_frac"), 0.0)))
        sit = to_float(raw.get("sit"))
        sit_window_active = to_float(raw.get("sit_no_work_window_active"))

        item = acc.setdefault(
            wid,
            {
                "window_id": float(wid),
                "window_start_us": start_us,
                "window_end_us": end_us,
                "resident_total_us": 0.0,
                "active_total_us": 0.0,
                "stall_total_us": 0.0,
                "idle_total_us": 0.0,
                "sit_weighted": 0.0,
                "sit_weight": 0.0,
                "sit_window_active_weighted": 0.0,
                "sit_window_active_weight": 0.0,
                "present_rows": 0.0,
            },
        )
        item["window_start_us"] = min(item["window_start_us"], start_us)
        item["window_end_us"] = max(item["window_end_us"], end_us)
        item["resident_total_us"] += resident_us
        item["active_total_us"] += resident_us * active_frac
        item["stall_total_us"] += resident_us * stall_frac
        item["idle_total_us"] += resident_us * idle_frac
        if math.isfinite(sit) and resident_us > 0:
            item["sit_weighted"] += sit * resident_us
            item["sit_weight"] += resident_us
        if math.isfinite(sit_window_active) and resident_us > 0:
            item["sit_window_active_weighted"] += sit_window_active * resident_us
            item["sit_window_active_weight"] += resident_us
        item["present_rows"] += 1.0

    aggregate_out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "core",
        "window_id",
        "window_start_us",
        "window_end_us",
        "resident_us",
        "resident_frac_of_window",
        "is_resident_window",
        "active_frac",
        "stall_frac",
        "idle_frac",
        "sit",
        "sit_no_work_window_active",
        "source_cores",
    ]
    with aggregate_out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for wid in sorted(acc.keys()):
            item = acc[wid]
            window_us = max(0.0, item["window_end_us"] - item["window_start_us"])
            resident_mean_us = item["resident_total_us"] / float(total_cores)
            resident_frac = 0.0 if window_us <= 0 else min(1.0, resident_mean_us / window_us)
            if item["resident_total_us"] > 0.0:
                active_frac = item["active_total_us"] / item["resident_total_us"]
                stall_frac = item["stall_total_us"] / item["resident_total_us"]
                idle_frac = item["idle_total_us"] / item["resident_total_us"]
            else:
                active_frac = float("nan")
                stall_frac = float("nan")
                idle_frac = float("nan")
            sit = (
                item["sit_weighted"] / item["sit_weight"]
                if item["sit_weight"] > 0.0
                else float("nan")
            )
            sit_window_active = (
                item["sit_window_active_weighted"] / item["sit_window_active_weight"]
                if item["sit_window_active_weight"] > 0.0
                else float("nan")
            )
            writer.writerow(
                {
                    "core": 0,
                    "window_id": int(item["window_id"]),
                    "window_start_us": f"{item['window_start_us']:.6f}",
                    "window_end_us": f"{item['window_end_us']:.6f}",
                    "resident_us": f"{resident_mean_us:.6f}",
                    "resident_frac_of_window": f"{resident_frac:.6f}",
                    "is_resident_window": 1 if resident_mean_us > 0.0 else 0,
                    "active_frac": "" if not math.isfinite(active_frac) else f"{active_frac:.6f}",
                    "stall_frac": "" if not math.isfinite(stall_frac) else f"{stall_frac:.6f}",
                    "idle_frac": "" if not math.isfinite(idle_frac) else f"{idle_frac:.6f}",
                    "sit": "" if not math.isfinite(sit) else f"{sit:.6f}",
                    "sit_no_work_window_active": "" if not math.isfinite(sit_window_active) else f"{sit_window_active:.6f}",
                    "source_cores": total_cores,
                }
            )

    return {"source_rows": len(rows), "source_cores": total_cores, "aggregate_windows": len(acc)}


def write_csv(rows: List[Dict[str, object]], out_path: Path) -> None:
    if not rows:
        return
    fieldnames = sorted({str(k) for row in rows for k in row.keys()})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _md_escape(text: object) -> str:
    return str(text).replace("|", "\\|")


def write_bar_chart_svg(
    out_path: Path,
    *,
    title: str,
    y_label: str,
    rows: List[Dict[str, object]],
    value_key: str,
    value_fmt: str,
    color: str,
) -> None:
    items: List[Tuple[str, float]] = []
    for row in rows:
        label = str(row.get("case", "")).strip()
        value = float(row.get(value_key, float("nan")))
        if label and math.isfinite(value):
            items.append((label, value))
    if not items:
        return

    n = len(items)
    width = max(900, 110 * n)
    height = 520
    ml, mr, mt, mb = 90, 30, 48, 130
    pw = width - ml - mr
    ph = height - mt - mb
    ymax = max(v for _, v in items)
    if ymax <= 0.0:
        ymax = 1.0
    ymax *= 1.10

    bar_w = max(18.0, min(56.0, pw / max(1, n * 1.4)))
    step = pw / max(1, n)

    def sy(v: float) -> float:
        return mt + ph - (v / ymax) * ph

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2:.1f}" y="24" text-anchor="middle" font-family="sans-serif" font-size="18">{_svg_escape(title)}</text>',
        f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#222"/>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#222"/>',
    ]

    for i in range(5):
        tick = ymax * (i / 4.0)
        y = sy(tick)
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" stroke="#eee"/>')
        lines.append(f'<text x="{ml-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="11">{tick:.3f}</text>')

    for idx, (label, value) in enumerate(items):
        x = ml + idx * step + (step - bar_w) / 2.0
        y = sy(value)
        h = (mt + ph) - y
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}"/>')
        lines.append(
            f'<text x="{x + bar_w/2:.1f}" y="{y-6:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10">{value:{value_fmt}}</text>'
        )
        lines.append(
            f'<text x="{x + bar_w/2:.1f}" y="{mt+ph+18:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11" '
            f'transform="rotate(22 {x + bar_w/2:.1f} {mt+ph+18:.1f})">{_svg_escape(label)}</text>'
        )

    lines.append(
        f'<text x="{24}" y="{mt + ph/2:.1f}" transform="rotate(-90 24 {mt + ph/2:.1f})" '
        f'text-anchor="middle" font-family="sans-serif" font-size="13">{_svg_escape(y_label)}</text>'
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_report_md(
    out_path: Path,
    *,
    dataset_root: Path,
    window_us: float,
    residency_model: str,
    rows: List[Dict[str, object]],
    skipped: List[Dict[str, str]],
) -> None:
    lines: List[str] = []
    lines.append("# Tenstorrent Wormhole Documentation Suite")
    lines.append("")
    lines.append(f"- Dataset root: `{dataset_root}`")
    lines.append(f"- Window size: `{window_us}` us")
    lines.append(f"- TT residency model: `{residency_model}`")
    lines.append(f"- Generated: `{dt.datetime.utcnow().isoformat()}Z`")
    lines.append("")
    lines.append("## Cases")
    lines.append("")
    lines.append("| Case | Family | Proxy | Console Status | SIT Median | Stall Avg | Active Avg | Plot 1 | Plot 2 | Plot 3 |")
    lines.append("|---|---|---|---|---:|---:|---:|---|---|---|")
    for row in rows:
        if int(row.get("returncode", 1)) != 0:
            continue
        plot1 = Path(str(row.get("plot1_svg", "")))
        plot2 = Path(str(row.get("plot2_svg", "")))
        plot3 = Path(str(row.get("plot3_svg", "")))
        plot1_rel = rel_to_repo(plot1) if plot1.exists() else ""
        plot2_rel = rel_to_repo(plot2) if plot2.exists() else ""
        plot3_rel = rel_to_repo(plot3) if plot3.exists() else ""
        lines.append(
            "| {case} | {family} | {proxy} | {console} | {sit:.6f} | {stall:.2f}% | {active:.2f}% | {plot1} | {plot2} | {plot3} |".format(
                case=_md_escape(row.get("case", "")),
                family=_md_escape(row.get("tt_family", "")),
                proxy=_md_escape(row.get("proxy_workload", "")),
                console=_md_escape(row.get("console_status", "")),
                sit=float(row.get("sit_median", float("nan"))),
                stall=100.0 * float(row.get("residency_stall_avg", float("nan"))),
                active=100.0 * float(row.get("residency_active_avg", float("nan"))),
                plot1=f"[svg]({plot1_rel})" if plot1_rel else "",
                plot2=f"[svg]({plot2_rel})" if plot2_rel else "",
                plot3=f"[svg]({plot3_rel})" if plot3_rel else "",
            )
        )
    lines.append("")
    lines.append("## Heatmaps")
    lines.append("")
    for row in rows:
        if int(row.get("returncode", 1)) != 0:
            continue
        active = Path(str(row.get("heatmap_active_svg", "")))
        stall = Path(str(row.get("heatmap_stall_svg", "")))
        idle = Path(str(row.get("heatmap_idle_svg", "")))
        resident = Path(str(row.get("heatmap_resident_svg", "")))
        sit = Path(str(row.get("heatmap_sit_svg", "")))
        refs = []
        if active.exists():
            refs.append(f"[active]({rel_to_repo(active)})")
        if stall.exists():
            refs.append(f"[stall]({rel_to_repo(stall)})")
        if idle.exists():
            refs.append(f"[idle]({rel_to_repo(idle)})")
        if resident.exists():
            refs.append(f"[resident]({rel_to_repo(resident)})")
        if sit.exists():
            refs.append(f"[sit]({rel_to_repo(sit)})")
        if refs:
            lines.append(f"- `{row.get('case', '')}`: " + " | ".join(refs))
    lines.append("")
    lines.append("## Skipped")
    lines.append("")
    if skipped:
        for row in skipped:
            lines.append(f"- `{row['case']}`: {row['reason']}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## Main Artifacts")
    lines.append("")
    lines.append("- `sweep_results.csv`: TT case manifest for aggregate visualization")
    lines.append("- `tt_doc_summary.csv`: documentation summary table with metrics and plot paths")
    lines.append("- `tt_compute_summary.csv`: compute-only TT subset (matmul/sfpu/eltwise)")
    lines.append("- `plots/common_sit_median_by_workload.svg`: RISCVBench-style case summary plot")
    lines.append("- `plots/tt_sit_median_by_case.svg`: TT case bar chart")
    lines.append("- `plots/tt_compute_sit_median_by_case.svg`: compute-only SIT bar chart")
    lines.append("- `plots/tt_compute_residency_active_pct_by_case.svg`: compute-only active-residency bar chart")
    lines.append("- `plots/tt_compute_residency_stall_pct_by_case.svg`: compute-only stall-residency bar chart")
    lines.append("- `cases/<case>/plots/*`: per-case SIT timeline, stacked breakdown, and window-profile diagnostics")
    lines.append("- `cases/<case>/plots/*heatmap*.svg`: per-case active/stall/idle/residency/SIT heatmaps")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Run all Tenstorrent Wormhole profiler bundles through the Phase-2 "
            "pipeline and generate documentation-ready summaries and plots."
        )
    )
    ap.add_argument(
        "--dataset-root",
        default=str(PHASE2_ROOT / "datasets" / "Tenstorrent_test_raw_files-main"),
        help="Root directory containing tt_* case folders.",
    )
    ap.add_argument(
        "--outdir",
        default=str(PHASE2_ROOT / "tt_doc_runs" / now_stamp()),
        help="Output directory for TT documentation artifacts.",
    )
    ap.add_argument("--python", default=sys.executable, help="Python executable")
    ap.add_argument("--window-us", type=float, default=256.0, help="Window size for classify")
    ap.add_argument(
        "--tt-output-mode",
        choices=["tile", "lane"],
        default="tile",
        help="TT adapter output mode. Use tile for documentation-level summaries.",
    )
    ap.add_argument(
        "--tt-residency-model",
        choices=["kernel_envelope", "active_span"],
        default="kernel_envelope",
        help="TT adapter residency policy to use for this documentation run.",
    )
    ap.add_argument("--no-strict-pairing", action="store_true", help="Disable strict START/END pairing checks.")
    ap.add_argument("--no-strict-map-hit", action="store_true", help="Disable strict zone-map hit checks.")
    ap.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional subset of case directory names to run (e.g. tt_vecadd tt_matmul_multi).",
    )
    ap.add_argument("--verbose", action="store_true", help="Print full subprocess commands and outputs.")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    if not dataset_root.exists():
        raise SystemExit(f"dataset root not found: {dataset_root}")
    if not CLI_PY.exists():
        raise SystemExit(f"missing cli.py: {CLI_PY}")
    if not PLOTTER_PY.exists():
        raise SystemExit(f"missing plotter: {PLOTTER_PY}")
    if not VIS_PY.exists():
        raise SystemExit(f"missing visualizer: {VIS_PY}")
    if not HEATMAP_PY.exists():
        raise SystemExit(f"missing heatmap tool: {HEATMAP_PY}")

    runnable, skipped = discover_cases(dataset_root)
    if args.cases:
        selected = set(args.cases)
        runnable = [row for row in runnable if row["case"] in selected]
        skipped.extend(
            {"case": case, "status": "skip", "reason": "filtered out by --cases"}
            for case in sorted(selected - {row["case"] for row in runnable})
        )

    summary_rows: List[Dict[str, object]] = []
    sweep_rows: List[Dict[str, object]] = []
    window_plot_rows: List[Dict[str, object]] = []
    custom_order: List[str] = []

    for idx, case in enumerate(runnable, start=1):
        case_name = case["case"]
        custom_order.append(case_name)
        case_root = outdir / "cases" / case_name
        run_root = case_root / "run"
        plots_root = case_root / "plots"
        run_root.mkdir(parents=True, exist_ok=True)
        plots_root.mkdir(parents=True, exist_ok=True)

        elapsed_total = 0.0
        failure_rc = 0
        failure_reason = ""

        ingest_cmd = [
            args.python,
            str(CLI_PY),
            "ingest",
            "--trace",
            case["profile_csv"],
            "--format",
            "tt_wormhole",
            "--zone-log",
            case["zone_log"],
            "--tt-output-mode",
            args.tt_output_mode,
            "--tt-residency-model",
            args.tt_residency_model,
            "--out",
            str(run_root),
        ]
        if not args.no_strict_pairing:
            ingest_cmd.append("--strict-pairing")
        if not args.no_strict_map_hit:
            ingest_cmd.append("--strict-map-hit")
        rc, out, elapsed = run_cmd(cmd=ingest_cmd, cwd=REPO_ROOT, label=f"{case_name}:ingest", verbose=args.verbose)
        elapsed_total += elapsed
        if rc != 0:
            failure_rc = rc
            failure_reason = "ingest failed"

        if failure_rc == 0:
            classify_cmd = [
                args.python,
                str(CLI_PY),
                "classify",
                "--in",
                str(run_root),
                "--window-us",
                str(args.window_us),
            ]
            rc, out, elapsed = run_cmd(cmd=classify_cmd, cwd=REPO_ROOT, label=f"{case_name}:classify", verbose=args.verbose)
            elapsed_total += elapsed
            if rc != 0:
                failure_rc = rc
                failure_reason = "classify failed"

        if failure_rc == 0:
            export_cmd = [
                args.python,
                str(CLI_PY),
                "export",
                "--in",
                str(run_root),
            ]
            rc, out, elapsed = run_cmd(cmd=export_cmd, cwd=REPO_ROOT, label=f"{case_name}:export", verbose=args.verbose)
            elapsed_total += elapsed
            if rc != 0:
                failure_rc = rc
                failure_reason = "export failed"

        trace_csv = run_root / "trace.csv"
        summary_json = run_root / "summary.json"
        windows_csv = run_root / "windows.csv"
        aggregate_windows_csv = case_root / "aggregate_windows.csv"
        plot1_svg = plots_root / f"{case_name}__plot1_sit_vs_time.svg"
        plot2_svg = plots_root / f"{case_name}__plot2_window_breakdown_stacked.svg"
        plot3_svg = plots_root / f"{case_name}__plot3_sit_window_profile.svg"
        breakdown_csv = plots_root / f"{case_name}__window_breakdown.csv"
        heatmap_active_svg = plots_root / f"{case_name}__heatmap_active_frac.svg"
        heatmap_stall_svg = plots_root / f"{case_name}__heatmap_stall_frac.svg"
        heatmap_idle_svg = plots_root / f"{case_name}__heatmap_idle_frac.svg"
        heatmap_resident_svg = plots_root / f"{case_name}__heatmap_resident_frac_of_window.svg"
        heatmap_sit_svg = plots_root / f"{case_name}__heatmap_sit_metric.svg"
        heatmap_manifest_csv = plots_root / f"{case_name}__heatmap_manifest.csv"

        aggregate_meta: Dict[str, int] = {"source_rows": 0, "source_cores": 0, "aggregate_windows": 0}
        plot_status = "skip"
        plot_reason = ""
        if failure_rc == 0 and windows_csv.exists():
            try:
                aggregate_meta = aggregate_windows(windows_csv, aggregate_windows_csv)
            except Exception as exc:
                failure_rc = 2
                failure_reason = f"aggregate windows failed: {exc}"

        if failure_rc == 0 and aggregate_windows_csv.exists():
            plot_cmd = [
                args.python,
                str(PLOTTER_PY),
                "--windows-csv",
                str(aggregate_windows_csv),
                "--out-dir",
                str(plots_root),
                "--prefix",
                case_name,
                "--platform-label",
                "Tenstorrent",
            ]
            rc, out, elapsed = run_cmd(cmd=plot_cmd, cwd=REPO_ROOT, label=f"{case_name}:plots", verbose=args.verbose)
            elapsed_total += elapsed
            if rc != 0:
                failure_rc = rc
                failure_reason = "plot generation failed"
                plot_status = "fail"
                plot_reason = "plotter returned non-zero"
            else:
                plot_status = "pass"
                plot_reason = ""

        if failure_rc == 0 and windows_csv.exists():
            heatmap_cmd = [
                args.python,
                str(HEATMAP_PY),
                "--windows-csv",
                str(windows_csv),
                "--out-dir",
                str(plots_root),
                "--prefix",
                case_name,
                "--platform-label",
                "Tenstorrent",
            ]
            rc, out, elapsed = run_cmd(cmd=heatmap_cmd, cwd=REPO_ROOT, label=f"{case_name}:heatmaps", verbose=args.verbose)
            elapsed_total += elapsed
            if rc != 0:
                failure_rc = rc
                failure_reason = "heatmap generation failed"

        console_status = extract_console_status(Path(case["console_log"]))
        summary_obj: Dict[str, object] = {}
        if summary_json.exists():
            try:
                summary_obj = load_summary(summary_json)
            except Exception:
                summary_obj = {}

        summary_row: Dict[str, object] = {
            "case": case_name,
            "case_id": idx,
            "status": "pass" if failure_rc == 0 else "fail",
            "reason": failure_reason,
            "returncode": failure_rc,
            "elapsed_s": round(elapsed_total, 6),
            "tt_family": case["tt_family"],
            "proxy_workload": case["proxy_workload"],
            "workload_size": case["workload_size"],
            "profile_csv": case["profile_csv"],
            "zone_log": case["zone_log"],
            "console_log": case["console_log"],
            "console_status": console_status,
            "trace_csv": str(trace_csv.resolve()) if trace_csv.exists() else "",
            "windows_csv": str(windows_csv.resolve()) if windows_csv.exists() else "",
            "aggregate_windows_csv": str(aggregate_windows_csv.resolve()) if aggregate_windows_csv.exists() else "",
            "summary_json": str(summary_json.resolve()) if summary_json.exists() else "",
            "plot1_svg": str(plot1_svg.resolve()) if plot1_svg.exists() else "",
            "plot2_svg": str(plot2_svg.resolve()) if plot2_svg.exists() else "",
            "plot3_svg": str(plot3_svg.resolve()) if plot3_svg.exists() else "",
            "breakdown_csv": str(breakdown_csv.resolve()) if breakdown_csv.exists() else "",
            "heatmap_manifest_csv": str(heatmap_manifest_csv.resolve()) if heatmap_manifest_csv.exists() else "",
            "heatmap_active_svg": str(heatmap_active_svg.resolve()) if heatmap_active_svg.exists() else "",
            "heatmap_stall_svg": str(heatmap_stall_svg.resolve()) if heatmap_stall_svg.exists() else "",
            "heatmap_idle_svg": str(heatmap_idle_svg.resolve()) if heatmap_idle_svg.exists() else "",
            "heatmap_resident_svg": str(heatmap_resident_svg.resolve()) if heatmap_resident_svg.exists() else "",
            "heatmap_sit_svg": str(heatmap_sit_svg.resolve()) if heatmap_sit_svg.exists() else "",
            "source_rows": aggregate_meta["source_rows"],
            "source_cores": aggregate_meta["source_cores"],
            "aggregate_windows": aggregate_meta["aggregate_windows"],
            "window_us": float(summary_obj.get("window_us", args.window_us)) if summary_obj else args.window_us,
            "windows_total": int(summary_obj.get("windows_total", 0)) if summary_obj else 0,
            "resident_windows_total": int(summary_obj.get("resident_windows_total", 0)) if summary_obj else 0,
            "sit_median": float(summary_obj.get("sit_median", float("nan"))) if summary_obj else float("nan"),
            "sit_p95": float(summary_obj.get("sit_p95", float("nan"))) if summary_obj else float("nan"),
            "tt_residency_model": args.tt_residency_model,
            "residency_idle_avg": float(summary_obj.get("residency_idle_avg", float("nan"))) if summary_obj else float("nan"),
            "residency_stall_avg": float(summary_obj.get("residency_stall_avg", float("nan"))) if summary_obj else float("nan"),
            "residency_active_avg": float(summary_obj.get("residency_active_avg", float("nan"))) if summary_obj else float("nan"),
            "used_residency_file": bool(summary_obj.get("used_residency_file", False)) if summary_obj else False,
        }
        summary_rows.append(summary_row)
        window_plot_rows.append(
            {
                "case": case_name,
                "status": plot_status if failure_rc == 0 else "skip",
                "reason": plot_reason if failure_rc == 0 else failure_reason,
                "aggregate_windows_csv": str(aggregate_windows_csv.resolve()) if aggregate_windows_csv.exists() else "",
                "plot1_svg": str(plot1_svg.resolve()) if plot1_svg.exists() else "",
                "plot2_svg": str(plot2_svg.resolve()) if plot2_svg.exists() else "",
                "plot3_svg": str(plot3_svg.resolve()) if plot3_svg.exists() else "",
                "breakdown_csv": str(breakdown_csv.resolve()) if breakdown_csv.exists() else "",
                "heatmap_manifest_csv": str(heatmap_manifest_csv.resolve()) if heatmap_manifest_csv.exists() else "",
                "heatmap_active_svg": str(heatmap_active_svg.resolve()) if heatmap_active_svg.exists() else "",
                "heatmap_stall_svg": str(heatmap_stall_svg.resolve()) if heatmap_stall_svg.exists() else "",
                "heatmap_idle_svg": str(heatmap_idle_svg.resolve()) if heatmap_idle_svg.exists() else "",
                "heatmap_resident_svg": str(heatmap_resident_svg.resolve()) if heatmap_resident_svg.exists() else "",
                "heatmap_sit_svg": str(heatmap_sit_svg.resolve()) if heatmap_sit_svg.exists() else "",
            }
        )

        if failure_rc == 0:
            sweep_rows.append(
                {
                    "case_id": idx,
                    "elapsed_s": f"{elapsed_total:.6f}",
                    "returncode": 0,
                    "summary_copy_ok": 1,
                    "summary_path": str(summary_json.resolve()),
                    "time_us": float(summary_obj.get("window_us", args.window_us)) if summary_obj else args.window_us,
                    "trace_copy_ok": 1 if trace_csv.exists() else 0,
                    "trace_path": str(trace_csv.resolve()) if trace_csv.exists() else "",
                    "workload": case_name,
                    "workload_size": case["workload_size"],
                    "branch_mispredict": False,
                    "cache_pressure": False,
                    "tt_family": case["tt_family"],
                    "proxy_workload": case["proxy_workload"],
                }
            )

    write_csv(summary_rows, outdir / "tt_doc_summary.csv")
    write_csv(skipped, outdir / "tt_skipped_cases.csv")
    write_csv(window_plot_rows, outdir / "window_plot_report.csv")
    write_csv(sweep_rows, outdir / "sweep_results.csv")

    plots_dir = outdir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    passed_rows = [row for row in summary_rows if int(row.get("returncode", 1)) == 0]
    compute_rows = [row for row in passed_rows if is_compute_family(str(row.get("tt_family", "")))]
    write_csv(compute_rows, outdir / "tt_compute_summary.csv")

    if sweep_rows:
        vis_cmd = [
            args.python,
            str(VIS_PY),
            "--results-dir",
            str(outdir),
            "--x-field",
            "case_id",
            "--group-field",
            "tt_family",
            "--common-title-suffix",
            " (Tenstorrent Wormhole)",
            "--workload-order",
            ",".join(custom_order),
        ]
        rc, out, elapsed = run_cmd(cmd=vis_cmd, cwd=REPO_ROOT, label="aggregate:visualize", verbose=args.verbose)
        if rc != 0:
            print("warning: aggregate visualizer failed")

    write_bar_chart_svg(
        plots_dir / "tt_sit_median_by_case.svg",
        title="Tenstorrent SIT Median by Case",
        y_label="sit_median",
        rows=passed_rows,
        value_key="sit_median",
        value_fmt=".4f",
        color="#1f77b4",
    )
    stall_pct_rows = []
    active_pct_rows = []
    elapsed_rows = []
    for row in passed_rows:
        out = dict(row)
        out["residency_stall_pct"] = 100.0 * float(row.get("residency_stall_avg", float("nan")))
        out["residency_active_pct"] = 100.0 * float(row.get("residency_active_avg", float("nan")))
        stall_pct_rows.append(out)
        active_pct_rows.append(out)
        elapsed_rows.append(out)
    write_bar_chart_svg(
        plots_dir / "tt_residency_stall_pct_by_case.svg",
        title="Tenstorrent Residency Stall by Case",
        y_label="stall (%)",
        rows=stall_pct_rows,
        value_key="residency_stall_pct",
        value_fmt=".2f",
        color="#d62728",
    )
    write_bar_chart_svg(
        plots_dir / "tt_residency_active_pct_by_case.svg",
        title="Tenstorrent Residency Active by Case",
        y_label="active (%)",
        rows=active_pct_rows,
        value_key="residency_active_pct",
        value_fmt=".2f",
        color="#2ca02c",
    )
    write_bar_chart_svg(
        plots_dir / "tt_elapsed_s_by_case.svg",
        title="Tenstorrent Pipeline Runtime by Case",
        y_label="elapsed_s",
        rows=elapsed_rows,
        value_key="elapsed_s",
        value_fmt=".2f",
        color="#ff7f0e",
    )
    if compute_rows:
        compute_stall_rows = []
        compute_active_rows = []
        for row in compute_rows:
            out = dict(row)
            out["residency_stall_pct"] = 100.0 * float(row.get("residency_stall_avg", float("nan")))
            out["residency_active_pct"] = 100.0 * float(row.get("residency_active_avg", float("nan")))
            compute_stall_rows.append(out)
            compute_active_rows.append(out)
        write_bar_chart_svg(
            plots_dir / "tt_compute_sit_median_by_case.svg",
            title=f"Tenstorrent Compute SIT Median by Case ({args.tt_residency_model})",
            y_label="sit_median",
            rows=compute_rows,
            value_key="sit_median",
            value_fmt=".4f",
            color="#0f766e",
        )
        write_bar_chart_svg(
            plots_dir / "tt_compute_residency_active_pct_by_case.svg",
            title=f"Tenstorrent Compute Residency Active by Case ({args.tt_residency_model})",
            y_label="active (%)",
            rows=compute_active_rows,
            value_key="residency_active_pct",
            value_fmt=".2f",
            color="#15803d",
        )
        write_bar_chart_svg(
            plots_dir / "tt_compute_residency_stall_pct_by_case.svg",
            title=f"Tenstorrent Compute Residency Stall by Case ({args.tt_residency_model})",
            y_label="stall (%)",
            rows=compute_stall_rows,
            value_key="residency_stall_pct",
            value_fmt=".2f",
            color="#b91c1c",
        )

    write_report_md(
        outdir / "report.md",
        dataset_root=dataset_root,
        window_us=args.window_us,
        residency_model=args.tt_residency_model,
        rows=summary_rows,
        skipped=skipped,
    )

    passed = sum(1 for row in summary_rows if int(row.get("returncode", 1)) == 0)
    failed = len(summary_rows) - passed
    print(f"Wrote TT documentation bundle: {outdir}")
    print(f"Cases discovered: {len(runnable)}")
    print(f"Cases passed: {passed}")
    print(f"Cases failed: {failed}")
    print(f"Cases skipped: {len(skipped)}")
    print(f"Summary CSV: {outdir / 'tt_doc_summary.csv'}")
    print(f"Documentation report: {outdir / 'report.md'}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
