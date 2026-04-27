from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import math
import os
import re
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sit_classifier.ingest_api import validate_resid_df, validate_state_df
from sit_classifier.adapters.work_markers import allocate_work_done, decode_work_units

# Residency marker encodings: addi x0, x0, 101 / 102
RES_ON_INSN = 0x06500013
RES_OFF_INSN = 0x06600013
# Stall marker encodings: addi x0, x0, 103 / 104
STALL_ON_INSN = 0x06700013
STALL_OFF_INSN = 0x06800013
# Idle marker encodings: addi x0, x0, 105 / 106
IDLE_ON_INSN = 0x06900013
IDLE_OFF_INSN = 0x06A00013

CPU_RE = re.compile(r"\bcpu(?:[._])?(?P<core>\d+)\b", re.IGNORECASE)
PC_TID_RE = re.compile(r"T\d+\s*:\s*0x(?P<pc>[0-9a-fA-F]{1,16})")
HEX_RE = re.compile(r"0x(?P<hex>[0-9a-fA-F]{8,16})")
INSN_RE = re.compile(r"\(0x(?P<insn>[0-9a-fA-F]{8})\)")
ASM_RE = re.compile(
    r"T\d+\s*:\s*0x[0-9a-fA-F]{1,16}(?:\s+@[^:]+)?\s*:\s*(?P<asm>[^:]+?)\s*:\s*[A-Za-z][A-Za-z0-9_]*\s*:"
)

