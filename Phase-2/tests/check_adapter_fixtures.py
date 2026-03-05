#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from adapters.gem5_adapter import Gem5ParseConfig, Gem5PlatformAdapter
from adapters.qemu_adapter import QEMU_INSN_RE, QemuParseConfig, QemuPlatformAdapter
from adapters.spike_adapter import SpikeParseConfig, SpikePlatformAdapter


def compare_csv(actual: Path, expected: Path, label: str) -> None:
    adf = pd.read_csv(actual)
    edf = pd.read_csv(expected)
    try:
        pd.testing.assert_frame_equal(adf, edf, check_dtype=False, check_like=False, atol=0.0, rtol=0.0)
    except AssertionError as e:
        raise AssertionError(f"{label}: mismatch\n{e}") from e


def run_qemu_fixture(repo: Path) -> None:
    fixture_dir = repo / "tests" / "fixtures" / "qemu"
    trace = fixture_dir / "qemu.trace"
    exp_state = fixture_dir / "expected_state_intervals.csv"
    exp_resid = fixture_dir / "expected_residency_intervals.csv"

    if not trace.exists():
        raise AssertionError(f"qemu fixture trace missing: {trace}")

    with tempfile.TemporaryDirectory(prefix="qemu_fixture_") as td:
        out_dir = Path(td)
        ad = QemuPlatformAdapter(str(trace), cfg=QemuParseConfig(inst_us=1.0, resident_pc_ge=0x80000000))
        raw_lines = trace.read_text(encoding="utf-8").splitlines()
        dynamic_lines = sum(1 for ln in raw_lines if ln.startswith("Trace "))
        static_lines = sum(1 for ln in raw_lines if QEMU_INSN_RE.match(ln))
        events = list(ad._iter_events())
        if len(events) != dynamic_lines:
            raise AssertionError(
                f"qemu dynamic event mismatch: events={len(events)} trace_lines={dynamic_lines}"
            )
        if dynamic_lines <= static_lines:
            raise AssertionError(
                f"qemu fixture must contain more dynamic events than static insn lines: dynamic={dynamic_lines} static={static_lines}"
            )
        state_path, resid_path = ad.export_baseline_csvs(str(out_dir))
        compare_csv(Path(state_path), exp_state, "qemu state")
        compare_csv(Path(resid_path), exp_resid, "qemu residency")



def run_spike_fixture(repo: Path) -> None:
    fixture_dir = repo / "tests" / "fixtures" / "spike"
    trace = fixture_dir / "spike.trace"
    exp_state = fixture_dir / "expected_state_intervals.csv"
    exp_resid = fixture_dir / "expected_residency_intervals.csv"

    if not trace.exists():
        raise AssertionError(f"spike fixture trace missing: {trace}")

    with tempfile.TemporaryDirectory(prefix="spike_fixture_") as td:
        out_dir = Path(td)
        ad = SpikePlatformAdapter(str(trace), cfg=SpikeParseConfig(inst_us=1.0, resident_pc_ge=0x80000000))
        state_path, resid_path = ad.export_baseline_csvs(str(out_dir))
        compare_csv(Path(state_path), exp_state, "spike state")
        compare_csv(Path(resid_path), exp_resid, "spike residency")


def run_gem5_fixture(repo: Path) -> None:
    fixture_dir = repo / "tests" / "fixtures" / "gem5"
    trace = fixture_dir / "gem5.trace"
    exp_state = fixture_dir / "expected_state_intervals.csv"
    exp_resid = fixture_dir / "expected_residency_intervals.csv"

    if not trace.exists():
        raise AssertionError(f"gem5 fixture trace missing: {trace}")

    with tempfile.TemporaryDirectory(prefix="gem5_fixture_") as td:
        out_dir = Path(td)
        ad = Gem5PlatformAdapter(str(trace), cfg=Gem5ParseConfig(inst_us=1.0, resident_pc_ge=0x80000000))
        state_path, resid_path = ad.export_baseline_csvs(str(out_dir))
        compare_csv(Path(state_path), exp_state, "gem5 state")
        compare_csv(Path(resid_path), exp_resid, "gem5 residency")



def main() -> int:
    ap = argparse.ArgumentParser(description="Adapter parser stability checks against raw fixture snapshots")
    ap.add_argument("--fixtures", nargs="+", default=["qemu", "spike", "gem5"], choices=["qemu", "spike", "gem5"])
    args = ap.parse_args()

    repo = ROOT_DIR
    selected = list(dict.fromkeys(args.fixtures))

    for fixture in selected:
        if fixture == "qemu":
            run_qemu_fixture(repo)
            print("PASS fixture: qemu")
        elif fixture == "spike":
            run_spike_fixture(repo)
            print("PASS fixture: spike")
        elif fixture == "gem5":
            run_gem5_fixture(repo)
            print("PASS fixture: gem5")

    print("PASS adapter fixture checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
