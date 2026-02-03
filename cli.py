#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

# --- terminal formatting helpers ---
def ok(msg: str) -> None:
    print(f"\u2713 {msg}")   # ✓

def info(msg: str) -> None:
    print(f"\u203A {msg}")   # ›

def blank() -> None:
    print("")

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def cmd_ingest(args) -> int:
    """
    Phase-1 ingest (baseline adapter):
      - CPU adapter parses raw trace format
      - Baseline adapter validates via ingest_api
      - Save normalized trace to CSV
      - Record run manifest
      - Print CLI stats
    """
    from adapters.baseline_adapter import BaselineAdapter

    outdir = Path(args.out)
    ensure_dir(outdir)

    trace_path = Path(args.trace).resolve()
    if not trace_path.exists():
        print(f"trace not found: {trace_path}")
        return 2

    # Determine trace format
    trace_format = "raw" if args.format == "cpu" else "csv"
    
    # Baseline adapter handles both CSV and raw (via CPU adapter)
    try:
        adapter = BaselineAdapter(str(trace_path), trace_format=trace_format)
        df = adapter.load_state_intervals()
    except Exception as e:
        print(f"adapter error: {e}")
        return 2

    if "core" not in df.columns:
        print("trace missing required column: core")
        return 2

    # Save normalized trace as CSV for engine
    normalized_trace = outdir / "trace.csv"
    df.to_csv(normalized_trace, index=False)

    cores = sorted(df["core"].unique().tolist())
    n_events = int(len(df))
    n_cores = int(len(cores))

    # Pretty event count: show raw count for small traces, M for big traces
    if n_events >= 1_000_000:
        ev_str = f"{n_events/1e6:.1f} M"
    else:
        ev_str = f"{n_events}"

    core_str = "core" if n_cores == 1 else "cores"

    manifest = {
        "trace": str(normalized_trace),
        "original_trace": str(trace_path),
        "format": args.format,
        "events": n_events,
        "cores": cores,
    }

    # If CPU/raw format, try to derive and save residency intervals
    if trace_format == "raw":
        try:
            resid_df = adapter.load_residency_intervals()
            if resid_df is not None and len(resid_df) > 0:
                resid_path = outdir / "residency.csv"
                resid_df.to_csv(resid_path, index=False)
                manifest["residency"] = str(resid_path)
        except Exception:
            # Non-fatal: continue without residency
            pass

    # If baseline CSV ingest, check for sibling residency files to include
    if trace_format == "csv":
        trace_dir = trace_path.parent
        candidates = [trace_dir / "residency.csv", trace_dir / "residency_intervals.csv", trace_dir / "inputs" / "residency_intervals.csv"]
        for c in candidates:
            if c.exists():
                manifest["residency"] = str(c)
                break
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    blank()
    ok(f"parsed {ev_str} events across {n_cores} {core_str}")
    blank()
    return 0



def cmd_classify(args) -> int:
    """
    Phase-1 classify:
      - Loads manifest
      - Runs engine with adapter inputs
      - Writes stable artifacts into run dir
      - Prints demo-style CLI output
    """
    outdir = Path(args.in_dir)
    manifest_path = outdir / "manifest.json"
    if not manifest_path.exists():
        print("missing manifest.json in", outdir)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    trace = manifest["trace"]
    # Use residency from manifest if user didn't pass one
    residency_path = None
    if args.residency is not None:
        rp = Path(args.residency).resolve()
        if not rp.exists():
            print("residency file not found:", rp)
            return 2
        residency_path = str(rp)
    else:
        # fallback to manifest entry if present
        if "residency" in manifest:
            residency_path = manifest.get("residency")

    # Resolve engine path robustly (works after pip install -e .)
    engine_py = (Path(__file__).resolve().parent / "sit_engine_phase1.py")
    if not engine_py.exists():
        print("engine file not found:", engine_py)
        return 2

    # residency_path already set above

    # Pretty header (matches your target)
    blank()
    if residency_path:
        info("applying residency classifiers")
    else:
        print(f"$ sit-engine classify --windows {int(args.window_us)}us")
        info("no residency gating")

    info("detecting SIT windows and thresholds")
    blank()

    out_prefix = outdir / "run"  # produces run_windows.csv + run_summary.json

    cmd = [
        sys.executable, str(engine_py),
        "--trace", trace,
        "--window-us", str(args.window_us),
        "--out-prefix", str(out_prefix),
    ]
    if residency_path:
        cmd += ["--residency", residency_path]

    p = subprocess.run(cmd)
    if p.returncode != 0:
        return p.returncode

    # Stable names in run dir
    src_windows = Path(str(out_prefix) + "_windows.csv")
    src_summary = Path(str(out_prefix) + "_summary.json")

    if not src_windows.exists() or not src_summary.exists():
        print("engine did not produce expected outputs")
        return 2

    shutil.copyfile(src_windows, outdir / "windows.csv")
    shutil.copyfile(src_summary, outdir / "summary.json")

    ok("windows ready")
    ok("summary ready")
    blank()
    return 0



def cmd_export(args) -> int:
    """
    Phase-1 export:
      - Copies artifacts into versioned names (schema v1)
      - Prints a clean summary block like the reference CLI
    """
    outdir = Path(args.in_dir)
    windows = outdir / "windows.csv"
    summary = outdir / "summary.json"
    if not windows.exists() or not summary.exists():
        print("missing windows.csv/summary.json in", outdir)
        return 2

    export_dir = outdir / "export"
    ensure_dir(export_dir)

    # Copy with explicit schema version names
    shutil.copyfile(windows, export_dir / "windows_v1.csv")
    shutil.copyfile(summary, export_dir / "summary_v1.json")

    # Load summary for printing
    s = json.loads(summary.read_text(encoding="utf-8"))

    def pct(x: float) -> str:
        if x != x:  # NaN
            return "nan"
        return f"{100.0 * x:.1f}%"

    blank()
    ok("summary")
    blank()

    def row(k: str, v: str) -> None:
        print(f"  {k:<16} {v}")

    # Defensive formatting (handles NaN)
    sit_median = float(s.get("sit_median", float("nan")))
    sit_p95 = float(s.get("sit_p95", float("nan")))
    idle_avg = float(s.get("residency_idle_avg", float("nan")))
    stall_avg = float(s.get("residency_stall_avg", float("nan")))

    row("sit_median", f"{sit_median:.2f}" if sit_median == sit_median else "nan")
    row("sit_p95", f"{sit_p95:.2f}" if sit_p95 == sit_p95 else "nan")
    row("residency_idle", pct(idle_avg))
    row("residency_stall", pct(stall_avg))
    blank()

    ok(f"data ready: {export_dir}")
    blank()
    return 0


def main():
    ap = argparse.ArgumentParser(prog="sit-engine (phase1)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("--trace", required=True)
    p_ing.add_argument("--format", default="baseline", choices=["baseline", "cpu"])
    p_ing.add_argument("--out", required=True)
    p_ing.set_defaults(fn=cmd_ingest)

    p_cls = sub.add_parser("classify")
    p_cls.add_argument("--in", dest="in_dir", required=True)
    p_cls.add_argument("--window-us", type=float, default=256.0)
    p_cls.add_argument("--residency", default=None)
    p_cls.set_defaults(fn=cmd_classify)

    p_exp = sub.add_parser("export")
    p_exp.add_argument("--in", dest="in_dir", required=True)
    p_exp.add_argument("--schema", default="v1", choices=["v1"])
    p_exp.set_defaults(fn=cmd_export)
    p_exp.add_argument("--format", default="csv", choices=["csv"])
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
