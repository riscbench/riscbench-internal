from __future__ import annotations

from typing import Optional
import pandas as pd

from sit_classifier.ingest_api import TraceAdapter, validate_resid_df, validate_state_df


class NewPlatformAdapter(TraceAdapter):
    """
    Template for adding a new Phase-2 platform adapter.

    Contract:
      state_df columns: start_us,end_us,core,state[,work_done]
      resid_df columns: start_us,end_us,core[,resident]
    """

    def __init__(self, trace_path: str, residency_path: Optional[str] = None):
        self.trace_path = trace_path
        self.residency_path = residency_path

    def load_state_intervals(self) -> pd.DataFrame:
        # TODO: parse your platform trace format and emit normalized state intervals.
        # Example placeholder reads already-normalized CSV.
        df = pd.read_csv(self.trace_path)
        return validate_state_df(df)

    def load_residency_intervals(self) -> Optional[pd.DataFrame]:
        if self.residency_path is None:
            return None
        rdf = pd.read_csv(self.residency_path)
        return validate_resid_df(rdf)