ADDI_ZERO_IMM_RE = re.compile(
    r"\baddi\s+(?:x0|zero)\s*,\s*(?:x0|zero)\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)
LI_ZERO_IMM_RE = re.compile(
    r"\bli\s+(?:x0|zero)\s*,\s*(?P<imm>-?(?:0x[0-9a-fA-F]+|\d+))\b",
    re.IGNORECASE,
)

STATS_BLOCK_BEGIN = "---------- Begin Simulation Statistics ----------"
STATS_BLOCK_END = "---------- End Simulation Statistics ----------"
STATS_LINE_RE = re.compile(
    r"^(?P<key>\S+)\s+(?P<val>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|nan|inf|-inf)\b"
)
CPU_KEY_RE = re.compile(r"^system\.cpu(?P<core>\d*)\.")


@dataclass
class Gem5ParseConfig:
    inst_us: float = 1.0
    resident_pc_ge: int = 0x80000000
    classification_mode: str = "strict"


@dataclass
class Gem5StatsParseConfig:
    ipc_active_thresh: float = 0.24
    stall_miss_thresh: float = 0.05
    l1_resident_thresh: float = 0.8
    mem_reqs_per_inst_thresh: float = 0.08
    idle_inst_thresh: float = 0.0


class Gem5PlatformAdapter:
    """
    Parse gem5 Exec debug traces and emit normalized state/residency intervals.

    State classification policy:
    - residency is marker-driven when present, else falls back to resident_pc_ge
    - explicit IDLE_* / STALL_* markers are authoritative
    - otherwise, control-flow / nop / fence / CSR-like instructions count as idle
    - memory / atomic style instructions count as stall
    - remaining instructions inside residency count as active
    """

    def __init__(self, gem5_trace_path: str, cfg: Optional[Gem5ParseConfig] = None):
        self.gem5_trace_path = gem5_trace_path
        self.cfg = cfg or Gem5ParseConfig()

    @staticmethod
    def _extract_core(line: str) -> int:
        m = CPU_RE.search(line)
        if not m:
            return 0
        try:
            return int(m.group("core"))
        except ValueError:
            return 0

    @staticmethod
    def _extract_pc(line: str) -> Optional[int]:
        m = PC_TID_RE.search(line)
        if m:
            try:
                return int(m.group("pc"), 16)
            except ValueError:
                return None

        # Fallback: first large hex token in line.
        for mm in HEX_RE.finditer(line):
            tok = mm.group("hex")
            if len(tok) >= 8:
                try:
                    return int(tok, 16)
                except ValueError:
                    pass
        return None

    @staticmethod
    def _extract_insn(line: str) -> Optional[int]:
        m = INSN_RE.search(line)
        if not m:
            return None
        try:
            return int(m.group("insn"), 16)
        except ValueError:
            return None

    @staticmethod
    def _extract_mnemonic(line: str) -> str:
        # Typical format:
        # ... T0 : 0xADDR @sym : <mnemonic operands> : <OpClass> : ...
        m = ASM_RE.search(line)
        if m:
            return m.group("asm").strip()

        # Fallback: if we can find a known op-class token, instruction asm is
        # usually the field immediately before it.
        parts = [p.strip() for p in line.split(":") if p.strip()]
        for i, seg in enumerate(parts):
            if re.match(r"^[A-Za-z][A-Za-z0-9_]*$", seg) and any(ch.islower() for ch in seg):
                if i > 0:
                    prev = parts[i - 1].strip()
                    if prev:
                        return prev
        return ""

    @staticmethod
    def _extract_marker_from_text(raw_mnemonic: str) -> Optional[int]:
        if not raw_mnemonic:
            return None
        for rx in (ADDI_ZERO_IMM_RE, LI_ZERO_IMM_RE):
            m = rx.search(raw_mnemonic)
            if not m:
                continue
            try:
                return int(m.group("imm"), 0)
            except ValueError:
                continue
        return None

    @staticmethod
    def _is_idle(norm_mnemonic: str) -> bool:
        n = norm_mnemonic.replace(".", "_")
        return (
            n in ("nop", "c_nop", "residency_on", "residency_off", "stall_on", "stall_off", "idle_on", "idle_off")
            or n in (
                "j",
                "jr",
                "jal",
                "jalr",
                "ret",
                "beq",
                "bne",
                "blt",
                "bge",
                "bltu",
                "bgeu",
                "c_j",
                "c_jal",
                "c_jr",
                "c_jalr",
                "c_beqz",
                "c_bnez",
                "fence",
                "fence_i",
                "fence_tso",
            )
            or n.startswith("csrr")
        )

    def _is_stall(self, norm_mnemonic: str, *, is_mem_op: bool) -> bool:
        n = norm_mnemonic.replace(".", "_")
        if self.cfg.classification_mode == "compute_biased":
            return n.startswith("amo") or n.startswith("lr") or n.startswith("sc")
        return (
            is_mem_op
            or (n.startswith("l") and n not in ("li", "lui", "la"))
            or (n.startswith("s") and n not in ("slli", "srli", "srai"))
            or n in (
                "c_lw",
                "c_lwsp",
                "c_ld",
                "c_ldsp",
                "c_flw",
                "c_flwsp",
                "c_fld",
                "c_fldsp",
                "c_sw",
                "c_swsp",
                "c_sd",
                "c_sdsp",
                "c_fsw",
                "c_fswsp",
                "c_fsd",
                "c_fsdsp",
            )
            or n.startswith("amo")
            or n.startswith("lr")
            or n.startswith("sc")
        )

    def _iter_events(self) -> Iterable[Tuple[int, str, int, str, Optional[int], Optional[int], bool]]:
        inst_count_by_core: Dict[int, int] = {}

        with open(self.gem5_trace_path, "r", errors="ignore") as f:
            for line in f:
                if "cpu" not in line.lower() and "0x" not in line:
                    continue

                core = self._extract_core(line)
                pc = self._extract_pc(line)
                insn_val = self._extract_insn(line)
                raw_mnemonic = self._extract_mnemonic(line)
                norm_mnemonic = raw_mnemonic.split()[0].lower() if raw_mnemonic else ""
                is_mem_op = (": MemRead :" in line) or (": MemWrite :" in line)

                marker_imm = self._extract_marker_from_text(raw_mnemonic)
                if insn_val == RES_ON_INSN or marker_imm == 101:
                    raw_mnemonic = "RESIDENCY_ON"
                    norm_mnemonic = "residency_on"
                    insn_val = RES_ON_INSN
                elif insn_val == RES_OFF_INSN or marker_imm == 102:
                    raw_mnemonic = "RESIDENCY_OFF"
                    norm_mnemonic = "residency_off"
                    insn_val = RES_OFF_INSN
                elif insn_val == STALL_ON_INSN or marker_imm == 103:
                    raw_mnemonic = "STALL_ON"
                    norm_mnemonic = "stall_on"
                    insn_val = STALL_ON_INSN
                elif insn_val == STALL_OFF_INSN or marker_imm == 104:
                    raw_mnemonic = "STALL_OFF"
                    norm_mnemonic = "stall_off"
                    insn_val = STALL_OFF_INSN
                elif insn_val == IDLE_ON_INSN or marker_imm == 105:
                    raw_mnemonic = "IDLE_ON"
                    norm_mnemonic = "idle_on"
                    insn_val = IDLE_ON_INSN
                elif insn_val == IDLE_OFF_INSN or marker_imm == 106:
                    raw_mnemonic = "IDLE_OFF"
                    norm_mnemonic = "idle_off"
                    insn_val = IDLE_OFF_INSN

                # Keep only instruction-like rows.
                if pc is None and not norm_mnemonic:
                    continue

                inst_count_by_core[core] = inst_count_by_core.get(core, 0) + 1
                inst_count = inst_count_by_core[core]

                yield core, norm_mnemonic, inst_count, raw_mnemonic, pc, insn_val, is_mem_op

    def _collect_core_timeline(self) -> Dict[int, Dict[str, List]]:
        inst_us = float(self.cfg.inst_us)
        resident_pc_ge = int(self.cfg.resident_pc_ge)

        marker_on_start_by_core: Dict[int, Optional[float]] = {}
        marker_starts_by_core: Dict[int, List[float]] = {}
        marker_ends_by_core: Dict[int, List[float]] = {}

        fallback_on_start_by_core: Dict[int, Optional[float]] = {}
        fallback_starts_by_core: Dict[int, List[float]] = {}
        fallback_ends_by_core: Dict[int, List[float]] = {}

        state_intervals_by_core: Dict[int, List[Tuple[float, float, str]]] = {}
        work_markers_by_core: Dict[int, List[Tuple[float, float]]] = {}
        current_state_by_core: Dict[int, Optional[Tuple[float, str]]] = {}

        max_t_by_core: Dict[int, float] = {}
        in_residency_by_core: Dict[int, bool] = {}
        markers_seen_by_core: Dict[int, bool] = {}
        forced_stall_by_core: Dict[int, bool] = {}
        forced_idle_by_core: Dict[int, bool] = {}

        for core, mnemonic, inst_count, raw_mnemonic, pc, insn_val, is_mem_op in self._iter_events():
            t1 = float(inst_count) * inst_us
            max_t_by_core[core] = max(max_t_by_core.get(core, 0.0), t1)
            was_in_residency = in_residency_by_core.get(core, False)

            if insn_val == RES_ON_INSN:
                markers_seen_by_core[core] = True

                if fallback_on_start_by_core.get(core) is not None:
                    start_t = fallback_on_start_by_core[core]
                    if start_t is not None and t1 > start_t:
                        fallback_starts_by_core.setdefault(core, []).append(float(start_t))
                        fallback_ends_by_core.setdefault(core, []).append(float(t1))
                    fallback_on_start_by_core[core] = None

                marker_on_start_by_core[core] = t1
                in_residency_by_core[core] = True

            elif insn_val == RES_OFF_INSN:
                markers_seen_by_core[core] = True
                start_t = marker_on_start_by_core.get(core)
                if start_t is not None and t1 > start_t:
                    marker_starts_by_core.setdefault(core, []).append(float(start_t))
                    marker_ends_by_core.setdefault(core, []).append(float(t1))
                marker_on_start_by_core[core] = None
                in_residency_by_core[core] = False

            if insn_val == STALL_ON_INSN:
                forced_stall_by_core[core] = True
            elif insn_val == STALL_OFF_INSN:
                forced_stall_by_core[core] = False
            elif insn_val == IDLE_ON_INSN:
                forced_idle_by_core[core] = True
            elif insn_val == IDLE_OFF_INSN:
                forced_idle_by_core[core] = False

            work_units = decode_work_units(
                insn_val=insn_val,
                marker_imm=self._extract_marker_from_text(raw_mnemonic),
            )
            if work_units and (was_in_residency or in_residency_by_core.get(core, False)):
                work_markers_by_core.setdefault(core, []).append((t1, float(work_units)))
                continue

            if not markers_seen_by_core.get(core, False):
                in_resident_range = pc is not None and pc >= resident_pc_ge

                if in_resident_range and fallback_on_start_by_core.get(core) is None:
                    fallback_on_start_by_core[core] = t1
                    in_residency_by_core[core] = True
                elif (not in_resident_range) and fallback_on_start_by_core.get(core) is not None:
                    start_t = fallback_on_start_by_core[core]
                    if start_t is not None and t1 > start_t:
                        fallback_starts_by_core.setdefault(core, []).append(float(start_t))
                        fallback_ends_by_core.setdefault(core, []).append(float(t1))
                    fallback_on_start_by_core[core] = None
                    in_residency_by_core[core] = False

            if in_residency_by_core.get(core, False):
                if forced_stall_by_core.get(core, False):
                    new_state = "stall"
                elif forced_idle_by_core.get(core, False):
                    new_state = "idle"
                elif self._is_idle(mnemonic):
                    new_state = "idle"
                elif self._is_stall(mnemonic, is_mem_op=is_mem_op):
                    new_state = "stall"
                else:
                    new_state = "active"
                current = current_state_by_core.get(core)
                if current is None:
                    current_state_by_core[core] = (t1, new_state)
                else:
                    start_t, curr_state = current
                    if curr_state != new_state:
                        state_intervals_by_core.setdefault(core, []).append((start_t, t1, curr_state))
                        current_state_by_core[core] = (t1, new_state)
            else:
                current = current_state_by_core.get(core)
                if current is not None:
                    start_t, curr_state = current
                    state_intervals_by_core.setdefault(core, []).append((start_t, t1, curr_state))
                    current_state_by_core[core] = None

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

        for core, current in current_state_by_core.items():
            if current is None:
                continue
            start_t, curr_state = current
            end_t = max_t_by_core.get(core, start_t)
            if end_t > start_t:
                state_intervals_by_core.setdefault(core, []).append((start_t, end_t, curr_state))

        out: Dict[int, Dict[str, List]] = {}
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
                "state_intervals": state_intervals_by_core.get(core, []),
                "work_markers": work_markers_by_core.get(core, []),
            }
        return out

    def build_residency_intervals(self) -> pd.DataFrame:
        timeline = self._collect_core_timeline()

        rows: List[Dict] = []
        for core, meta in timeline.items():
            for s, e in zip(meta["starts"], meta["ends"]):
                if e > s:
                    rows.append({"start_us": s, "end_us": e, "core": core, "resident": 1})

        rdf = pd.DataFrame(rows)
        rdf = rdf.reindex(columns=["start_us", "end_us", "core", "resident"])
        return validate_resid_df(rdf)

    def build_state_intervals(self) -> pd.DataFrame:
        timeline = self._collect_core_timeline()
        work_enabled = any(bool(meta.get("work_markers", [])) for meta in timeline.values())

        rows: List[Dict] = []
        for core, meta in timeline.items():
            state_intervals = meta.get("state_intervals", [])
            max_t = float(meta["max_t"][0]) if meta["max_t"] else 0.0
            core_rows: List[Dict] = []

            if state_intervals:
                for start_t, end_t, state in state_intervals:
                    if end_t > start_t:
                        core_rows.append({"start_us": start_t, "end_us": end_t, "core": core, "state": state})

                sorted_intervals = sorted(state_intervals, key=lambda x: x[0])
                t = 0.0
                for start_t, end_t, _ in sorted_intervals:
                    if start_t > t:
                        core_rows.append({"start_us": t, "end_us": start_t, "core": core, "state": "idle"})
                    t = max(t, end_t)
                if t < max_t:
                    core_rows.append({"start_us": t, "end_us": max_t, "core": core, "state": "idle"})
            else:
                starts = [float(x) for x in meta["starts"]]
                ends = [float(x) for x in meta["ends"]]
                if max_t <= 0.0:
                    continue

                spans = sorted([(s, e) for s, e in zip(starts, ends) if e > s], key=lambda x: x[0])
                t = 0.0
                for s, e in spans:
                    if s > t:
                        core_rows.append({"start_us": t, "end_us": s, "core": core, "state": "idle"})
                    core_rows.append({"start_us": s, "end_us": e, "core": core, "state": "active"})
                    t = max(t, e)
                if t < max_t:
                    core_rows.append({"start_us": t, "end_us": max_t, "core": core, "state": "idle"})

            if work_enabled and core_rows:
                core_rows = sorted(core_rows, key=lambda row: row["start_us"])
                allocations = allocate_work_done(
                    [(row["start_us"], row["end_us"], row["state"]) for row in core_rows],
                    meta.get("work_markers", []),
                )
                for row, value in zip(core_rows, allocations):
                    row["work_done"] = float(value)

            rows.extend(core_rows)

        df = pd.DataFrame(rows)
        if len(df) == 0:
            cols = ["start_us", "end_us", "core", "state"]
            if work_enabled:
                cols.append("work_done")
            df = pd.DataFrame(columns=cols)
        else:
            df = df.sort_values(["core", "start_us"]).reset_index(drop=True)

        return validate_state_df(df)

    def export_baseline_csvs(self, out_dir: str) -> Tuple[str, str]:
        os.makedirs(out_dir, exist_ok=True)

        state_df = self.build_state_intervals()
        resid_df = self.build_residency_intervals()

        state_path = os.path.join(out_dir, "state_intervals.csv")
        resid_path = os.path.join(out_dir, "residency_intervals.csv")

        state_df.to_csv(state_path, index=False)
        resid_df.to_csv(resid_path, index=False)
        return state_path, resid_path


