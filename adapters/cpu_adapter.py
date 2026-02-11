# adapters/cpu_adapter.py
"""
CPU adapter: platform-specific trace parsing.
Derives state intervals AND residency intervals directly from workload events.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd


class CPUAdapter:
    """
    Parse raw CPU trace formats (e.g., matmul key=value events).

    Input: Raw trace file with events like:
        ts_us=X thread=Y event=Z key=val ...

    Output:
      - state_df: [start_us, end_us, core, state, work_done, pressure_flag]
      - resid_df: [start_us, end_us, core, resident]

    Notes:
      - Intervals are derived directly from consecutive trace timestamps.
      - No synthetic idle/stall injection, timeline splitting, or work scaling is applied.
    """

    def __init__(self, trace_path: str, max_events: Optional[int] = None):
        self.trace_path = Path(trace_path)
        self.max_events = max_events if max_events and max_events > 0 else None
        self._events = self._parse_raw_events()

    def _parse_raw_events(self) -> List[Dict[str, Any]]:
        """Parse raw trace format: ts_us=X thread=Y event=Z key=val ..."""
        events: List[Dict[str, Any]] = []

        with open(self.trace_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                row: Dict[str, Any] = {}
                for part in line.split():
                    if '=' in part:
                        k, v = part.split('=', 1)
                        row[k] = v

                if 'ts_us' in row and 'thread' in row and 'event' in row:
                    events.append(row)
                    if self.max_events is not None and len(events) >= self.max_events:
                        break

        return events

    @staticmethod
    def _state_from_event(event_type: str) -> str:
        if event_type == 'COMPUTE_WORK':
            return 'active'
        if 'UNDERFLOW' in event_type or 'OVERFLOW' in event_type:
            return 'stall'
        if event_type in ('THREAD_START', 'THREAD_END'):
            return 'idle'
        return 'idle'

    @staticmethod
    def _tiles_done(ev: Dict[str, Any]) -> float:
        raw = ev.get("tiles_done", ev.get("tiles", ev.get("tile", 0.0)))
        try:
            return float(raw or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def to_state_dataframe(self) -> pd.DataFrame:
        """Convert events to interval DataFrame (start_us, end_us, core, state)."""
        cols = ['start_us', 'end_us', 'core', 'state', 'work_done', 'pressure_flag']
        if not self._events:
            return pd.DataFrame(columns=cols)

        threads: Dict[int, List[Dict[str, Any]]] = {}
        for ev in self._events:
            thread_id = int(ev['thread'])
            threads.setdefault(thread_id, []).append(ev)

        intervals: List[Dict[str, Any]] = []
        for thread_id in sorted(threads.keys()):
            events = sorted(threads[thread_id], key=lambda e: float(e['ts_us']))

            for i, ev in enumerate(events):
                ts = float(ev['ts_us'])
                if i + 1 < len(events):
                    next_ts = float(events[i + 1]['ts_us'])
                else:
                    # No synthetic tail for the final event.
                    next_ts = ts

                if next_ts <= ts:
                    continue

                event_type = ev.get('event', '')
                state = self._state_from_event(event_type)

                work_done = 0.0
                if state == 'active' and i + 1 < len(events):
                    work_done = max(0.0, self._tiles_done(events[i + 1]) - self._tiles_done(ev))

                intervals.append({
                    'start_us': ts,
                    'end_us': next_ts,
                    'core': thread_id - 1,  # thread 1 -> core 0
                    'state': state,
                    'work_done': work_done,
                    'pressure_flag': 0,
                })

        df = pd.DataFrame(intervals)
        if len(df) == 0:
            return pd.DataFrame(columns=cols)

        return df.sort_values(['core', 'start_us']).reset_index(drop=True)

    def to_residency_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Derive residency directly from parsed events.

        Residency is asserted only on intervals mapped to active/stall states,
        then merged when contiguous per core.
        """
        state_df = self.to_state_dataframe()
        if state_df.empty:
            return None

        resident_df = state_df[state_df['state'].isin(['active', 'stall'])][['start_us', 'end_us', 'core']].copy()
        if resident_df.empty:
            return pd.DataFrame(columns=['start_us', 'end_us', 'core', 'resident'])

        resident_df = resident_df.sort_values(['core', 'start_us']).reset_index(drop=True)

        merged: List[Dict[str, Any]] = []
        cur = resident_df.iloc[0].to_dict()
        for i in range(1, len(resident_df)):
            r = resident_df.iloc[i].to_dict()
            if r['core'] == cur['core'] and abs(float(r['start_us']) - float(cur['end_us'])) < 1e-9:
                cur['end_us'] = r['end_us']
            else:
                cur['resident'] = 1
                merged.append(cur)
                cur = r
        cur['resident'] = 1
        merged.append(cur)

        return pd.DataFrame(merged, columns=['start_us', 'end_us', 'core', 'resident'])
