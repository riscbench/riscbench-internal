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
    
    def __init__(self, trace_path: str):
        self.trace_path = Path(trace_path)
        self._events = self._parse_raw_events()
    
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
        
        return events
    
    def to_state_dataframe(self) -> pd.DataFrame:
        """Convert events to state interval DataFrame (start_us, end_us, core, state)."""
        if not self._events:
            return pd.DataFrame(columns=['start_us', 'end_us', 'core', 'state'])
        
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
                
                event_type = ev.get('event', '')
                
                # Map event types to CPU states
                if event_type == 'COMPUTE_WORK':
                    state = 'active'
                elif 'UNDERFLOW' in event_type or 'OVERFLOW' in event_type:
                    state = 'stall'
                else:
                    state = 'active'
                
                intervals.append({
                    'start_us': ts,
                    'end_us': next_ts,
                    'core': thread_id - 1,  # thread 1 -> core 0
                    'state': state,
                })
                
                # If gap between this event and next > threshold, mark as idle overhead
                if i + 1 < len(events):
                    gap_us = next_ts - ts
                    # Gaps > 5µs likely indicate spin/yield periods (overhead, treat as idle)
                    if gap_us > 5.0 and event_type not in ('THREAD_START', 'THREAD_END'):
                        intervals.append({
                            'start_us': ts,
                            'end_us': next_ts,
                            'core': thread_id - 1,
                            'state': 'idle',  # overhead/spin wait
                        })
        
        df = pd.DataFrame(intervals)
        if len(df) == 0:
            return pd.DataFrame(columns=['start_us', 'end_us', 'core', 'state'])
        
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
