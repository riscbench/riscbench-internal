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
# Residency markers (encoded as addi x0,x0,imm). Spike may print as "li zero, imm".
RES_ON_INSN  = 0x06500013  # imm=101
RES_OFF_INSN = 0x06600013  # imm=102
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


class SpikePlatformAdapter:
    """
    Platform adapter (Spike) -> emits baseline CSVs that BaselineAdapter can read.

    Output CSV schemas are exactly what ingest_api.validate_* expects:
      state: start_us,end_us,core,state
      resid: start_us,end_us,core[,resident]
    
    WORMHOLE OPTIMIZED: Detects 'nop' instructions as IDLE cycles.
    Stalls are NOT auto-detected (Wormhole has scratchpad SRAM, not caches).
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
                if insn_val is not None and insn_val in (RES_ON_INSN, RES_OFF_INSN):
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

    def _collect_core_timeline(self) -> Dict[int, Dict[str, List]]:
        """
        Parse commit-log once and collect per-core timeline with state detection.

        Preferred residency detection is marker-driven (RESIDENCY_ON/RESIDENCY_OFF tokens
        emitted by _iter_events() via instruction-word match). If markers are absent for a
        core, fall back to PC-threshold residency using resident_pc_ge.

        Track idle vs active based on instruction type (nop/c.nop = idle).
        
        WORMHOLE ARCHITECTURE:
        - Scratchpad SRAM (108 MB), not caches
        - Stalls are NOT auto-detected from memory operations
        - Stalls must be modeled explicitly in workload code
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
        current_state_by_core: Dict[int, Optional[Tuple[float, str]]] = {}

        max_t_by_core: Dict[int, float] = {}
        in_residency_by_core: Dict[int, bool] = {}

        # Whether we have ever seen markers for this core
        markers_seen_by_core: Dict[int, bool] = {}

        for core, mnemonic, inst_count, raw_mnemonic, pc, insn_val in self._iter_events():
            t1 = float(inst_count) * inst_us
            max_t_by_core[core] = max(max_t_by_core.get(core, 0.0), t1)

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
            # Enhanced idle detection:
            # - Standard and compressed nops (nop, c.nop)
            # - Residency markers (treated as overhead, not work)
            # - li zero variants (Spike disassembly of addi x0, x0, imm)
            # - Control flow instructions (branches/jumps in idle loops)
            # - Fence/synchronization (waiting, not working)
            # - CSR reads that don't modify state (polling/waiting)
            # - Loads to x0 (memory polling)
            # - Moves between same register (compiler noise)
            
            is_idle = (
                # No-ops (all variants)
                mnemonic in ("nop", "c.nop", "residency_on", "residency_off") or
                (mnemonic.startswith("li") and "zero" in raw_mnemonic.lower()) or
                
                # Control flow (idle loop maintenance)
                mnemonic in ("j", "jal", "jalr", "beq", "bne", "blt", "bge", "bltu", "bgeu") or
                mnemonic in ("c.j", "c.jal", "c.jr", "c.jalr", "c.beqz", "c.bnez") or
                
                # Fence/synchronization (waiting, not working)
                mnemonic in ("fence", "fence.i", "fence.tso") or
                
                # CSR reads that don't modify state (polling/waiting)
                mnemonic.startswith("csrr") or
                
                # Loads that load but don't compute (memory polling)
                (mnemonic.startswith("l") and "zero" in raw_mnemonic.lower()) or
                
                # Moves between same register (compiler noise)
                ("mv" in mnemonic and len(raw_mnemonic.split(",")) >= 2 and 
                raw_mnemonic.split(",")[0].strip().split()[-1] == raw_mnemonic.split(",")[1].strip())
            )
            
            # ========================================================================
            # CRITICAL CHANGE FOR WORMHOLE ARCHITECTURE
            # ========================================================================
            # Wormhole uses scratchpad SRAM (108 MB), NOT hardware caches
            # 
            # Memory access characteristics:
            # - SRAM (scratchpad): ~2 cycle latency, software-managed placement
            # - GDDR6 (main memory): ~150 cycle latency, 288 GB/s bandwidth
            # 
            # Stalls cannot be inferred from instruction types because:
            # 1. Data placement is explicit (programmer controls SRAM vs GDDR6)
            # 2. Spike has no knowledge of memory hierarchy
            # 3. SRAM access is fast (no stall), GDDR6 access stalls
            # 4. Cannot determine from instruction alone which memory is accessed
            # 
            # Therefore: Stalls must be modeled explicitly in workload code via
            # stall_phase() function, controlled by --memory-overflow flag
            # ========================================================================
            
            is_stall = (
                        (mnemonic.startswith("l") and mnemonic not in ("li", "lui", "la")) or
                        (mnemonic.startswith("s") and mnemonic not in ("slli", "srli", "srai")) or
                        mnemonic.startswith("c.l") or mnemonic.startswith("c.s") or
                        mnemonic.startswith("lr") or mnemonic.startswith("sc") or mnemonic.startswith("amo"))            
            # State assignment
            if in_residency_by_core.get(core, False):
                if is_idle:
                    new_state = "idle"
                elif is_stall:
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
        Build state intervals from detected idle/active patterns within residency.
        Uses actual instruction-level state detection instead of just residency.
        """
        timeline = self._collect_core_timeline()

        rows: List[Dict] = []
        for core, meta in timeline.items():
            state_intervals = meta.get("state_intervals", [])
            max_t = float(meta["max_t"][0]) if meta["max_t"] else 0.0
            
            if state_intervals:
                # Use fine-grained state intervals
                for start_t, end_t, state in state_intervals:
                    if end_t > start_t:
                        rows.append({"start_us": start_t, "end_us": end_t, "core": core, "state": state})
                
                # Fill gaps outside residency with idle
                sorted_intervals = sorted(state_intervals, key=lambda x: x[0])
                t = 0.0
                for start_t, end_t, _ in sorted_intervals:
                    if start_t > t:
                        rows.append({"start_us": t, "end_us": start_t, "core": core, "state": "idle"})
                    t = max(t, end_t)
                if t < max_t:
                    rows.append({"start_us": t, "end_us": max_t, "core": core, "state": "idle"})
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
    args = ap.parse_args()

    cfg = SpikeParseConfig(inst_us=args.inst_us, resident_pc_ge=args.resident_pc_ge)
    ad = SpikePlatformAdapter(args.spike_trace, cfg=cfg)
    s_path, r_path = ad.export_baseline_csvs(args.out_dir)

    print("✓ wrote:", s_path)
    print("✓ wrote:", r_path)


if __name__ == "__main__":
    main()