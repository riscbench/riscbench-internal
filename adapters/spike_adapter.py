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
    # Some Spike builds emit: "core   0: 0x... (0x...) add ..."
    # Others emit:          "core   0: 3 0x... (0x...) add ..." (privilege level token)
    r"^\s*core\s+(?P<core>\d+):\s+(?:\d+\s+)?0x(?P<pc>[0-9a-fA-F]+)\s+\(0x(?P<insn>[0-9a-fA-F]+)\)(?:\s+(?P<mnemonic>\S+))?"
)


# Fallback parser for Spike variants that do not include an (0xINSN) tuple.
CORE_FALLBACK_RE = re.compile(r"core\s+(?P<core>\d+):")
PC_AFTER_CORE_RE = re.compile(r"0x(?P<pc>[0-9a-fA-F]{8,16})")
GENERIC_CORE_RE = re.compile(r"(?:core|hart)\D*(?P<core>\d+)", re.IGNORECASE)
HEX_TOKEN_RE = re.compile(r"0x(?P<hex>[0-9a-fA-F]{8,16})")

# Very simple heuristic: treat memory ops as "stall" else "active"
MEM_MNEMONICS_PREFIX = (
    "lb", "lbu", "lh", "lhu", "lw", "lwu", "ld",
    "sb", "sh", "sw", "sd",
    "flw", "fld", "fsw", "fsd",
)

# CPU-style calibration: treat regular load/store instructions as active work
# (not pipeline stall), and reserve "stall" for explicit waiting/synchronization
# instructions that better match software-visible blocked time.
STALL_MNEMONICS = {
    "wfi", "fence", "fence.i",
}

