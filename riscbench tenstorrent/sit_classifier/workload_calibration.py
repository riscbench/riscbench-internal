from __future__ import annotations

import re
from pathlib import Path

AUTO_OPS_PER_ZONE: dict[str, float] = {
    "vecadd": 1024.0,
    "eltwise_binary": 1024.0,
    "eltwise_binary_mul": 1024.0,
    "eltwise_sfpu": 1024.0,
    "custom_sfpi_add": 1024.0,
    "custom_sfpi_smoothstep": 6144.0,
    "sfpu_chain": 3072.0,
    "matmul": 65536.0,
    "matmul_single": 65536.0,
    "matmul_multicore": 65536.0,
    "matmul_multi": 65536.0,
    "matmul_shared": 65536.0,
}

CALIBRATION_WORKLOAD_ALIASES: dict[str, str] = {
    "tt_vecadd": "vecadd",
    "tt_eltwise_binary": "eltwise_binary",
    "tt_eltwise_sfpu": "eltwise_sfpu",
    "tt_custom_sfpi_add": "custom_sfpi_add",
    "tt_custom_sfpi_smoothstep": "custom_sfpi_smoothstep",
    "tt_sfpu_chain": "sfpu_chain",
    "tt_matmul_single": "matmul_single",
    "tt_matmul_multi": "matmul_multi",
}

TT_SIZE_ACTIVE_BOOST: dict[str, int] = {
    "tt_tile": 1,
    "tt_1tile": 1,
    "tt_4tile": 4,
    "tt_32tile": 32,
    "tt_64tile": 64,
    "tt_128tile": 128,
    "tt_256tile": 256,
    "tt_1024tile": 1024,
}

HEADER_FREQ_RE = re.compile(r"CHIP_FREQ\[MHz\]:\s*(\d+)")
TT_TILE_SIZE_RE = re.compile(r"^(?:tt_)?(\d+)tile$")
TT_MATMUL_SIZE_RE = re.compile(r"^(?:tt_)?m(\d+)_n(\d+)_k(\d+)$")


def canonicalize_calibration_workload(workload: str) -> str:
    raw = str(workload or "").strip()
    return CALIBRATION_WORKLOAD_ALIASES.get(raw, raw)


def resolve_auto_ops_per_zone(workload: str) -> float | None:
    canonical = canonicalize_calibration_workload(workload)
    return AUTO_OPS_PER_ZONE.get(canonical)


def resolve_matmul_total_invocations(size: str) -> int | None:
    """Return tiles_M × tiles_N × tiles_K — total THROUGHPUT_SECTION calls for a matmul."""
    raw = str(size or "").strip().lower()
    match = TT_MATMUL_SIZE_RE.match(raw)
    if not match:
        return None
    tile = 32
    tiles_m = max(1, int(match.group(1)) // tile)
    tiles_n = max(1, int(match.group(2)) // tile)
    tiles_k = max(1, int(match.group(3)) // tile)
    return tiles_m * tiles_n * tiles_k


def resolve_size_active_boost(size: str) -> int | None:
    raw = str(size or "").strip().lower()
    if not raw:
        return None
    if raw in TT_SIZE_ACTIVE_BOOST:
        return TT_SIZE_ACTIVE_BOOST[raw]
    match = TT_TILE_SIZE_RE.match(raw)
    if match:
        return int(match.group(1))
    n = resolve_matmul_total_invocations(raw)
    if n is not None:
        return n
    return None


def read_tt_profile_chip_freq_mhz(profile_csv: str | Path | None) -> float | None:
    if profile_csv is None:
        return None
    path = Path(profile_csv).expanduser()
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(4):
                line = handle.readline()
                if not line:
                    break
                match = HEADER_FREQ_RE.search(line)
                if match:
                    return float(match.group(1))
    except OSError:
        return None
    return None
