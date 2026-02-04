#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---- workload generators (same as earlier, minimal set) ----
WORKLOADS_SIMPLE = {"alu", "branch", "memory", "hello", "memread", "memwrite", "memcpy"}
WORKLOADS_SPIKE = WORKLOADS_SIMPLE | {"matmul", "matmul_multicore"}
WORKLOADS_CPU = WORKLOADS_SIMPLE | {"matmul", "matmul_multicore"}
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
    "matmul": r"""
#define N DIM
static int A[N][N];
static int B[N][N];
static int C[N][N];
int main() {
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) {
      A[i][j] = i + j;
      B[i][j] = i - j;
      C[i][j] = 0;
    }

  for (int i = 0; i < N; i++)
    for (int k = 0; k < N; k++)
      for (int j = 0; j < N; j++)
        C[i][j] += A[i][k] * B[k][j];

  return C[N - 1][N - 1];
}
""",
    "memread": r"""
#define N DIM
static int A[N];
int main() {
  for (int i = 0; i < N; i++) A[i] = i;
  volatile int sum = 0;
  for (int i = 0; i < ITER; i++) {
    sum += A[i % N];
  }
  return sum;
}
""",
    "memwrite": r"""
#define N DIM
static int A[N];
int main() {
  for (int i = 0; i < N; i++) A[i] = 0;
  for (int i = 0; i < ITER; i++) {
    A[i % N] = i;
  }
  return A[N - 1];
}
""",
    "memcpy": r"""
#define N DIM
static int A[N];
static int B[N];
int main() {
  for (int i = 0; i < N; i++) A[i] = i;
  for (int i = 0; i < ITER; i++) {
    B[i % N] = A[i % N];
  }
  return B[N - 1];
}
""",
}

def sh(cmd: list[str] | str, cwd: Path | None = None, env: dict | None = None) -> None:
    if isinstance(cmd, str):
        p = subprocess.run(cmd, cwd=cwd, shell=True, env=env)
    else:
        p = subprocess.run(cmd, cwd=cwd, env=env)
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

def find_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "cli.py").exists() and (candidate / "adapters").is_dir():
            return candidate
    module_dir = Path(__file__).resolve().parent
    if (module_dir / "cli.py").exists() and (module_dir / "adapters").is_dir():
        return module_dir
    return cwd


