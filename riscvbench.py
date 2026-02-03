#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

# ---- workload generators (same as earlier, minimal set) ----
WORKLOADS = {"alu", "branch", "memory", "hello"}
SIZES = {"tiny", "small", "med", "large"}

SIZE_PRESETS = {
    "tiny":  {"ITER": 2_000,     "DIM": 64},
    "small": {"ITER": 10_000,    "DIM": 128},
    "med":   {"ITER": 200_000,   "DIM": 256},
    "large": {"ITER": 2_000_000, "DIM": 512},
}

SRC = {
    "alu": r"""
#include <stdint.h>
int main() {
  volatile uint64_t x = 1;
  for (uint64_t i = 1; i < ITER; i++) x = x * 3 + i;
  return (int)x;
}
""",
    "branch": r"""
int main() {
  volatile int sum = 0;
  for (int i = 0; i < ITER; i++) {
    if (i & 1) sum += i;
    else sum -= i;
  }
  return sum;
}
""",
    "memory": r"""
#define N DIM
static int A[N][N];
int main() {
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) A[i][j] = i + j;

  volatile int sum = 0;
  for (int j = 0; j < N; j++)
    for (int i = 0; i < N; i++) sum += A[i][j];
  return sum;
}
""",
    "hello": r"""
#include <stdio.h>
int main() {
  for (int i = 0; i < 3; i++) printf("Hello from RISC-V %d\n", i);
  return 0;
}
""",
}

def sh(cmd: list[str] | str, cwd: Path | None = None) -> None:
    if isinstance(cmd, str):
        p = subprocess.run(cmd, cwd=cwd, shell=True)
    else:
        p = subprocess.run(cmd, cwd=cwd)
    if p.returncode != 0:
        raise SystemExit(f"Command failed: {cmd}")

def ensure_tool(name: str):
    if shutil.which(name) is None:
        raise SystemExit(f"Tool not found in PATH: {name}")

def write_workload(build_dir: Path, workload: str, size: str) -> Path:
    preset = SIZE_PRESETS[size]
    code = SRC[workload].replace("ITER", str(preset["ITER"])).replace("DIM", str(preset["DIM"]))
    cpath = build_dir / f"{workload}.c"
    cpath.write_text(code)
    return cpath

def main():
    ap = argparse.ArgumentParser(prog="riscvbench")
    ap.add_argument("--target", required=True, choices=["spike"])
    ap.add_argument("--workload", required=True, choices=sorted(WORKLOADS))
    ap.add_argument("--workload_size", required=True, choices=sorted(SIZES))
    ap.add_argument("--time_us", required=True, type=float)

    # Spike plumbing
    ap.add_argument("--isa", default="RV64IMACV")
    ap.add_argument("--pk", default=str(Path.home() / "RISCV" / "riscv-pk" / "build" / "pk"))
    ap.add_argument("--inst_us", type=float, default=1.0)
    ap.add_argument("--resident_pc_ge", default="0x80000000")
    ap.add_argument("--trace_lines_max", type=int, default=200000)

    args = ap.parse_args()

    ensure_tool("spike")
    ensure_tool("sit-engine")
    ensure_tool("riscv64-unknown-elf-gcc")

    repo = Path.cwd()
    pk = Path(args.pk)
    if not pk.exists():
        raise SystemExit(f"pk not found: {pk}")

    adapter_py = repo / "adapters" / "spike_adapter.py"
    if not adapter_py.exists():
        raise SystemExit(f"missing adapter: {adapter_py}")

    # Run directory contract
    run_dir = repo / "runs" / args.target / args.workload / args.workload_size
    build_dir = run_dir / "build"
    traces_dir = run_dir / "traces"
    inputs_dir = run_dir / "inputs"

    build_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)

    # 1) build workload
    cpath = write_workload(build_dir, args.workload, args.workload_size)
    binpath = build_dir / args.workload
    sh(["riscv64-unknown-elf-gcc", "-O2", "-static", str(cpath), "-o", str(binpath)], cwd=build_dir)

    # 2) run spike -> trace
    trace_path = traces_dir / "spike.trace"
    if args.trace_lines_max > 0:
        sh(
            f"spike -l --isa={args.isa} {pk} {binpath} 2>&1 | head -n {args.trace_lines_max} > {trace_path}",
            cwd=run_dir,
        )
    else:
        sh(f"spike -l --isa={args.isa} {pk} {binpath} 2> {trace_path}", cwd=run_dir)

    if not trace_path.exists() or trace_path.stat().st_size == 0:
        raise SystemExit(f"Spike trace empty: {trace_path}")

    # 3) platform adaptor: trace -> baseline CSVs
    sh([
        "python3", str(adapter_py),
        "--spike-trace", str(trace_path),
        "--out-dir", str(inputs_dir),
        "--inst-us", str(args.inst_us),
        "--resident-pc-ge", str(args.resident_pc_ge),
    ], cwd=repo)

    state_csv = inputs_dir / "state_intervals.csv"
    resid_csv = inputs_dir / "residency_intervals.csv"
    if not state_csv.exists():
        raise SystemExit(f"Missing: {state_csv}")
    if not resid_csv.exists():
        raise SystemExit(f"Missing: {resid_csv}")

    # 4) sit-engine pipeline (your phase1 CLI)
    sh(["sit-engine", "ingest",
        "--trace", str(state_csv),
        "--format", "baseline",
        "--out", str(run_dir)], cwd=repo)

    sh(["sit-engine", "classify",
        "--in", str(run_dir),
        "--window-us", str(args.time_us),
        "--residency", str(resid_csv)], cwd=repo)

    sh(["sit-engine", "export",
        "--in", str(run_dir),
        "--schema", "v1",
        "--format", "csv"], cwd=repo)

    print("✓ done")
    print(f"run_dir: {run_dir}")
    print(f"summary: {run_dir / 'summary.json'}")
    print(f"windows: {run_dir / 'windows.csv'}")
    print(f"export:  {run_dir / 'export'}")

if __name__ == "__main__":
    main()
