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

from sit_classifier.ingest_api import validate_state_df, validate_resid_df
from sit_classifier.adapters.work_markers import allocate_work_done, decode_work_units

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
STALL_ON_MARKER = 103
STALL_OFF_MARKER = 104
IDLE_ON_MARKER = 105
IDLE_OFF_MARKER = 106
# Residency markers (encoded as addi x0,x0,imm). Spike may print as "li zero, imm".
RES_ON_INSN  = 0x06500013  # imm=101
RES_OFF_INSN = 0x06600013  # imm=102
STALL_ON_INSN  = 0x06700013  # imm=103
STALL_OFF_INSN = 0x06800013  # imm=104
IDLE_ON_INSN = 0x06900013  # imm=105
IDLE_OFF_INSN = 0x06A00013  # imm=106
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


@dataclass
class SpikeParseConfig:
    inst_us: float = 1.0
    resident_pc_ge: int = 0x80000000
    classification_mode: str = "strict"


class SpikePlatformAdapter:
    """
    Platform adapter (Spike) -> emits baseline CSVs that BaselineAdapter can read.

    Output CSV schemas are exactly what ingest_api.validate_* expects:
      state: start_us,end_us,core,state
      resid: start_us,end_us,core[,resident]
    
    State classification policy:
    - residency is marker-driven when present, else falls back to resident_pc_ge
    - explicit IDLE_* / STALL_* markers are authoritative
    - otherwise, control-flow / nop / fence / CSR-like instructions count as idle
    - memory / atomic style instructions count as stall
    - remaining instructions inside residency count as active
    """

    def __init__(self, spike_trace_path: str, cfg: Optional[SpikeParseConfig] = None):
        self.spike_trace_path = spike_trace_path
        self.cfg = cfg or SpikeParseConfig()


    def _iter_events(self) -> Iterable[Tuple[int, str, int, str, Optional[int],Optional[int]]]:
        """
        Yield per-instruction events as:
        (core, normalized_mnemonic, inst_count, raw_mnemonic, pc, insn_val)

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
                insn_val: Optional[int] = None

                m = SPIKE_LINE_RE.search(line)
                if m:
                    core = int(m.group("core"))
                    try:
                        pc = int(m.group("pc"), 16)
                    except Exception:
                        pc = None

                    try:
                        insn_str = (m.group("insn") or "").strip()
                        # handle both "06500013" and "0x06500013" just in case
                        if insn_str.startswith("0x") or insn_str.startswith("0X"):
                            insn_str = insn_str[2:]
                        insn_val = int(insn_str, 16) if insn_str else None

                    except Exception:
                        insn_val = None

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

                    # Require at least one PC-like token on fallback paths to avoid chatter.
                    if core is None or not hex_token_re.findall(line):
                        continue

                    pc_m = PC_AFTER_CORE_RE.search(line)
                    if pc_m:
                        try:
                            pc = int(pc_m.group("pc"), 16)
                        except Exception:
                            pc = None

                    tail = line.split(")", 1)
                    if len(tail) == 2:
                        tok = tail[1].strip().split()
                        mnemonic = tok[0] if tok else ""

                if core is None:
                    continue

                # --- Count this instruction (per core) ---
                inst_count_by_core[core] = inst_count_by_core.get(core, 0) + 1
                inst_count = inst_count_by_core[core]

                raw_mnemonic = (mnemonic or "").strip()
                norm_mnemonic = raw_mnemonic.split()[0].lower() if raw_mnemonic else ""

                # --- Residency markers by instruction word (robust to "li zero, 101") ---
                if insn_val == RES_ON_INSN:
                    raw_mnemonic = "RESIDENCY_ON"
                    norm_mnemonic = "residency_on"
                elif insn_val == RES_OFF_INSN:
                    raw_mnemonic = "RESIDENCY_OFF"
                    norm_mnemonic = "residency_off"
                elif insn_val == STALL_ON_INSN:
                    raw_mnemonic = "STALL_ON"
                    norm_mnemonic = "stall_on"
                elif insn_val == STALL_OFF_INSN:
                    raw_mnemonic = "STALL_OFF"
                    norm_mnemonic = "stall_off"
                elif insn_val == IDLE_ON_INSN:
                    raw_mnemonic = "IDLE_ON"
                    norm_mnemonic = "idle_on"
                elif insn_val == IDLE_OFF_INSN:
                    raw_mnemonic = "IDLE_OFF"
                    norm_mnemonic = "idle_off"
                if insn_val is not None and insn_val in (
                    RES_ON_INSN,
                    RES_OFF_INSN,
                    STALL_ON_INSN,
                    STALL_OFF_INSN,
                    IDLE_ON_INSN,
                    IDLE_OFF_INSN,
                ):
                    print("ITER_MARKER:", core, insn_val, hex(insn_val), "pc", hex(pc) if pc is not None else None, "rawtail", mnemonic)

                yield core, norm_mnemonic, inst_count, raw_mnemonic, pc, insn_val


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

    def _is_stall(self, norm_mnemonic: str) -> bool:
        n = norm_mnemonic.replace(".", "_")
        if self.cfg.classification_mode == "compute_biased":
            return n.startswith("amo") or n.startswith("lr") or n.startswith("sc")
        return (
            (n.startswith("l") and n not in ("li", "lui", "la"))
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

    def _collect_core_timeline(self) -> Dict[int, Dict[str, List]]:
        """
        Parse commit-log once and collect per-core timeline with state detection.

        Preferred residency detection is marker-driven (RESIDENCY_ON/RESIDENCY_OFF tokens
        emitted by _iter_events() via instruction-word match). If markers are absent for a
        core, fall back to PC-threshold residency using resident_pc_ge.

        State behavior:
        - explicit STALL_ON/STALL_OFF markers are authoritative
        - explicit IDLE_ON/IDLE_OFF markers are authoritative
        - otherwise, instruction class drives state:
          control/no-op/fence/csr -> idle, memory/atomic -> stall, compute -> active
        """
        inst_us = float(self.cfg.inst_us)
        resident_pc_ge = int(self.cfg.resident_pc_ge)

        # Marker-driven residency spans
        marker_on_start_by_core: Dict[int, Optional[float]] = {}
        marker_starts_by_core: Dict[int, List[float]] = {}
        marker_ends_by_core: Dict[int, List[float]] = {}

        # Fallback residency spans (PC-threshold)
        fallback_on_start_by_core: Dict[int, Optional[float]] = {}
        fallback_starts_by_core: Dict[int, List[float]] = {}
        fallback_ends_by_core: Dict[int, List[float]] = {}

        # Track state intervals (active/idle/stall) *within residency*
        state_intervals_by_core: Dict[int, List[Tuple[float, float, str]]] = {}
        work_markers_by_core: Dict[int, List[Tuple[float, float]]] = {}
        current_state_by_core: Dict[int, Optional[Tuple[float, str]]] = {}
        forced_stall_by_core: Dict[int, bool] = {}
        forced_idle_by_core: Dict[int, bool] = {}

        max_t_by_core: Dict[int, float] = {}
        in_residency_by_core: Dict[int, bool] = {}

        # Whether we have ever seen markers for this core
        markers_seen_by_core: Dict[int, bool] = {}

        for core, mnemonic, inst_count, raw_mnemonic, pc, insn_val in self._iter_events():
            t1 = float(inst_count) * inst_us
            max_t_by_core[core] = max(max_t_by_core.get(core, 0.0), t1)
            was_in_residency = in_residency_by_core.get(core, False)

            # -------------------------------
            # 1) Marker-driven residency (authoritative) via instruction word
            # -------------------------------
            if insn_val == RES_ON_INSN:
                markers_seen_by_core[core] = True

                # If fallback had started earlier, close it at marker ON boundary.
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
            elif insn_val == STALL_ON_INSN:
                forced_stall_by_core[core] = True
            elif insn_val == STALL_OFF_INSN:
                forced_stall_by_core[core] = False
            elif insn_val == IDLE_ON_INSN:
                forced_idle_by_core[core] = True
            elif insn_val == IDLE_OFF_INSN:
                forced_idle_by_core[core] = False

            work_units = decode_work_units(
                insn_val=insn_val,
                marker_imm=(
                    self._extract_marker_id(raw_mnemonic, ADDI_ZERO_IMM_RE)
                    or self._extract_marker_id(raw_mnemonic, LI_ZERO_IMM_RE)
                ),
            )
            if work_units and (was_in_residency or in_residency_by_core.get(core, False)):
                work_markers_by_core.setdefault(core, []).append((t1, float(work_units)))
                continue

            # -------------------------------
            # 2) PC-threshold fallback residency (only if no markers ever seen)
            # -------------------------------
            if not markers_seen_by_core.get(core, False):
                in_resident_range = (pc is not None and pc >= resident_pc_ge)

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

            # -------------------------------
            # 3) State detection inside residency
            # -------------------------------
            if in_residency_by_core.get(core, False):
                if forced_stall_by_core.get(core, False):
                    new_state = "stall"
                elif forced_idle_by_core.get(core, False):
                    new_state = "idle"
                elif self._is_idle(mnemonic):
                    new_state = "idle"
                elif self._is_stall(mnemonic):
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

        # -------------------------------
        # Close dangling open intervals at trace end
        # -------------------------------
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

        # -------------------------------
        # Emit per-core output: prefer marker spans if any exist, else fallback
        # -------------------------------
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
        Build state intervals from explicit idle/stall markers within residency.
        Uses actual instruction-level state detection instead of just residency.
        """
        timeline = self._collect_core_timeline()
        work_enabled = any(bool(meta.get("work_markers", [])) for meta in timeline.values())

        rows: List[Dict] = []
        for core, meta in timeline.items():
            state_intervals = meta.get("state_intervals", [])
            max_t = float(meta["max_t"][0]) if meta["max_t"] else 0.0
            core_rows: List[Dict] = []
            
            if state_intervals:
                # Use fine-grained state intervals
                for start_t, end_t, state in state_intervals:
                    if end_t > start_t:
                        core_rows.append({"start_us": start_t, "end_us": end_t, "core": core, "state": state})
                
                # Fill gaps outside residency with idle
                sorted_intervals = sorted(state_intervals, key=lambda x: x[0])
                t = 0.0
                for start_t, end_t, _ in sorted_intervals:
                    if start_t > t:
                        core_rows.append({"start_us": t, "end_us": start_t, "core": core, "state": "idle"})
                    t = max(t, end_t)
                if t < max_t:
                    core_rows.append({"start_us": t, "end_us": max_t, "core": core, "state": "idle"})
            else:
                # Fallback: use residency-based intervals
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

    # ============================================================================
    # ENHANCED: VALIDATION AND DIAGNOSTIC METHODS
    # ============================================================================

    def _debug_marker_detection(self, max_lines: int = 20):
        """
        Debug helper: print first N lines of trace to verify marker format.
        
        Expected patterns:
          - addi x0, x0, 101  (marker ON)
          - addi x0, x0, 102  (marker OFF)
        """
        print("\n=== SPIKE TRACE SAMPLE ===")
        try:
            with open(self.spike_trace_path, "r", errors="ignore") as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    if "core" in line and "0x" in line:
                        print(f"  {line.rstrip()}")
        except Exception as e:
            print(f"Error reading trace: {e}")
        print()

    def _check_for_marker_instructions(self, verbose: bool = True):
        """
        Scan trace for marker instructions and report findings.
        """
        addi_101_count = 0
        addi_102_count = 0
        li_101_count = 0
        li_102_count = 0
        
        pattern_addi_101 = re.compile(r"\baddi\s+x0\s*,\s*x0\s*,\s*101\b", re.IGNORECASE)
        pattern_addi_102 = re.compile(r"\baddi\s+x0\s*,\s*x0\s*,\s*102\b", re.IGNORECASE)
        pattern_li_101 = re.compile(r"\bli\s+\w+\s*,\s*101\b", re.IGNORECASE)
        pattern_li_102 = re.compile(r"\bli\s+\w+\s*,\s*102\b", re.IGNORECASE)
        
        try:
            with open(self.spike_trace_path, "r", errors="ignore") as f:
                for line in f:
                    if pattern_addi_101.search(line):
                        addi_101_count += 1
                    if pattern_addi_102.search(line):
                        addi_102_count += 1
                    if pattern_li_101.search(line):
                        li_101_count += 1
                    if pattern_li_102.search(line):
                        li_102_count += 1
        except Exception as e:
            print(f"Error scanning trace: {e}")
            return (False, False), (False, False)
        
        if verbose:
            print()
        
        return (addi_101_count > 0, addi_102_count > 0), (li_101_count > 0, li_102_count > 0)

    def _validate_residency_timing(self, timeline: Dict) -> bool:
        """
        Check if residency detection is reasonable.
        """
        for core, meta in timeline.items():
            starts = meta.get("starts", [])
            if not starts:
                print(f"⚠ Core {core}: No residency intervals detected")
                print(f"  Using PC threshold fallback")
                return False
            
            first_start = min(starts)
        
        return True

    def _print_residency_summary(self, timeline: Dict):
        """Print summary of detected residency regions."""
        print("\n=== RESIDENCY DETECTION SUMMARY ===")
        for core, meta in sorted(timeline.items()):
            starts = meta.get("starts", [])
            ends = meta.get("ends", [])
            spans = list(zip(starts, ends))
            
            print(f"Core {core}:")
            if not spans:
                print("  No residency regions detected")
            else:
                total_resident = sum(e - s for s, e in spans)
                max_t = meta.get("max_t", [0.0])[0]
                pct = (total_resident / max_t * 100) if max_t > 0 else 0
                
                print(f"  Regions: {len(spans)}")
                for i, (s, e) in enumerate(spans[:5]):
                    dur = e - s
                    print(f"    [{i}] t={s:.1f}..{e:.1f} us (duration: {dur:.1f} us)")
                if len(spans) > 5:
                    print(f"    ... and {len(spans) - 5} more")
                print(f"  Total resident: {total_resident:.1f} us ({pct:.1f}% of {max_t:.1f} us)")
        print()

    def export_baseline_csvs(self, out_dir: str) -> Tuple[str, str]:
        """
        Writes:
          out_dir/state_intervals.csv
          out_dir/residency_intervals.csv
        Returns (state_path, resid_path)
        
        ENHANCED: Includes marker detection diagnostics
        """
        print("\n" + "="*60)
        print("MARKER DETECTION DIAGNOSTICS")
        print("="*60)
        
        # Debug: Show trace sample
        self._debug_marker_detection(max_lines=20)
        
        # Check for marker instructions
        addi_found, li_found = self._check_for_marker_instructions(verbose=True)
        
        # Build timeline
        timeline = self._collect_core_timeline()
        
        # Validate residency timing
        residency_ok = self._validate_residency_timing(timeline)
        
        # Print summary
        self._print_residency_summary(timeline)
        
        # Strong warning if nothing detected
        if not residency_ok and not addi_found[0] and not addi_found[1] and not (li_found[0] and li_found[1]):
            print("\n" + "!"*60)
            print("CRITICAL: MARKER DETECTION FAILED")
            print("!"*60)
            print("\nNo residency markers detected. Checking possible causes:\n")
            print("1. Markers not in code:")
            print("   - SIT_RES_ON() and SIT_RES_OFF() may not be in workload")
            print()
            print("2. Markers compiled wrong:")
            print("   - Using volatile variable: compiles to memory store")
            print("   - NOT detected by adapter regex patterns")
            print("   FIX: Use inline asm instead:")
            print("   asm volatile(\"addi x0, x0, 101\");")
            print()
            print("Result: Using PC threshold fallback")
            print(f"        Residency will start at first PC >= {hex(self.cfg.resident_pc_ge)}")
            print()
        
        os.makedirs(out_dir, exist_ok=True)

        state_df = self.build_state_intervals()
        resid_df = self.build_residency_intervals()

        # DEBUG: Print state breakdown
        if len(state_df) > 0:
            total_time = (state_df['end_us'] - state_df['start_us']).sum()
            print("\n=== STATE BREAKDOWN ===")
            for state in state_df['state'].unique():
                state_time = (state_df[state_df['state'] == state]['end_us'] - 
                             state_df[state_df['state'] == state]['start_us']).sum()
                pct = (state_time / total_time) * 100 if total_time > 0 else 0
                print(f"{state}: {state_time:.2f} us ({pct:.1f}%)")
            print(f"Total: {total_time:.2f} us")

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
    ap.add_argument("--classification-mode", choices=["strict", "compute_biased"], default="strict")
    args = ap.parse_args()

    cfg = SpikeParseConfig(
        inst_us=args.inst_us,
        resident_pc_ge=args.resident_pc_ge,
        classification_mode=str(args.classification_mode),
    )
    ad = SpikePlatformAdapter(args.spike_trace, cfg=cfg)
    s_path, r_path = ad.export_baseline_csvs(args.out_dir)

    print("✓ wrote:", s_path)
    print("✓ wrote:", r_path)


if __name__ == "__main__":
    main()
