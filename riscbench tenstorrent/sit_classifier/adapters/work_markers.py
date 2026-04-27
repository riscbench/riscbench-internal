from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

# Reserve a positive immediate range that does not overlap the existing
# residency/stall/idle markers (101-106). We use addi x0, x0, imm so the
# instruction survives across spike/qemu/gem5 traces.
WORK_MARKER_BASE_IMM = 512
WORK_MARKER_MAX_UNITS = 1023
WORK_MARKER_MAX_IMM = WORK_MARKER_BASE_IMM + WORK_MARKER_MAX_UNITS

StateInterval = Tuple[float, float, str]
WorkMarker = Tuple[float, float]


def encode_work_units_to_imm(units: int) -> int:
    clamped = max(1, min(int(units), WORK_MARKER_MAX_UNITS))
    return WORK_MARKER_BASE_IMM + clamped


def decode_work_units_from_imm(imm: Optional[int]) -> Optional[float]:
    if imm is None:
        return None
    if WORK_MARKER_BASE_IMM <= int(imm) <= WORK_MARKER_MAX_IMM:
        return float(int(imm) - WORK_MARKER_BASE_IMM)
    return None


def extract_addi_zero_imm(insn_val: Optional[int]) -> Optional[int]:
    if insn_val is None:
        return None
    # addi x0, x0, imm => rd=x0, rs1=x0, funct3=0, opcode=0x13
    if (int(insn_val) & 0x000FFFFF) != 0x00000013:
        return None
    imm = (int(insn_val) >> 20) & 0xFFF
    if imm & 0x800:
        imm -= 0x1000
    return imm


def decode_work_units(insn_val: Optional[int] = None, marker_imm: Optional[int] = None) -> Optional[float]:
    units = decode_work_units_from_imm(marker_imm)
    if units is not None:
        return units
    return decode_work_units_from_imm(extract_addi_zero_imm(insn_val))


def allocate_work_done(
    state_intervals: Sequence[StateInterval],
    work_markers: Iterable[WorkMarker],
) -> List[float]:
    intervals = list(state_intervals)
    allocations = [0.0] * len(intervals)
    total_work = sum(float(units) for _t, units in work_markers if float(units) > 0.0)
    if total_work <= 0.0 or not intervals:
        return allocations

    active_indices = [
        idx
        for idx, (start_us, end_us, state) in enumerate(intervals)
        if state == "active" and float(end_us) > float(start_us)
    ]
    if not active_indices:
        return allocations

    total_active_us = sum(
        float(intervals[idx][1]) - float(intervals[idx][0])
        for idx in active_indices
    )
    if total_active_us <= 0.0:
        allocations[active_indices[-1]] = total_work
        return allocations

    assigned = 0.0
    for idx in active_indices[:-1]:
        start_us, end_us, _state = intervals[idx]
        duration = max(0.0, float(end_us) - float(start_us))
        value = total_work * (duration / total_active_us)
        allocations[idx] = value
        assigned += value

    allocations[active_indices[-1]] = max(0.0, total_work - assigned)
    return allocations