class Gem5StatsPlatformAdapter:
    """
    Parse gem5 stats dump blocks and emit interval state/residency CSVs.

    This follows the stats-driven mapping:
    - time: ticks -> us with global t0 normalization
    - core: system.cpu[N] prefix
    - state: per-interval IPC/miss based classification
    - residency: per-interval L1 hit-rate + memory-pressure gating
    """

    def __init__(self, gem5_stats_path: str, cfg: Optional[Gem5StatsParseConfig] = None):
        self.gem5_stats_path = gem5_stats_path
        self.cfg = cfg or Gem5StatsParseConfig()

    @staticmethod
    def _safe_float(x: Optional[float], default: float = 0.0) -> float:
        if x is None:
            return default
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return default
        return float(x)

    @staticmethod
    def _core_prefixes(core: int) -> list[str]:
        if core == 0:
            return ["system.cpu.", "system.cpu0."]
        return [f"system.cpu{core}."]

    @staticmethod
    def _pick_metric(metrics: Dict[str, float], names: list[str]) -> Optional[float]:
        for n in names:
            if n in metrics:
                return metrics[n]
        return None

    def _pick_core_metric(self, metrics: Dict[str, float], core: int, suffixes: list[str]) -> Optional[float]:
        for p in self._core_prefixes(core):
            for s in suffixes:
                key = p + s
                if key in metrics:
                    return metrics[key]
        return None

    def _parse_stats_blocks(self) -> List[Dict[str, float]]:
        blocks: list[dict[str, float]] = []
        current: Optional[dict[str, float]] = None

        with open(self.gem5_stats_path, "r", errors="ignore") as f:
            for raw in f:
                line = raw.strip()
                if line.startswith("---------- Begin Simulation Statistics"):
                    current = {}
                    continue
                if line.startswith("---------- End Simulation Statistics"):
                    if current is not None:
                        blocks.append(current)
                    current = None
                    continue
                if current is None:
                    continue

                m = STATS_LINE_RE.match(line)
                if not m:
                    continue
                key = m.group("key")
                tok = m.group("val")
                try:
                    current[key] = float(tok)
                except ValueError:
                    continue
        return blocks

    @staticmethod
    def _cores_in_block(metrics: Dict[str, float]) -> list[int]:
        cores: set[int] = set()
        for k in metrics.keys():
            m = CPU_KEY_RE.match(k)
            if not m:
                continue
            tok = m.group("core")
            if tok == "":
                cores.add(0)
            else:
                try:
                    cores.add(int(tok))
                except ValueError:
                    continue
        if not cores:
            cores.add(0)
        return sorted(cores)

    def _classify_interval(self, metrics: Dict[str, float], core: int) -> tuple[str, bool]:
        committed = self._safe_float(
            self._pick_core_metric(metrics, core, ["commitStats0.numInsts", "numInsts"]),
            0.0,
        )
        ipc = self._safe_float(
            self._pick_core_metric(metrics, core, ["commitStats0.ipc", "ipc"]),
            0.0,
        )
        hits = self._safe_float(
            self._pick_core_metric(
                metrics,
                core,
                [
                    "dcache.overallHits::total",
                    "dcache.demandHits::total",
                    "dcache.overallHits::cpu.data",
                    "dcache.demandHits::cpu.data",
                ],
            ),
            0.0,
        )
        misses = self._safe_float(
            self._pick_core_metric(
                metrics,
                core,
                [
                    "dcache.overallMisses::total",
                    "dcache.demandMisses::total",
                    "dcache.overallMisses::cpu.data",
                    "dcache.demandMisses::cpu.data",
                ],
            ),
            0.0,
        )
        accesses = hits + misses

        miss_rate_metric = self._pick_core_metric(
            metrics,
            core,
            ["dcache.overallMissRate::total", "dcache.demandMissRate::total"],
        )
        if accesses > 0:
            miss_rate = misses / accesses
            l1_hit_rate = hits / accesses
        elif miss_rate_metric is not None:
            miss_rate = self._safe_float(miss_rate_metric, 1.0)
            l1_hit_rate = max(0.0, 1.0 - miss_rate)
        else:
            # No observed cache traffic in the stats window is cache-neutral,
            # not an automatic miss-heavy stall window.
            miss_rate = 0.0
            l1_hit_rate = 1.0

        mem_reads = self._safe_float(
            self._pick_metric(metrics, ["system.mem_ctrls.readReqs", "system.mem_ctrl.readReqs"]),
            0.0,
        )
        mem_writes = self._safe_float(
            self._pick_metric(metrics, ["system.mem_ctrls.writeReqs", "system.mem_ctrl.writeReqs"]),
            0.0,
        )
        mem_reqs = mem_reads + mem_writes
        mem_reqs_per_inst = mem_reqs / max(committed, 1.0)
        l2_misses = self._safe_float(
            self._pick_metric(
                metrics,
                [
                    "system.l2cache.overallMisses::total",
                    "system.l2.overallMisses::total",
                    "system.l2cache.demandMisses::total",
                    "system.l2.demandMisses::total",
                ],
            ),
            0.0,
        )

        if committed <= float(self.cfg.idle_inst_thresh):
            state = "idle"
        elif ipc >= float(self.cfg.ipc_active_thresh):
            state = "active"
        elif miss_rate >= float(self.cfg.stall_miss_thresh):
            state = "stall"
        elif l2_misses > 0.0:
            state = "stall"
        elif mem_reqs_per_inst >= float(self.cfg.mem_reqs_per_inst_thresh):
            state = "stall"
        else:
            # If the interval is doing work and we do not see clear memory
            # pressure, treat it as active instead of a synthetic stall.
            state = "active"

        resident = (
            l1_hit_rate >= float(self.cfg.l1_resident_thresh)
            and mem_reqs_per_inst <= float(self.cfg.mem_reqs_per_inst_thresh)
        )
        return state, resident

    def _build_interval_rows(self) -> tuple[list[dict], list[dict]]:
        blocks = self._parse_stats_blocks()
        if not blocks:
            return [], []

        state_rows: list[dict] = []
        resid_rows: list[dict] = []

        prev_end_tick = 0.0
        interval_ticks: list[tuple[float, float, Dict[str, float]]] = []
        for blk in blocks:
            final_tick = self._safe_float(self._pick_metric(blk, ["finalTick"]), float("nan"))
            sim_ticks = self._safe_float(self._pick_metric(blk, ["simTicks"]), float("nan"))
            if not math.isnan(final_tick) and final_tick > 0.0:
                end_tick = final_tick
            elif not math.isnan(sim_ticks) and sim_ticks > 0.0:
                end_tick = prev_end_tick + sim_ticks
            else:
                continue

            start_tick = prev_end_tick
            if end_tick <= start_tick:
                continue
            interval_ticks.append((start_tick, end_tick, blk))
            prev_end_tick = end_tick

        if not interval_ticks:
            return [], []

        t0 = min(s for s, _, _ in interval_ticks)
        sim_freq = self._safe_float(
            self._pick_metric(interval_ticks[-1][2], ["simFreq"]),
            1_000_000_000_000.0,
        )
        ticks_per_us = sim_freq / 1_000_000.0 if sim_freq > 0 else 1_000_000.0

        for start_tick, end_tick, blk in interval_ticks:
            start_us = (start_tick - t0) / ticks_per_us
            end_us = (end_tick - t0) / ticks_per_us
            if end_us <= start_us:
                continue

            for core in self._cores_in_block(blk):
                state, resident = self._classify_interval(blk, core)
                state_rows.append(
                    {
                        "start_us": start_us,
                        "end_us": end_us,
                        "core": core,
                        "state": state,
                    }
                )
                if resident:
                    resid_rows.append(
                        {
                            "start_us": start_us,
                            "end_us": end_us,
                            "core": core,
                            "resident": 1,
                        }
                    )
        return state_rows, resid_rows

    def build_state_intervals(self) -> pd.DataFrame:
        state_rows, _ = self._build_interval_rows()
        df = pd.DataFrame(state_rows)
        if len(df) == 0:
            df = pd.DataFrame(columns=["start_us", "end_us", "core", "state"])
        else:
            df = df.sort_values(["core", "start_us"]).reset_index(drop=True)
        return validate_state_df(df)

    def build_residency_intervals(self) -> pd.DataFrame:
        _, resid_rows = self._build_interval_rows()
        rdf = pd.DataFrame(resid_rows)
        rdf = rdf.reindex(columns=["start_us", "end_us", "core", "resident"])
        return validate_resid_df(rdf)

    def export_baseline_csvs(self, out_dir: str) -> Tuple[str, str]:
        os.makedirs(out_dir, exist_ok=True)

        state_df = self.build_state_intervals()
        resid_df = self.build_residency_intervals()

        state_path = os.path.join(out_dir, "state_intervals.csv")
        resid_path = os.path.join(out_dir, "residency_intervals.csv")

        state_df.to_csv(state_path, index=False)
        resid_df.to_csv(resid_path, index=False)
        return state_path, resid_path


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--gem5-trace", default=None, help="gem5 Exec debug trace file")
    ap.add_argument("--gem5-stats", default=None, help="gem5 stats.txt file (preferred for strict stats mode)")
    ap.add_argument("--out-dir", required=True, help="Directory to write baseline CSVs")

    # Exec-trace mode knobs
    ap.add_argument("--inst-us", type=float, default=1.0, help="Time per instruction (us)")
    ap.add_argument(
        "--resident-pc-ge",
        type=lambda x: int(x, 0),
        default=0x80000000,
        help="Fallback residency PC threshold",
    )
    ap.add_argument("--classification-mode", choices=["strict", "compute_biased"], default="strict")

    # Stats mode thresholds (slide-aligned classification)
    ap.add_argument("--ipc-active-thresh", type=float, default=0.24)
    ap.add_argument("--stall-miss-thresh", type=float, default=0.05)
    ap.add_argument("--l1-resident-thresh", type=float, default=0.8)
    ap.add_argument("--mem-reqs-per-inst-thresh", type=float, default=0.08)
    ap.add_argument("--idle-inst-thresh", type=float, default=0.0)
    args = ap.parse_args()

    if not args.gem5_trace and not args.gem5_stats:
        raise SystemExit("Pass --gem5-stats (preferred) or --gem5-trace.")

    if args.gem5_stats:
        cfg = Gem5StatsParseConfig(
            ipc_active_thresh=args.ipc_active_thresh,
            stall_miss_thresh=args.stall_miss_thresh,
            l1_resident_thresh=args.l1_resident_thresh,
            mem_reqs_per_inst_thresh=args.mem_reqs_per_inst_thresh,
            idle_inst_thresh=args.idle_inst_thresh,
        )
        ad = Gem5StatsPlatformAdapter(args.gem5_stats, cfg=cfg)
    else:
        cfg = Gem5ParseConfig(
            inst_us=args.inst_us,
            resident_pc_ge=args.resident_pc_ge,
            classification_mode=str(args.classification_mode),
        )
        ad = Gem5PlatformAdapter(args.gem5_trace, cfg=cfg)

    s_path, r_path = ad.export_baseline_csvs(args.out_dir)

    print("✓ wrote:", s_path)
    print("✓ wrote:", r_path)


if __name__ == "__main__":
    main()