def main():
    ap = argparse.ArgumentParser(
        prog="riscvbench",
        epilog=(
            "Workloads by target: spike="
            + ",".join(sorted(WORKLOADS_SPIKE))
            + " cpu="
            + ",".join(sorted(WORKLOADS_CPU))
        ),
    )
    ap.add_argument("--target", required=True, choices=["spike", "cpu"])
    ap.add_argument("--workload", required=True, choices=sorted(WORKLOADS_CPU | WORKLOADS_SPIKE))
    ap.add_argument("--workload_size", required=True, choices=sorted(SIZES))
    ap.add_argument("--time_us", required=True, type=float)

    # Matmul/workload-specific args (for --target cpu)
    ap.add_argument("--tile-elems", type=int, default=1024)
    ap.add_argument("--tiles", type=int, default=50000)
    ap.add_argument("--compute-threads", type=int, default=1, help="Number of parallel compute threads (for matmul_multicore)")
    ap.add_argument("--cores", type=int, default=None, help="Alias for --compute-threads (number of cores for matmul_multicore)")
    ap.add_argument("--in-depth", type=int, default=2)
    ap.add_argument("--out-depth", type=int, default=2)
    ap.add_argument("--reader-sleep-ns", type=int, default=0)
    ap.add_argument("--writer-sleep-ns", type=int, default=0)
    ap.add_argument("--underflow", action="store_true", help="Enable reader slowdown to cause underflow")
    ap.add_argument("--overflow", action="store_true", help="Enable writer slowdown to cause overflow")

    # Spike plumbing
    ap.add_argument("--isa", default="RV64IMACV")
    ap.add_argument("--pk", default=str(Path.home() / "RISCV" / "riscv-pk" / "build" / "pk"))
    ap.add_argument("--inst_us", type=float, default=1.0)
    ap.add_argument("--resident_pc_ge", default="0x80000000")
    ap.add_argument("--trace_lines_max", type=int, default=200000)
    ap.add_argument("--events-max", type=int, default=None, help="Max events to parse for both spike and cpu (0 for no limit)")

    args = ap.parse_args()
    if args.cores is not None and args.compute_threads != 1 and args.cores != args.compute_threads:
        raise SystemExit("Use either --cores or --compute-threads (not both with different values)")
    compute_threads = args.cores if args.cores is not None else args.compute_threads
    events_max = args.events_max
    if events_max is None:
        events_max = args.trace_lines_max

    # no global requirement for 'sit-engine' — we call local Phase-1 CLI instead

    repo = find_repo_root()

    adapter_spike = repo / "adapters" / "spike_adapter.py"
    adapter_cpu = repo / "adapters" / "cpu_adapter.py"

    # Run directory contract
    run_dir = repo / "runs" / args.target / args.workload / args.workload_size
    build_dir = run_dir / "build"
    traces_dir = run_dir / "traces"
    inputs_dir = run_dir / "inputs"

    build_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)

    # Target-specific handling
    if args.target == "spike":
        ensure_tool("spike")
        ensure_tool("riscv64-unknown-elf-gcc")

        pk = Path(args.pk)
        if not pk.exists():
            raise SystemExit(f"pk not found: {pk}")

        adapter_py = adapter_spike
        if not adapter_py.exists():
            raise SystemExit(f"missing adapter: {adapter_py}")

        if args.workload not in WORKLOADS_SPIKE:
            raise SystemExit(f"spike target does not support workload: {args.workload}")

        # 1) build workload
        if args.workload == "matmul_multicore":
            workload_src = repo / "matmul_multicore.c"
            if not workload_src.exists():
                raise SystemExit(f"matmul_multicore.c not found: {workload_src}")
            binpath = build_dir / "matmul_multicore"
            sh(
                ["riscv64-unknown-elf-gcc", "-O2", "-static", "-pthread", str(workload_src), "-o", str(binpath)],
                cwd=build_dir,
            )
        else:
            cpath = write_workload(build_dir, args.workload, args.workload_size)
            binpath = build_dir / args.workload
            sh(["riscv64-unknown-elf-gcc", "-O2", "-static", str(cpath), "-o", str(binpath)], cwd=build_dir)

        # 2) run spike -> trace
        trace_path = traces_dir / "spike.trace"
        if events_max > 0:
            sh(
                f"spike -l --isa={args.isa} {pk} {binpath} 2>&1 | head -n {events_max} > {trace_path}",
                cwd=run_dir,
            )
        else:
            sh(f"spike -l --isa={args.isa} {pk} {binpath} 2> {trace_path}", cwd=run_dir)

        if not trace_path.exists() or trace_path.stat().st_size == 0:
            raise SystemExit(f"Spike trace empty: {trace_path}")

        # 3) platform adaptor: spike trace -> baseline CSVs
        adapter_env = dict(os.environ)
        adapter_env["PYTHONPATH"] = f"{repo}:{adapter_env.get('PYTHONPATH', '')}".rstrip(":")
        sh(
            [
                sys.executable, str(adapter_py),
                "--spike-trace", str(trace_path),
                "--out-dir", str(inputs_dir),
                "--inst-us", str(args.inst_us),
                "--resident-pc-ge", str(args.resident_pc_ge),
            ],
            cwd=repo,
            env=adapter_env,
        )

        state_csv = inputs_dir / "state_intervals.csv"
        resid_csv = inputs_dir / "residency_intervals.csv"
        if not state_csv.exists():
            raise SystemExit(f"Missing: {state_csv}")
        if not resid_csv.exists():
            raise SystemExit(f"Missing: {resid_csv}")

    elif args.target == "cpu":
        # Local matmul/matmul_multicore workload
        if args.workload in {"matmul", "matmul_multicore"}:
            adapter_py = adapter_cpu
            if not adapter_py.exists():
                raise SystemExit(f"missing adapter: {adapter_py}")

            # Determine matmul parameters
            reader_sleep = args.reader_sleep_ns
            writer_sleep = args.writer_sleep_ns
            if args.underflow:
                reader_sleep = max(reader_sleep, 2000)
            if args.overflow:
                writer_sleep = max(writer_sleep, 5000)

            # 1) Select and build workload
            if args.workload == "matmul_multicore":
                src_name = "matmul_multicore.c"
                bin_name = "matmul_multicore"
            else:
                src_name = "matmul.c"
                bin_name = "matmul"
            
            workload_src = repo / src_name
            if not workload_src.exists():
                raise SystemExit(f"{src_name} not found: {workload_src}")
            
            binpath = build_dir / bin_name
            sh(["gcc", "-O2", "-g", "-pthread", str(workload_src), "-o", str(binpath)], cwd=repo)

            # 2) run matmul/matmul_multicore -> raw trace
            trace_path = traces_dir / f"{bin_name}.trace"
            # pick sensible tile counts for workload sizes unless user provided explicit tiles
            size_tiles = {"tiny": 10, "small": 100, "med": 1000, "large": 5000}
            tiles_count = args.tiles if args.tiles != 50000 else size_tiles.get(args.workload_size, args.tiles)

            # Scale ring depths for multicore variant
            in_depth_final = args.in_depth
            out_depth_final = args.out_depth
            if args.workload == "matmul_multicore":
                in_depth_final = max(args.in_depth, compute_threads)
                out_depth_final = max(args.out_depth, compute_threads)

            run_cmd = [str(binpath),
                   "--tile-elems", str(args.tile_elems),
                   "--tiles", str(tiles_count),
                   "--in-depth", str(in_depth_final),
                   "--out-depth", str(out_depth_final),
                   "--trace", str(trace_path)]
            
            # Add compute-threads for multicore variant
            if args.workload == "matmul_multicore":
                run_cmd += ["--compute-threads", str(compute_threads)]
            
            if reader_sleep:
                run_cmd += ["--reader-sleep-ns", str(reader_sleep)]
            if writer_sleep:
                run_cmd += ["--writer-sleep-ns", str(writer_sleep)]

            sh(run_cmd, cwd=repo)

            if not trace_path.exists() or trace_path.stat().st_size == 0:
                raise SystemExit(f"Matmul trace empty: {trace_path}")

            # 3) ingest raw trace via Phase-1 CLI (format cpu) into run_dir
            ingest_cmd = [
                sys.executable, str(Path(__file__).resolve().parent / "cli.py"),
                "ingest", "--trace", str(trace_path), "--format", "cpu", "--out", str(run_dir),
            ]
            if events_max is not None:
                ingest_cmd += ["--events-max", str(events_max)]
            sh(ingest_cmd, cwd=repo)

            # move normalized outputs into inputs_dir expected layout
            normalized_trace = run_dir / "trace.csv"
            normalized_resid = run_dir / "residency.csv"
            if not normalized_trace.exists():
                raise SystemExit(f"Normalized trace not found: {normalized_trace}")
            inputs_dir.mkdir(parents=True, exist_ok=True)
            (inputs_dir / "state_intervals.csv").write_bytes(normalized_trace.read_bytes())
            if normalized_resid.exists():
                (inputs_dir / "residency_intervals.csv").write_bytes(normalized_resid.read_bytes())
            else:
                # create empty residency to satisfy downstream (engine will handle missing)
                (inputs_dir / "residency_intervals.csv").write_text("start_us,end_us,core,resident\n")
            # set state/resid paths for downstream
            state_csv = inputs_dir / "state_intervals.csv"
            resid_csv = inputs_dir / "residency_intervals.csv"
        elif args.workload in WORKLOADS_SIMPLE:
            # For other CPU workloads, run a simple binary and emit a single active interval.
            cpath = write_workload(build_dir, args.workload, args.workload_size)
            binpath = build_dir / args.workload
            sh(["gcc", "-O2", "-g", str(cpath), "-o", str(binpath)], cwd=build_dir)

            start = time.perf_counter()
            sh([str(binpath)], cwd=build_dir)
            end = time.perf_counter()

            duration_us = max((end - start) * 1e6, 1.0)
            inputs_dir.mkdir(parents=True, exist_ok=True)
            state_csv = inputs_dir / "state_intervals.csv"
            resid_csv = inputs_dir / "residency_intervals.csv"
            state_csv.write_text("start_us,end_us,core,state\n0.0,{:.3f},0,active\n".format(duration_us))
            resid_csv.write_text("start_us,end_us,core,resident\n0.0,{:.3f},0,1\n".format(duration_us))
        else:
            raise SystemExit(f"cpu target does not support workload: {args.workload}")

    # 4) Use Phase-1 CLI for ingest/classify/export (no sit-engine in PATH required)
    cli_spec = importlib.util.find_spec("cli")
    if cli_spec is not None and cli_spec.origin is not None:
        cli_py = Path(cli_spec.origin)
    else:
        cli_py = Path(__file__).resolve().parent / "cli.py"
        if not cli_py.exists():
            repo_cli = repo / "cli.py"
            if repo_cli.exists():
                cli_py = repo_cli
            else:
                raise SystemExit("cli.py not found; reinstall riscvbench or run from the repo root")

    sh([sys.executable, str(cli_py), "ingest",
        "--trace", str(state_csv),
        "--format", "baseline",
        "--out", str(run_dir)], cwd=repo)

    cls_cmd = [sys.executable, str(cli_py), "classify",
               "--in", str(run_dir),
               "--window-us", str(args.time_us)]
    if resid_csv.exists():
        cls_cmd += ["--residency", str(resid_csv)]
    sh(cls_cmd, cwd=repo)

    sh([sys.executable, str(cli_py), "export",
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
