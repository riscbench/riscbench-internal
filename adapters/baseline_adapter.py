# adapters/baseline_adapter.py
from __future__ import annotations

from typing import Optional
import pandas as pd

from ingest.ingest_api import TraceAdapter, validate_state_df, validate_resid_df


class BaselineAdapter(TraceAdapter):
    """
    Phase-1 baseline adapter.

    Purpose:
      - Provide a deterministic, simple reference ingestion path
      - Read inputs (here: CSV) and emit normalized DataFrames
      - Enforce schema/semantic validation via ingest_api.py

    Note:
      - CSV is an implementation choice for the baseline adapter only.
      - The SIT engine must depend only on the adapter interface.
    """

    def __init__(self, trace_path: str, residency_path: Optional[str] = None):
        self.trace_path = trace_path
        self.residency_path = residency_path

    def load_state_intervals(self) -> pd.DataFrame:
        df = pd.read_csv(self.trace_path)
        return validate_state_df(df)

    def load_residency_intervals(self) -> Optional[pd.DataFrame]:
        if self.residency_path is None:
            return None
        rdf = pd.read_csv(self.residency_path)
        return validate_resid_df(rdf)
