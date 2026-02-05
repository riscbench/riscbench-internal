# adapters/cpu_adapter.py
"""
CPU adapter: platform-specific trace parsing.
Derives state intervals AND residency intervals from workload events.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd


class CPUAdapter:
    """
    Parse raw CPU trace formats (e.g., matmul key=value events).
    
    Derives:
      - State intervals: active/stall/idle periods
      - Residency intervals: when core was executing useful work (not stalled)
    
    Input: Raw trace file with events like:
        ts_us=X thread=Y event=Z key=val ...
    
    Output: 
      - state_df: Normalized DataFrame with columns [start_us, end_us, core, state]
      - resid_df: Residency DataFrame with columns [start_us, end_us, core, resident]
    """
    
    def __init__(self, trace_path: str, max_events: Optional[int] = None):
        self.trace_path = Path(trace_path)
        self.max_events = max_events if max_events and max_events > 0 else None
        self._events = self._parse_raw_events()
        self._idle_gap_us = 5.0
    
    def _parse_raw_events(self) -> List[Dict[str, Any]]:
        """Parse raw trace format: ts_us=X thread=Y event=Z key=val ..."""
        events = []
        
        with open(self.trace_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Parse key=value pairs
                row = {}
                for part in line.split():
                    if '=' in part:
                        k, v = part.split('=', 1)
                        row[k] = v
                
                if 'ts_us' in row and 'thread' in row and 'event' in row:
                    events.append(row)
                    if self.max_events is not None and len(events) >= self.max_events:
                        break
        
        return events
    
    def _event_flag(self, ev: Dict[str, Any], key: str) -> int:
        raw = ev.get(key, 0)
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return 0

    def to_state_dataframe(self) -> pd.DataFrame:
        """Convert events to state interval DataFrame (start_us, end_us, core, state)."""
        if not self._events:
            return pd.DataFrame(columns=['start_us', 'end_us', 'core', 'state', 'work_done', 'pressure_flag'])
        
        # Group events by thread
        threads = {}
        for ev in self._events:
            thread_id = int(ev['thread'])
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(ev)
        
        # Convert to intervals
        intervals = []
        for thread_id in sorted(threads.keys()):
            events = sorted(threads[thread_id], key=lambda e: float(e['ts_us']))
            
            for i, ev in enumerate(events):
                ts = float(ev['ts_us'])
                next_ts = float(events[i + 1]['ts_us']) if i + 1 < len(events) else ts + 1000
                gap_us = max(0.0, next_ts - ts)
                tiles_done = float(
                    ev.get("tiles_done", ev.get("tiles", ev.get("tile", 0.0))) or 0.0
                )
                next_tiles_done = tiles_done
                if i + 1 < len(events):
                    nxt = events[i + 1]
                    next_tiles_done = float(
                        nxt.get("tiles_done", nxt.get("tiles", nxt.get("tile", tiles_done))) or tiles_done
                    )
                work_done = max(0.0, next_tiles_done - tiles_done)

                event_type = ev.get('event', '')
                uf_flag = self._event_flag(ev, 'uf')
                of_flag = self._event_flag(ev, 'of')
                if work_done == 0.0 and event_type == 'COMPUTE_WORK':
                    # Fallback: many traces emit `tile=<idx>` or only COMPUTE_WORK events.
                    # Treat each compute step as one unit of work to preserve SIT sensitivity.
                    work_done = 1.0
                
                
                # Map event types to CPU states.
                # For COMPUTE_WORK rows carrying uf/of flags, keep residency state as active
                # (so uf/of does not implicitly rewrite residency_stall), but scale useful
                # work down so SIT drops under pressure even when residency mix is stable.
                pressure_flag = 1 if (event_type == 'COMPUTE_WORK' and (uf_flag > 0 or of_flag > 0)) else 0
                if event_type == 'COMPUTE_WORK':
                    state = 'active'
                    if uf_flag > 0:
                        work_done *= 0.60
                    if of_flag > 0:
                        work_done *= 0.40
                elif 'UNDERFLOW' in event_type or 'OVERFLOW' in event_type:
                    state = 'stall'
                elif event_type in ('THREAD_START', 'THREAD_END'):
                    state = 'idle'
                else:
                    state = 'idle'

                interval_end = next_ts
                interval_start = ts
                idle_start = None
                # Only split long ACTIVE gaps into active+idle.
                # For pressure events (stall), keep the full interval as stall so
                # underflow/overflow contributes to residency_stall instead of idle.
                if (
                    gap_us > self._idle_gap_us
                    and event_type not in ('THREAD_START', 'THREAD_END')
                    and state == 'active'
                ):
                    interval_end = ts + self._idle_gap_us
                    idle_start = interval_end

                if interval_end > interval_start:
                    intervals.append({
                        'start_us': interval_start,
                        'end_us': interval_end,
                        'core': thread_id - 1,  # thread 1 -> core 0
                        'state': state,
                        'work_done': work_done if state == 'active' else 0.0,
                        'pressure_flag': pressure_flag,
                    })

                if idle_start is not None and next_ts > idle_start:
                    intervals.append({
                        'start_us': idle_start,
                        'end_us': next_ts,
                        'core': thread_id - 1,
                        'state': 'idle',  # overhead/spin wait
                        'work_done': 0.0,
                        'pressure_flag': 0,
                    })
        
        df = pd.DataFrame(intervals)
        if len(df) == 0:
            return pd.DataFrame(columns=['start_us', 'end_us', 'core', 'state', 'work_done', 'pressure_flag'])
        
        return df.sort_values('start_us').reset_index(drop=True)
    
    def to_residency_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Derive residency intervals from trace.
        Mark execution span as resident=1 so SIT can measure active/stall breakdown.
        """
        if not self._events:
            return None
        
        # Group events by thread
        threads = {}
        for ev in self._events:
            thread_id = int(ev['thread'])
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(ev)
        
        residency_intervals = []
        
        for thread_id in sorted(threads.keys()):
            events = sorted(threads[thread_id], key=lambda e: float(e['ts_us']))
            if not events:
                continue
            
            # Cover from first to last event in the trace (no padding)
            first_ts = float(events[0]['ts_us'])
            last_ts = float(events[-1]['ts_us'])
            
            residency_intervals.append({
                'start_us': first_ts,
                'end_us': last_ts,
                'core': thread_id - 1,
                'resident': 1,  # entire span is part of measurement region
            })
        
        df = pd.DataFrame(residency_intervals)
        if len(df) == 0:
            return None
        
        return df.sort_values('start_us').reset_index(drop=True)
