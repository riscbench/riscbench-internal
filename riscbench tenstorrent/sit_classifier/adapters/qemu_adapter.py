from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import os
import re
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sit_classifier.ingest_api import validate_resid_df, validate_state_df
from sit_classifier.adapters.work_markers import allocate_work_done, decode_work_units

# Marker encodings emitted by riscvbench inline asm markers.
RES_ON_INSN = 0x06500013
RES_OFF_INSN = 0x06600013
STALL_ON_INSN = 0x06700013
STALL_OFF_INSN = 0x06800013
IDLE_ON_INSN = 0x06900013
IDLE_OFF_INSN = 0x06A00013

# qemu-riscv64 user-mode disassembly line, e.g.:
#   0x00000040000007b8:  06500013          addi                    zero,zero,101
QEMU_INSN_RE = re.compile(
    r"^\s*0x(?P<pc>[0-9a-fA-F]{1,16}):\s+(?P<insn>[0-9a-fA-F]{4,8})(?:\s+(?P<asm>.*))?$"
)


@dataclass
class QemuParseConfig:
    inst_us: float = 1.0
    resident_pc_ge: int = 0x80000000
    classification_mode: str = "strict"


class QemuPlatformAdapter:
    """
    Parse qemu `-d in_asm,exec,nochain` logs and emit normalized intervals.

    Time base choice (intentional):
    - We advance timeline on dynamic `Trace ...` execution lines, not static
      `0x...: <insn>` disassembly lines.
    - In qemu logs, disassembly is emitted per translated block (TB) definition,
      while `Trace` lines represent runtime execution events and can repeat many
      times in loops. Using `Trace` lines prevents under-counting runtime.

    State classification policy:
    - residency is marker-driven when present, else falls back to resident_pc_ge
    - explicit IDLE_* / STALL_* markers are authoritative
    - otherwise, control-flow / nop / fence / CSR-like instructions count as idle
    - memory / atomic style instructions count as stall
    - remaining instructions inside residency count as active
    """

    def __init__(self, qemu_trace_path: str, cfg: Optional[QemuParseConfig] = None):
        self.qemu_trace_path = qemu_trace_path
        self.cfg = cfg or QemuParseConfig()

    @staticmethod
    def _parse_trace_pc(line: str) -> Optional[int]:
        if not line.startswith("Trace "):
            return None
        lb = line.find("[")
        rb = line.find("]", lb + 1) if lb >= 0 else -1
        if lb < 0 or rb < 0:
            return None
        fields = [x.strip() for x in line[lb + 1 : rb].split("/")]
        if len(fields) < 2:
            return None
        tok = fields[1]
        if tok.lower().startswith("0x"):
            tok = tok[2:]
        if not tok or any(ch not in "0123456789abcdefABCDEF" for ch in tok):
            return None
        try:
            return int(tok, 16)
        except ValueError:
            return None

    def _summarize_tb(self, tb_insns: List[Dict[str, Any]]) -> Dict[str, Any]:
        marker_insn: Optional[int] = None
        has_active = False
        has_stall = False
        work_units = 0.0

        for ins in tb_insns:
            insn_val = ins.get("insn_val")
            norm = str(ins.get("norm", ""))
            work_delta = decode_work_units(insn_val=insn_val)
            if work_delta:
                work_units += float(work_delta)
                continue
            if insn_val in (
                RES_ON_INSN,
                RES_OFF_INSN,
                STALL_ON_INSN,
                STALL_OFF_INSN,
                IDLE_ON_INSN,
                IDLE_OFF_INSN,
            ):
                if marker_insn is None:
                    marker_insn = int(insn_val)
                continue
            if self._is_idle(norm):
                continue
            if self._is_stall(norm):
                has_stall = True
            else:
                has_active = True

        # If a TB mixes compute+memory ops, keep it active by default; pure memory
        # TBs are treated as stall-like.
        if has_stall and not has_active:
            class_norm = "lw"
            class_raw = "TB_STALL"
        elif has_active:
            class_norm = "add"
            class_raw = "TB_ACTIVE"
        else:
            class_norm = "nop"
            class_raw = "TB_IDLE"

        return {
            "marker_insn": marker_insn,
            "class_norm": class_norm,
            "class_raw": class_raw,
            "work_units": work_units,
        }

    def _iter_events(self) -> Iterable[Tuple[int, str, int, str, Optional[int], Optional[int], float]]:
        event_count = 0
        tb_map: Dict[int, Dict[str, Any]] = {}
        current_tb_pc: Optional[int] = None
        current_tb_insns: List[Dict[str, Any]] = []

        with open(self.qemu_trace_path, "r", errors="ignore") as f:
            for line in f:
                if line.startswith("IN:"):
                    current_tb_pc = None
                    current_tb_insns = []
                    continue

                m = QEMU_INSN_RE.match(line)
                if m:
                    try:
                        pc = int(m.group("pc"), 16)
                    except ValueError:
                        pc = None
                    try:
                        insn_val = int(m.group("insn"), 16)
                    except ValueError:
                        insn_val = None

                    raw_mnemonic = (m.group("asm") or "").strip()
                    norm_mnemonic = raw_mnemonic.split()[0].lower() if raw_mnemonic else ""

                    if current_tb_pc is None and pc is not None:
                        current_tb_pc = pc
                    current_tb_insns.append(
                        {
                            "pc": pc,
                            "insn_val": insn_val,
                            "norm": norm_mnemonic,
                            "raw": raw_mnemonic,
                        }
                    )
                    continue

                trace_pc = self._parse_trace_pc(line)
                if trace_pc is None:
                    continue

                if current_tb_pc is not None and current_tb_insns and current_tb_pc not in tb_map:
                    tb_map[current_tb_pc] = self._summarize_tb(current_tb_insns)

                tb = tb_map.get(trace_pc, None)
                marker_insn = tb.get("marker_insn") if tb is not None else None
                work_units = float(tb.get("work_units", 0.0)) if tb is not None else 0.0
                if marker_insn == RES_ON_INSN:
                    raw_mnemonic = "RESIDENCY_ON"
                    norm_mnemonic = "residency_on"
                elif marker_insn == RES_OFF_INSN:
                    raw_mnemonic = "RESIDENCY_OFF"
                    norm_mnemonic = "residency_off"
                elif marker_insn == STALL_ON_INSN:
                    raw_mnemonic = "STALL_ON"
                    norm_mnemonic = "stall_on"
                elif marker_insn == STALL_OFF_INSN:
                    raw_mnemonic = "STALL_OFF"
                    norm_mnemonic = "stall_off"
                elif marker_insn == IDLE_ON_INSN:
                    raw_mnemonic = "IDLE_ON"
                    norm_mnemonic = "idle_on"
                elif marker_insn == IDLE_OFF_INSN:
                    raw_mnemonic = "IDLE_OFF"
                    norm_mnemonic = "idle_off"
                elif tb is not None:
                    raw_mnemonic = str(tb["class_raw"])
                    norm_mnemonic = str(tb["class_norm"])
                else:
                    raw_mnemonic = "TB_ACTIVE"
                    norm_mnemonic = "add"

                # Dynamic execution event counter (TB execution count).
                event_count += 1
                yield 0, norm_mnemonic, event_count, raw_mnemonic, trace_pc, marker_insn, work_units

    @staticmethod
    def _is_idle(norm_mnemonic: str) -> bool:
        n = norm_mnemonic.replace(".", "_")
        return (
            n in ("nop", "c_nop", "residency_on", "residency_off", "stall_on", "stall_off", "idle_on", "idle_off")
            or n in (
                "j",
                "jal",
                "jalr",
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
            or n.startswith("amo")
            or n.startswith("lr")
            or n.startswith("sc")
        )

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

        for core, mnemonic, inst_count, _raw_mnemonic, pc, insn_val, work_units in self._iter_events():
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

            if work_units > 0.0 and (was_in_residency or in_residency_by_core.get(core, False)):
                if not in_residency_by_core.get(core, False):
                    current = current_state_by_core.get(core)
                    if current is not None:
                        start_t, curr_state = current
                        state_intervals_by_core.setdefault(core, []).append((start_t, t1, curr_state))
                        current_state_by_core[core] = None
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


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--qemu-trace", required=True, help="QEMU disassembly trace (`-d in_asm,exec,nochain`) ")
    ap.add_argument("--out-dir", required=True, help="Directory to write baseline CSVs")
    ap.add_argument("--inst-us", type=float, default=1.0, help="Time per instruction (us)")
    ap.add_argument(
        "--resident-pc-ge",
        type=lambda x: int(x, 0),
        default=0x80000000,
        help="Fallback residency PC threshold",
    )
    ap.add_argument("--classification-mode", choices=["strict", "compute_biased"], default="strict")
    args = ap.parse_args()

    cfg = QemuParseConfig(
        inst_us=args.inst_us,
        resident_pc_ge=args.resident_pc_ge,
        classification_mode=str(args.classification_mode),
    )
    ad = QemuPlatformAdapter(args.qemu_trace, cfg=cfg)
    s_path, r_path = ad.export_baseline_csvs(args.out_dir)

    print("✓ wrote:", s_path)
    print("✓ wrote:", r_path)


if __name__ == "__main__":
    main()
