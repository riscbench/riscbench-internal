# schemas/v1.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List
import pandas as pd

SCHEMA_VERSION = 1

# Windows table (per core, per window) schema v1
WINDOWS_COLUMNS: List[str] = [
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
]

# Summary schema v1 (keys)
SUMMARY_KEYS: List[str] = [
    "schema_version",
    "window_us",
    "windows_total",
    "resident_windows_total",
    "cores",
    "sit_median",
    "sit_p95",
    "residency_idle_avg",
    "residency_stall_avg",
    "residency_active_avg",
    "used_residency_file",
]

def validate_windows_v1(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the per-window output matches schema v1 (columns present & ordered)."""
    missing = [c for c in WINDOWS_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"windows v1 missing columns: {missing}")

    # Reorder + drop extras (extras allowed internally, not in exported v1)
    out = df[WINDOWS_COLUMNS].copy()

    # Light type normalization (keeps pandas flexibility)
    out["core"] = out["core"].astype(int)
    out["window_id"] = out["window_id"].astype(int)
    out["is_resident_window"] = out["is_resident_window"].astype(int)

    # numeric columns to float
    for c in [
        "window_start_us","window_end_us","resident_us","resident_frac_of_window",
        "active_frac","stall_frac","idle_frac","sit"
    ]:
        out[c] = out[c].astype(float)

    return out

def validate_summary_v1(summary: Dict[str, Any]) -> Dict[str, Any]:
    missing = [k for k in SUMMARY_KEYS if k not in summary]
    if missing:
        raise ValueError(f"summary v1 missing keys: {missing}")

    if int(summary["schema_version"]) != SCHEMA_VERSION:
        raise ValueError(f"summary schema_version != {SCHEMA_VERSION}")

    # minimal type sanity
    summary["schema_version"] = int(summary["schema_version"])
    summary["window_us"] = float(summary["window_us"])
    summary["windows_total"] = int(summary["windows_total"])
    summary["resident_windows_total"] = int(summary["resident_windows_total"])
    summary["used_residency_file"] = bool(summary["used_residency_file"])

    # cores list of ints
    summary["cores"] = [int(x) for x in summary["cores"]]

    # floats (may be nan)
    for k in ["sit_median","sit_p95","residency_idle_avg","residency_stall_avg","residency_active_avg"]:
        summary[k] = float(summary[k])

    return summary
