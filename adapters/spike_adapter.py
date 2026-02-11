# adapters/spike_platform_adapter.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import os
import re
import sys
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingest.ingest_api import validate_state_df, validate_resid_df

# Example spike -l line:
# core   0: 0x0000000080000214 (0x00000413) li      s0, 0
SPIKE_LINE_RE = re.compile(
    r"^\s*core\s+(?P<core>\d+):\s+(?:\d+\s+)?0x(?P<pc>[0-9a-fA-F]+)\s+\(0x(?P<insn>[0-9a-fA-F]+)\)(?:\s+(?P<mnemonic>\S+))?"
)

CORE_FALLBACK_RE = re.compile(r"core\s+(?P<core>\d+):")
PC_AFTER_CORE_RE = re.compile(r"0x(?P<pc>[0-9a-fA-F]{8,16})")
GENERIC_CORE_RE = re.compile(r"(?:core|hart)\D*(?P<core>\d+)", re.IGNORECASE)
HEX_TOKEN_RE = re.compile(r"0x(?P<hex>[0-9a-fA-F]{8,16})")

# Marker IDs encoded via: addi a0, x0, MARKER_ID ; ebreak
RES_ON_MARKER = 101
RES_OFF_MARKER = 102

# Match immediate payload for `addi a0, x0, imm` variants.
ADDI_A0_IMM_RE = re.compile(
    r"\baddi\s+a0\s*,\s*(?:x0|zero)\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)
LI_A0_IMM_RE = re.compile(
    r"\bli\s+a0\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)


@dataclass
class SpikeParseConfig:
    inst_us: float = 1.0


class SpikePlatformAdapter:
    """
    Platform adapter (Spike) -> emits baseline CSVs that BaselineAdapter can read.

    Output CSV schemas are exactly what ingest_api.validate_* expects:
      state: start_us,end_us,core,state
      resid: start_us,end_us,core[,resident]
    """

    def __init__(self, spike_trace_path: str, cfg: Optional[SpikeParseConfig] = None):
        self.spike_trace_path = spike_trace_path
        self.cfg = cfg or SpikeParseConfig()

    def _iter_events(self) -> Iterable[Tuple[int, str, int, str]]:
        """
        Yield per-instruction events as:
          (core, normalized_mnemonic, inst_count, raw_mnemonic)

        `inst_count` is per-core instruction index (1-based) and defines timeline:
          time_us = inst_count * inst_us
        """
        generic_core_re = globals().get("GENERIC_CORE_RE") or GENERIC_CORE_RE
        hex_token_re = globals().get("HEX_TOKEN_RE") or HEX_TOKEN_RE

        inst_count_by_core: Dict[int, int] = {}

        with open(self.spike_trace_path, "r", errors="ignore") as f:
            for line in f:
                core: Optional[int] = None
                mnemonic = ""

                m = SPIKE_LINE_RE.search(line)
                if m:
                    core = int(m.group("core"))
                    tail = line.split(")", 1)
                    mnemonic = tail[1].strip() if len(tail) == 2 else (m.group("mnemonic") or "")
                else:
                    core_m = CORE_FALLBACK_RE.search(line)
                    if core_m:
                        core = int(core_m.group("core"))
                    else:
                        generic_core_m = generic_core_re.search(line)
                        if generic_core_m:
                            try:
                                core = int(generic_core_m.group("core"))
                            except ValueError:
                                core = None

                    if core is not None and not line.strip().startswith("core"):
                        # leave as-is; this path still counts instruction-ish lines once a core is identified
                        pass

                    # Require at least one PC-like token on fallback paths to avoid
                    # counting non-commit-log chatter.
                    if core is None or not hex_token_re.findall(line):
                        continue

                    # Heuristic mnemonic extraction from fallback text.
                    # Usually after ')' token in commit log lines.
                    tail = line.split(")", 1)
                    if len(tail) == 2:
                        tok = tail[1].strip().split()
                        mnemonic = tok[0] if tok else ""

                if core is None:
                    continue

                inst_count_by_core[core] = inst_count_by_core.get(core, 0) + 1
                inst_count = inst_count_by_core[core]
                raw_mnemonic = (mnemonic or "").strip()
                norm_mnemonic = raw_mnemonic.split()[0].lower() if raw_mnemonic else ""
                yield core, norm_mnemonic, inst_count, raw_mnemonic

    @staticmethod
    def _extract_marker_id(raw_mnemonic: str) -> Optional[int]:
        if not raw_mnemonic:
            return None

        mm = ADDI_A0_IMM_RE.search(raw_mnemonic)
        if mm is None:
            mm = LI_A0_IMM_RE.search(raw_mnemonic)
        if mm is None:
            return None

        imm_txt = mm.group("imm")
        try:
            marker_id = int(imm_txt, 0)
        except ValueError:
            return None

        if marker_id in (RES_ON_MARKER, RES_OFF_MARKER):
            return marker_id
        return None

    def _collect_core_timeline(self) -> Dict[int, Dict[str, List[float]]]:
        """
        Parse commit-log once and collect per-core:
          - candidate residency boundaries from marker pairs
          - timeline min/max for optional idle gap emission

        Residency detection rule:
          ebreak consumes marker_id from preceding `addi a0,x0,<id>` on same core.
        """
        inst_us = float(self.cfg.inst_us)

        pending_marker_by_core: Dict[int, Optional[int]] = {}
        on_start_by_core: Dict[int, Optional[float]] = {}

        starts_by_core: Dict[int, List[float]] = {}
        ends_by_core: Dict[int, List[float]] = {}
        max_t_by_core: Dict[int, float] = {}

        for core, mnemonic, inst_count, raw_mnemonic in self._iter_events():
            t1 = float(inst_count) * inst_us
            max_t_by_core[core] = max(max_t_by_core.get(core, 0.0), t1)

            marker_id = self._extract_marker_id(raw_mnemonic)
            if marker_id is not None:
                pending_marker_by_core[core] = marker_id
                continue

            if mnemonic == "ebreak":
                marker_id = pending_marker_by_core.get(core)
                pending_marker_by_core[core] = None

                if marker_id == RES_ON_MARKER:
                    on_start_by_core[core] = t1
                elif marker_id == RES_OFF_MARKER:
                    rs = on_start_by_core.get(core)
                    if rs is not None and t1 > rs:
                        starts_by_core.setdefault(core, []).append(float(rs))
                        ends_by_core.setdefault(core, []).append(float(t1))
                    on_start_by_core[core] = None

        # Close dangling RES_ON markers at end-of-trace for that core.
        for core, rs in on_start_by_core.items():
            if rs is None:
                continue
            end_t = max_t_by_core.get(core, rs)
            if end_t > rs:
                starts_by_core.setdefault(core, []).append(float(rs))
                ends_by_core.setdefault(core, []).append(float(end_t))

        out: Dict[int, Dict[str, List[float]]] = {}
        for core in sorted(max_t_by_core.keys()):
            out[core] = {
                "starts": starts_by_core.get(core, []),
                "ends": ends_by_core.get(core, []),
                "max_t": [max_t_by_core.get(core, 0.0)],
            }
        return out

    def build_residency_intervals(self) -> pd.DataFrame:
        """
        Build residency intervals strictly from explicit RES_ON/RES_OFF markers.
        """
        timeline = self._collect_core_timeline()

        rows: List[Dict] = []
        for core, meta in timeline.items():
            starts = meta["starts"]
            ends = meta["ends"]
            for s, e in zip(starts, ends):
                if e > s:
                    rows.append({"start_us": s, "end_us": e, "core": core, "resident": 1})

        rdf = pd.DataFrame(rows)
        rdf = rdf.reindex(columns=["start_us", "end_us", "core", "resident"])
        return validate_resid_df(rdf)

    def build_state_intervals(self) -> pd.DataFrame:
        """
        Build marker-driven state intervals:
          - active on resident [RES_ON, RES_OFF) spans
          - idle in gaps between resident spans on each core timeline
        """
        timeline = self._collect_core_timeline()

        rows: List[Dict] = []
        for core, meta in timeline.items():
            starts = [float(x) for x in meta["starts"]]
            ends = [float(x) for x in meta["ends"]]
            max_t = float(meta["max_t"][0]) if meta["max_t"] else 0.0
            if max_t <= 0.0:
                continue

            # Ensure intervals are ordered and valid.
            spans = sorted([(s, e) for s, e in zip(starts, ends) if e > s], key=lambda x: x[0])
            t = 0.0
            for s, e in spans:
                if s > t:
                    rows.append({"start_us": t, "end_us": s, "core": core, "state": "idle"})
                rows.append({"start_us": s, "end_us": e, "core": core, "state": "active"})
                t = max(t, e)
            if t < max_t:
                rows.append({"start_us": t, "end_us": max_t, "core": core, "state": "idle"})

        df = pd.DataFrame(rows)
        if len(df) == 0:
            df = pd.DataFrame(columns=["start_us", "end_us", "core", "state"])
        else:
            df = df.sort_values(["core", "start_us"]).reset_index(drop=True)

        return validate_state_df(df)

    def export_baseline_csvs(self, out_dir: str) -> Tuple[str, str]:
        """
        Writes:
          out_dir/state_intervals.csv
          out_dir/residency_intervals.csv
        Returns (state_path, resid_path)
        """
        os.makedirs(out_dir, exist_ok=True)

        state_df = self.build_state_intervals()
        resid_df = self.build_residency_intervals()

        state_path = os.path.join(out_dir, "state_intervals.csv")
        resid_path = os.path.join(out_dir, "residency_intervals.csv")

        state_df.to_csv(state_path, index=False)
        resid_df.to_csv(resid_path, index=False)

        return state_path, resid_path


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--spike-trace", required=True, help="Spike -l log file (text)")
    ap.add_argument("--out-dir", required=True, help="Directory to write baseline CSVs")
    ap.add_argument("--inst-us", type=float, default=1.0, help="Time per instruction (us) for commit-log timeline")
    # kept for backward CLI compatibility; marker-driven residency ignores this threshold.
    ap.add_argument("--resident-pc-ge", type=lambda x: int(x, 0), default=0x80000000, help="(unused) legacy residency PC threshold")
    args = ap.parse_args()

    cfg = SpikeParseConfig(inst_us=args.inst_us)
    ad = SpikePlatformAdapter(args.spike_trace, cfg=cfg)
    s_path, r_path = ad.export_baseline_csvs(args.out_dir)

    print("✓ wrote:", s_path)
    print("✓ wrote:", r_path)


if __name__ == "__main__":
    main()