@dataclass
class SpikeParseConfig:
    inst_us: float = 1.0
    # Residency heuristic: PCs in DRAM/PK region typically start at 0x8000_0000
    resident_pc_ge: int = 0x8000_0000


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

    def _iter_events(self) -> Iterable[Tuple[int, int, str]]:
        """
        Yield (core, pc_int, mnemonic) per instruction line.

        Primary parser handles the common `core N: ...` disassembly format.
        Fallback parser extracts core+pc from minimal commit-log lines so
        workloads still produce events even when mnemonic text is absent.
        """
        # Defensive fallback: if module-level regexes are missing/stale in an
        # older installed copy, compile local patterns so parsing still works.
        generic_core_re = globals().get("GENERIC_CORE_RE") or GENERIC_CORE_RE
        hex_token_re = globals().get("HEX_TOKEN_RE") or HEX_TOKEN_RE

        with open(self.spike_trace_path, "r", errors="ignore") as f:
            for line in f:
                m = SPIKE_LINE_RE.search(line)
                if m:
                    core = int(m.group("core"))
                    pc = int(m.group("pc"), 16)
                    mnemonic = m.group("mnemonic") or ""
                    yield core, pc, mnemonic
                    continue

                core_m = CORE_FALLBACK_RE.search(line)
                if core_m:
                    core = int(core_m.group("core"))
                    tail = line[core_m.end():]
                    pc_m = PC_AFTER_CORE_RE.search(tail)
                    if pc_m:
                        try:
                            pc = int(pc_m.group("pc"), 16)
                        except ValueError:
                            pc = None
                        if pc is not None:
                            yield core, pc, ""
                            continue

                # Ultra-relaxed fallback for Spike variants with unusual formatting:
                # - core token may appear without colon
                # - line may omit decoded instruction tuple
                # - only a PC-like 0x........ token is available
                # This is Spike-only fallback and does not affect other targets.
                core_guess = 0
                generic_core_m = generic_core_re.search(line)
                if generic_core_m:
                    try:
                        core_guess = int(generic_core_m.group("core"))
                    except ValueError:
                        core_guess = 0
                hexes = hex_token_re.findall(line)
                if not hexes:
                    continue
                try:
                    pc_guess = int(hexes[0], 16)
                except ValueError:
                    continue
                yield core, pc, ""

    @staticmethod
    def _classify_state(mnemonic: str) -> str:
        m = (mnemonic or "").strip().lower()
        if not m:
            return "active"
        if m in STALL_MNEMONICS:
            return "stall"
        # CPU-style trace semantics: memory ops are still useful executed work.
        if m.startswith(MEM_MNEMONICS_PREFIX):
            return "active"
        return "active"

    def build_state_intervals(self) -> pd.DataFrame:
        """
        Convert instruction stream into per-core state intervals.
        Timebase: instruction index * inst_us.
        """
        inst_us = float(self.cfg.inst_us)

        t_by_core: Dict[int, float] = {}
        rows: List[Dict] = []

        for core, _pc, mnemonic in self._iter_events():
            t0 = t_by_core.get(core, 0.0)
            t1 = t0 + inst_us
            t_by_core[core] = t1

            state = self._classify_state(mnemonic)
            rows.append({"start_us": t0, "end_us": t1, "core": core, "state": state})

        df = pd.DataFrame(rows)
        if len(df) == 0:
            # produce an empty-but-valid dataframe shape
            df = pd.DataFrame(columns=["start_us", "end_us", "core", "state"])

        # Optional: compress adjacent same-state intervals for smaller CSV
        df = self._merge_adjacent_state(df)

        return validate_state_df(df)

    def _merge_adjacent_state(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.sort_values(["core", "start_us"]).reset_index(drop=True)

        out = []
        cur = df.iloc[0].to_dict()
        for i in range(1, len(df)):
            r = df.iloc[i].to_dict()
            if r["core"] == cur["core"] and r["state"] == cur["state"] and abs(r["start_us"] - cur["end_us"]) < 1e-9:
                cur["end_us"] = r["end_us"]
            else:
                out.append(cur)
                cur = r
        out.append(cur)
        return pd.DataFrame(out)

    def build_residency_intervals(self) -> pd.DataFrame:
        """
        Create residency intervals.
        Heuristic: resident == (pc >= resident_pc_ge).
        Emits only resident segments (engine treats missing windows as non-resident).
        """
        inst_us = float(self.cfg.inst_us)
        thresh = int(self.cfg.resident_pc_ge)

        t_by_core: Dict[int, float] = {}
        # Track contiguous resident segments per core
        open_seg: Dict[int, Optional[float]] = {}  # core -> start_us if currently resident

        rows: List[Dict] = []

        for core, pc, _mnemonic in self._iter_events():
            t0 = t_by_core.get(core, 0.0)
            t1 = t0 + inst_us
            t_by_core[core] = t1

            is_res = pc >= thresh

            if is_res and open_seg.get(core) is None:
                open_seg[core] = t0
            if (not is_res) and open_seg.get(core) is not None:
                rs = float(open_seg[core])
                re = t0
                if re > rs:
                    rows.append({"start_us": rs, "end_us": re, "core": core, "resident": 1})
                open_seg[core] = None

        # close any open segments at end
        for core, rs in open_seg.items():
            if rs is None:
                continue
            end_t = t_by_core.get(core, rs)
            if end_t > rs:
                rows.append({
                    "start_us": float(rs),
                    "end_us": float(end_t),
                    "core": int(core),
                    "resident": 1,
                })

        rdf = pd.DataFrame(rows)
        # Keep schema stable even when rows are empty or partially inferred.
        rdf = rdf.reindex(columns=["start_us", "end_us", "core", "resident"])
        if len(rdf) == 0:
            # Fallback: if no explicit residency transitions were observed, mark each
            # parsed core as resident for its full observed timeline.
            fallback_rows = []
            for core, end_t in sorted(t_by_core.items()):
                if end_t > 0.0:
                    fallback_rows.append({"start_us": 0.0, "end_us": float(end_t), "core": int(core), "resident": 1})
            if fallback_rows:
                rdf = pd.DataFrame(fallback_rows).reindex(columns=["start_us", "end_us", "core", "resident"])

        return validate_resid_df(rdf)

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
    ap.add_argument("--inst-us", type=float, default=1.0, help="Time per instruction (us) for synthetic timeline")
    ap.add_argument("--resident-pc-ge", type=lambda x: int(x, 0), default=0x80000000, help="Residency PC threshold (int or hex)")
    args = ap.parse_args()

    cfg = SpikeParseConfig(inst_us=args.inst_us, resident_pc_ge=args.resident_pc_ge)
    ad = SpikePlatformAdapter(args.spike_trace, cfg=cfg)
    s_path, r_path = ad.export_baseline_csvs(args.out_dir)

    print("✓ wrote:", s_path)
    print("✓ wrote:", r_path)


if __name__ == "__main__":
    main()
