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

# Marker IDs can be encoded in two forms:
#   1) legacy trap markers: addi a0, x0, MARKER_ID ; ebreak
#   2) non-trapping markers: addi x0, x0, MARKER_ID
#
# The non-trapping form is preferred for pk+spike workloads because `ebreak`
# can terminate execution before the workload body runs.
RES_ON_MARKER = 101
RES_OFF_MARKER = 102

# Match immediate payload for marker forms.
ADDI_A0_IMM_RE = re.compile(
    r"\baddi\s+a0\s*,\s*(?:x0|zero)\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)
ADDI_ZERO_IMM_RE = re.compile(
    r"\baddi\s+(?:x0|zero)\s*,\s*(?:x0|zero)\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)
LI_ZERO_IMM_RE = re.compile(
    r"\bli\s+(?:x0|zero)\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)

ADDI_ZERO_IMM_RE = re.compile(
    r"\baddi\s+(?:x0|zero)\s*,\s*(?:x0|zero)\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)


@dataclass
class SpikeParseConfig:
    inst_us: float = 1.0
    resident_pc_ge: int = 0x80000000


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

    def _iter_events(self) -> Iterable[Tuple[int, str, int, str, Optional[int]]]:
        """
        Yield per-instruction events as:
          (core, normalized_mnemonic, inst_count, raw_mnemonic, pc)

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
                pc: Optional[int] = None

                m = SPIKE_LINE_RE.search(line)
                if m:
                    core = int(m.group("core"))
                    try:
                        pc = int(m.group("pc"), 16)
                    except Exception:
                        pc = None
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

                    # Require at least one PC-like token on fallback paths to avoid
                    # counting non-commit-log chatter.
                    if core is None or not hex_token_re.findall(line):
                        continue

                    pc_m = PC_AFTER_CORE_RE.search(line)
                    if pc_m:
                        try:
                            pc = int(pc_m.group("pc"), 16)
                        except Exception:
                            pc = None

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
                yield core, norm_mnemonic, inst_count, raw_mnemonic, pc

    @staticmethod
    def _extract_marker_id(raw_mnemonic: str, marker_re: re.Pattern) -> Optional[int]:
        if not raw_mnemonic:
            return None
        mm = marker_re.search(raw_mnemonic)
        if not mm:
            return None
        imm_txt = mm.group("imm")
        try:
            return int(imm_txt, 0)
        except ValueError:
            return None

    def _collect_core_timeline(self) -> Dict[int, Dict[str, List[float]]]:
        """
        Parse commit-log once and collect per-core timeline.

        Preferred residency detection is marker-driven (RES_ON/RES_OFF). If markers
        are absent for a core, fall back to PC-threshold residency using
        resident_pc_ge.
        """
        inst_us = float(self.cfg.inst_us)
        resident_pc_ge = int(self.cfg.resident_pc_ge)

        pending_marker_by_core: Dict[int, Optional[int]] = {}
        marker_on_start_by_core: Dict[int, Optional[float]] = {}

        marker_starts_by_core: Dict[int, List[float]] = {}
        marker_ends_by_core: Dict[int, List[float]] = {}

        fallback_on_start_by_core: Dict[int, Optional[float]] = {}
        fallback_starts_by_core: Dict[int, List[float]] = {}
        fallback_ends_by_core: Dict[int, List[float]] = {}

        max_t_by_core: Dict[int, float] = {}

        for core, mnemonic, inst_count, raw_mnemonic, pc in self._iter_events():
            t1 = float(inst_count) * inst_us
            max_t_by_core[core] = max(max_t_by_core.get(core, 0.0), t1)

            if mnemonic.startswith("addi"):
                # Preferred marker path: non-trapping `addi x0, x0, IMM`.
                marker_id_direct = self._extract_marker_id(raw_mnemonic, ADDI_ZERO_IMM_RE)
                if marker_id_direct == RES_ON_MARKER:
                    on_start_by_core[core] = t1
                    continue
                if marker_id_direct == RES_OFF_MARKER:
                    rs = on_start_by_core.get(core)
                    if rs is not None and t1 > rs:
                        starts_by_core.setdefault(core, []).append(float(rs))
                        ends_by_core.setdefault(core, []).append(float(t1))
                    on_start_by_core[core] = None
                    continue

                # Backward-compatible path: `addi a0, x0, IMM` consumed by `ebreak`.
                marker_id_legacy = self._extract_marker_id(raw_mnemonic, ADDI_A0_IMM_RE)
                if marker_id_legacy is not None:
                    pending_marker_by_core[core] = marker_id_legacy
                continue

            if mnemonic == "ebreak":
                marker_id = pending_marker_by_core.get(core)
                pending_marker_by_core[core] = None

                if marker_id == RES_ON_MARKER:
                    marker_on_start_by_core[core] = t1
                elif marker_id == RES_OFF_MARKER:
                    rs = marker_on_start_by_core.get(core)
                    if rs is not None and t1 > rs:
                        marker_starts_by_core.setdefault(core, []).append(float(rs))
                        marker_ends_by_core.setdefault(core, []).append(float(t1))
                    marker_on_start_by_core[core] = None

        # Close dangling open intervals at trace end.
        for core, rs in marker_on_start_by_core.items():
            if rs is None:
                continue
            end_t = max_t_by_core.get(core, rs)
            if end_t > rs:
                marker_starts_by_core.setdefault(core, []).append(float(rs))
                marker_ends_by_core.setdefault(core, []).append(float(end_t))

        for core, rs in fallback_on_start_by_core.items():
            if rs is None:
                continue
            end_t = max_t_by_core.get(core, rs)
            if end_t > rs:
                fallback_starts_by_core.setdefault(core, []).append(float(rs))
                fallback_ends_by_core.setdefault(core, []).append(float(end_t))

        out: Dict[int, Dict[str, List[float]]] = {}
        for core in sorted(max_t_by_core.keys()):
            marker_spans = list(zip(marker_starts_by_core.get(core, []), marker_ends_by_core.get(core, [])))
            if marker_spans:
                starts = [s for s, _ in marker_spans]
                ends = [e for _, e in marker_spans]
            else:
                starts = fallback_starts_by_core.get(core, [])
                ends = fallback_ends_by_core.get(core, [])

            out[core] = {
                "starts": starts,
                "ends": ends,
                "max_t": [max_t_by_core.get(core, 0.0)],
            }
        return out

    def build_residency_intervals(self) -> pd.DataFrame:
        """
        Build residency intervals from marker spans (preferred) or PC-threshold fallback.
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
        Build state intervals:
          - active on resident spans
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
    ap.add_argument("--resident-pc-ge", type=lambda x: int(x, 0), default=0x80000000, help="Fallback residency PC threshold")
    args = ap.parse_args()

    cfg = SpikeParseConfig(inst_us=args.inst_us, resident_pc_ge=args.resident_pc_ge)
    ad = SpikePlatformAdapter(args.spike_trace, cfg=cfg)
    s_path, r_path = ad.export_baseline_csvs(args.out_dir)

    print("✓ wrote:", s_path)
    print("✓ wrote:", r_path)


if __name__ == "__main__":
    main()
