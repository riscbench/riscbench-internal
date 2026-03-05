#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def parse_float(raw: str | None) -> float:
    if raw is None:
        return float("nan")
    v = raw.strip()
    if not v or v.lower() == "nan":
        return float("nan")
    return float(v)


def approx(a: float, b: float, tol: float) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    if math.isnan(a) != math.isnan(b):
        return False
    return abs(a - b) <= tol


def load_summary(path: Path) -> Dict[str, object]:
    require(path.exists(), f"missing summary: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_windows(path: Path) -> Dict[Tuple[int, int], Dict[str, float | int]]:
    require(path.exists(), f"missing windows: {path}")
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    require(rows, f"empty windows csv: {path}")
    required_cols = {
        "core",
        "window_id",
        "is_resident_window",
        "sit",
        "sit_no_work_window_active",
        "sit_no_work_global_active",
    }
    missing = required_cols.difference(rows[0].keys())
    require(not missing, f"{path}: missing columns: {sorted(missing)}")

    out: Dict[Tuple[int, int], Dict[str, float | int]] = {}
    for row in rows:
        key = (int(float(row["core"])), int(float(row["window_id"])))
        out[key] = {
            "is_resident_window": int(float(row["is_resident_window"])),
            "sit": parse_float(row.get("sit")),
            "sit_no_work_window_active": parse_float(row.get("sit_no_work_window_active")),
            "sit_no_work_global_active": parse_float(row.get("sit_no_work_global_active")),
        }
    return out


def collect_stems(dir_path: Path, suffix: str) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for p in sorted(dir_path.glob(f"*{suffix}")):
        stem = p.name[: -len(suffix)]
        out[stem] = p
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Validate no-work SIT fallback behavior by comparing two golden-suite outputs: "
            "one run with --no-work-sit-mode window_active and one with global_active."
        )
    )
    ap.add_argument("--window-out", required=True, help="Golden output directory built with no-work mode window_active")
    ap.add_argument("--global-out", required=True, help="Golden output directory built with no-work mode global_active")
    ap.add_argument("--tol", type=float, default=1e-9, help="Numeric tolerance for comparisons")
    ap.add_argument(
        "--require-difference",
        action="store_true",
        help="Fail when no resident windows differ between window_active and global_active SIT",
    )
    ap.add_argument(
        "--report-csv",
        default=None,
        help="Optional per-file comparison report path",
    )
    args = ap.parse_args()

    window_out = Path(args.window_out).resolve()
    global_out = Path(args.global_out).resolve()
    require(window_out.exists(), f"window-out not found: {window_out}")
    require(global_out.exists(), f"global-out not found: {global_out}")

    w_windows = collect_stems(window_out, "_windows.csv")
    g_windows = collect_stems(global_out, "_windows.csv")
    require(w_windows, f"no *_windows.csv found in {window_out}")
    require(g_windows, f"no *_windows.csv found in {global_out}")
    require(set(w_windows.keys()) == set(g_windows.keys()), "window/global windows file sets differ")

    w_summaries = collect_stems(window_out, "_summary.json")
    g_summaries = collect_stems(global_out, "_summary.json")
    require(set(w_summaries.keys()) == set(g_summaries.keys()), "window/global summary file sets differ")
    require(set(w_windows.keys()) == set(w_summaries.keys()), "windows/summary stems differ in window-out")
    require(set(g_windows.keys()) == set(g_summaries.keys()), "windows/summary stems differ in global-out")

    failures: List[str] = []
    report_rows: List[Dict[str, str]] = []
    total_resident_rows = 0
    total_diff_rows = 0

    for stem in sorted(w_windows.keys()):
        w_summary = load_summary(w_summaries[stem])
        g_summary = load_summary(g_summaries[stem])
        w_windows_rows = load_windows(w_windows[stem])
        g_windows_rows = load_windows(g_windows[stem])

        if set(w_windows_rows.keys()) != set(g_windows_rows.keys()):
            failures.append(f"{stem}: row-key mismatch between window/global outputs")
            continue

        if str(w_summary.get("no_work_sit_mode", "")) != "window_active":
            failures.append(f"{stem}: window summary no_work_sit_mode != window_active")
        if str(g_summary.get("no_work_sit_mode", "")) != "global_active":
            failures.append(f"{stem}: global summary no_work_sit_mode != global_active")

        if "work_done_present" in w_summary and bool(w_summary["work_done_present"]):
            failures.append(f"{stem}: window summary expected work_done_present=false")
        if "work_done_present" in g_summary and bool(g_summary["work_done_present"]):
            failures.append(f"{stem}: global summary expected work_done_present=false")

        g_global_sit = parse_float(str(g_summary.get("no_work_global_active_sit", "nan")))
        resident_rows = 0
        diff_rows = 0

        for key in sorted(w_windows_rows.keys()):
            wr = w_windows_rows[key]
            gr = g_windows_rows[key]

            w_res = int(wr["is_resident_window"])
            g_res = int(gr["is_resident_window"])
            if w_res != g_res:
                failures.append(f"{stem} {key}: is_resident_window mismatch {w_res} != {g_res}")
                continue
            if w_res != 1:
                continue

            resident_rows += 1
            w_sit = float(wr["sit"])
            g_sit = float(gr["sit"])
            w_sit_window = float(wr["sit_no_work_window_active"])
            w_sit_global = float(wr["sit_no_work_global_active"])
            g_sit_window = float(gr["sit_no_work_window_active"])
            g_sit_global = float(gr["sit_no_work_global_active"])

            if not approx(w_sit, w_sit_window, args.tol):
                failures.append(f"{stem} {key}: window sit != sit_no_work_window_active")
            if not approx(g_sit, g_sit_global, args.tol):
                failures.append(f"{stem} {key}: global sit != sit_no_work_global_active")
            if not approx(w_sit_window, g_sit_window, args.tol):
                failures.append(f"{stem} {key}: sit_no_work_window_active differs between runs")
            if not approx(w_sit_global, g_sit_global, args.tol):
                failures.append(f"{stem} {key}: sit_no_work_global_active differs between runs")

            if math.isfinite(g_global_sit) and not approx(g_sit, g_global_sit, args.tol):
                failures.append(f"{stem} {key}: global sit != summary no_work_global_active_sit")

            if math.isfinite(w_sit) and math.isfinite(g_sit) and abs(w_sit - g_sit) > args.tol:
                diff_rows += 1

        total_resident_rows += resident_rows
        total_diff_rows += diff_rows
        report_rows.append(
            {
                "stem": stem,
                "resident_rows": str(resident_rows),
                "diff_rows_window_vs_global": str(diff_rows),
                "window_mode": str(w_summary.get("no_work_sit_mode", "")),
                "global_mode": str(g_summary.get("no_work_sit_mode", "")),
                "global_summary_sit": "" if math.isnan(g_global_sit) else f"{g_global_sit:.12f}",
            }
        )

    if args.report_csv:
        report_path = Path(args.report_csv).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        fields = sorted({k for r in report_rows for k in r.keys()})
        with report_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(report_rows)
        print(f"Wrote: {report_path}")

    if args.require_difference and total_diff_rows == 0:
        failures.append("No resident rows differed between window_active and global_active outputs")

    if failures:
        print("FAIL no-work SIT mode checks:")
        for msg in failures:
            print(" -", msg)
        return 2

    print(
        "PASS no-work SIT mode checks "
        f"(files={len(report_rows)}, resident_rows={total_resident_rows}, diff_rows={total_diff_rows})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(2)
