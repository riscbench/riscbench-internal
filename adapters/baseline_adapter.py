# adapters/baseline_adapter.py
from __future__ import annotations

from typing import Optional
import pandas as pd

from ingest.ingest_api import TraceAdapter, validate_state_df, validate_resid_df
from adapters.cpu_adapter import CPUAdapter


class BaselineAdapter(TraceAdapter):
    """
    Phase-1 baseline adapter: CPU adapter -> validation pipeline.

    Architecture:
      1. CPU adapter parses platform-specific trace format
      2. Baseline adapter validates against ingest_api schema
      3. Engine consumes normalized intervals

    Supported formats:
      - CSV (raw): Expects [ts_us, thread, event, core, ...] columns
      - Raw events (CPU): Delegates to CPUAdapter for parsing
    """

    def __init__(self, trace_path: str, residency_path: Optional[str] = None, trace_format: str = "csv"):
        self.trace_path = trace_path
        self.residency_path = residency_path
        self.trace_format = trace_format

    def load_state_intervals(self) -> pd.DataFrame:
        """Load and validate state intervals."""
        # Parse using appropriate adapter
        if self.trace_format == "raw":
            cpu_adapter = CPUAdapter(self.trace_path)
            df = cpu_adapter.to_state_dataframe()
        else:
            # Otherwise try CSV
            df = pd.read_csv(self.trace_path)
        
        return validate_state_df(df)

    def load_residency_intervals(self) -> Optional[pd.DataFrame]:
        if self.residency_path is None:
            # Derive residency from CPU adapter if available
            if self.trace_format == "raw":
                cpu_adapter = CPUAdapter(self.trace_path)
                df = cpu_adapter.to_residency_dataframe()
                if df is not None:
                    return validate_resid_df(df)
            return None
        rdf = pd.read_csv(self.residency_path)
        return validate_resid_df(rdf)
