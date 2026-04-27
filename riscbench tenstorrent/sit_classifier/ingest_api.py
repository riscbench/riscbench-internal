from __future__ import annotations

from typing import Optional, Protocol
import pandas as pd

VALID_STATES = {"active", "stall", "idle"}

STATE_REQ = ["start_us", "end_us", "core", "state"]
RESID_REQ = ["start_us", "end_us", "core"]  # "resident" optional


def parse_truthy(x) -> bool:
    s = str(x).strip().lower()
    return s in ("1", "true", "t", "yes", "y")


def validate_state_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize + validate state intervals for the engine contract."""
    for c in STATE_REQ:
        if c not in df.columns:
            raise ValueError(f"Missing state column: {c}")

    df = df.copy()
    df["start_us"] = df["start_us"].astype(float)
    df["end_us"] = df["end_us"].astype(float)
    df["core"] = df["core"].astype(int)
    df["state"] = df["state"].astype(str)

    bad = df[~df["state"].isin(list(VALID_STATES))]
    if len(bad) > 0:
        raise ValueError(f"Invalid states: {sorted(bad['state'].unique().tolist())}")

    bad_iv = df[df["end_us"] <= df["start_us"]]
    if len(bad_iv) > 0:
        sample = bad_iv.head(5)[["start_us", "end_us", "core", "state"]].to_dict(orient="records")
        raise ValueError(f"Found intervals with end_us <= start_us. Sample: {sample}")

    if "duration_us" in df.columns:
        df["duration_us"] = df["duration_us"].astype(float)

    return df


def validate_resid_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize + validate residency intervals; filter resident==truthy if present."""
    for c in RESID_REQ:
        if c not in df.columns:
            raise ValueError(f"Missing residency column: {c}")

    df = df.copy()
    df["start_us"] = df["start_us"].astype(float)
    df["end_us"] = df["end_us"].astype(float)
    df["core"] = df["core"].astype(int)

    if "resident" in df.columns:
        resident_mask = df["resident"].map(parse_truthy).astype(bool)
        df = df.loc[resident_mask].copy()

    bad_iv = df[df["end_us"] <= df["start_us"]]
    if len(bad_iv) > 0:
        sample = bad_iv.head(5)[["start_us", "end_us", "core"]].to_dict(orient="records")
        raise ValueError(f"Found residency intervals with end_us <= start_us. Sample: {sample}")

    return df


class TraceAdapter(Protocol):
    """Platform parsing layer must implement this; engine must only call this interface."""
    def load_state_intervals(self) -> pd.DataFrame: ...
    def load_residency_intervals(self) -> Optional[pd.DataFrame]: ...
