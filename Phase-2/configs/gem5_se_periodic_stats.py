#!/usr/bin/env python3
"""
Phase-2 wrapper for gem5 SE configs that enables periodic stat dump/reset.

This script is executed by gem5 in place of se.py. It patches
common.Simulation.run() to schedule periodic m5 stats dumps, then forwards
all non-wrapper arguments to the real SE config script.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parse_wrapper_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--phase2-se-script", required=True, help="Path to real gem5 SE config (e.g. se.py)")
    ap.add_argument(
        "--phase2-stats-period-us",
        type=float,
        default=10.0,
        help="Periodic stats dump interval in microseconds",
    )
    return ap.parse_known_args(argv)


def main() -> None:
    args, passthrough = _parse_wrapper_args(sys.argv[1:])
    se_script = Path(args.phase2_se_script).expanduser().resolve()
    if not se_script.exists():
        raise SystemExit(f"SE config not found: {se_script}")

    # Ensure gem5 configs root is importable (for 'common' package).
    # .../configs/deprecated/example/se.py -> .../configs
    configs_root = se_script.parents[2]
    if str(configs_root) not in sys.path:
        sys.path.insert(0, str(configs_root))

    import m5
    from m5.stats import periodicStatDump
    from common import Simulation

    period_us = max(float(args.phase2_stats_period_us), 1e-6)
    # Use gem5 default tick frequency (1 THz => 1 us = 1e6 ticks).
    # This avoids requiring global frequency fix-up before config execution.
    period_ticks = int(round(period_us * 1_000_000.0))
    if period_ticks <= 0:
        period_ticks = 1

    orig_run = Simulation.run

    def run_with_periodic_dump(*run_args, **run_kwargs):
        periodicStatDump(period_ticks)
        return orig_run(*run_args, **run_kwargs)

    Simulation.run = run_with_periodic_dump

    # Forward remaining args to the original SE script. Execute with __main__
    # semantics while ensuring sys.path[0] points at se.py's directory.
    sys.argv = [str(se_script)] + passthrough
    old_path0 = sys.path[0] if sys.path else ""
    if sys.path:
        sys.path[0] = str(se_script.parent)
    else:
        sys.path.insert(0, str(se_script.parent))

    globals_dict = {"__name__": "__main__", "__file__": str(se_script)}
    with open(se_script, "r", encoding="utf-8") as f:
        code = compile(f.read(), str(se_script), "exec")
    try:
        exec(code, globals_dict, globals_dict)
    finally:
        if sys.path:
            sys.path[0] = old_path0


if __name__ in ("__main__", "__m5_main__"):
    main()
