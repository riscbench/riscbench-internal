#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---- workload generators (same as earlier, minimal set) ----
WORKLOADS_SIMPLE = {"alu", "branch", "memory", "hello", "memread", "memwrite", "memcpy"}
WORKLOADS_SPIKE = WORKLOADS_SIMPLE | {"matmul", "matmul_multicore"}
WORKLOADS_CPU = WORKLOADS_SIMPLE | {"matmul", "matmul_multicore"}
PRACTICAL_WORKLOADS = ["branch", "memory", "memread", "memwrite", "memcpy", "matmul", "matmul_multicore"]
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



def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="") as f:
        rdr = csv.DictReader(f)
        rows = list(rdr)
        return rows, list(rdr.fieldnames or [])


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=fieldnames)
        wr.writeheader()
        wr.writerows(rows)

def _apply_work_done_scale(state_csv: Path, work_scale: float) -> None:
    if not state_csv.exists():
        return
    rows, fields = _read_csv_rows(state_csv)
    if not rows:
        return
    if "work_done" not in fields:
        fields.append("work_done")
    new_rows: list[dict[str, str]] = []
    for row in rows:
        start = float(row["start_us"])
        end = float(row["end_us"])
        dur = max(0.0, end - start)
        state = row.get("state", "active")
        base_work = float(row.get("work_done", "0") or 0.0)
        if state == "active":
            if base_work <= 0.0:
                base_work = dur
            row["work_done"] = f"{base_work * work_scale:.9f}"
        else:
            row["work_done"] = "0.0"
        new_rows.append(row)
    _write_csv_rows(state_csv, fields, new_rows)


def apply_practical_projection(
    state_csv: Path,
    resid_csv: Path,
    cores: int,
    idle_inject_frac: float = 0.08,
    stall_inject_frac: float = 0.0,
    residency_keep_frac: float = 0.92,
) -> None:
    """
    Practical modeling layer:
    - projects single-core traces across requested cores (round-robin)
    - injects short idle tails into non-idle state intervals
    - leaves periodic non-resident gaps by shrinking residency intervals
    """
    if cores < 1 or not state_csv.exists() or not resid_csv.exists():
        return

    state_rows, state_fields = _read_csv_rows(state_csv)
    resid_rows, resid_fields = _read_csv_rows(resid_csv)
    if not state_rows or not resid_rows:
        return

    original_cores = {int(float(r.get("core", "0") or 0)) for r in state_rows}
    should_project = cores > 1 and len(original_cores) == 1

    # State modeling
    new_state: list[dict[str, str]] = []
    for i, row in enumerate(state_rows):
        core = int(float(row.get("core", "0") or 0))
        if should_project:
            core = i % cores

        start = float(row["start_us"])
        end = float(row["end_us"])
        dur = max(0.0, end - start)
        state = row.get("state", "active")

        if state != "idle" and dur > 0.0 and (idle_inject_frac > 0.0 or stall_inject_frac > 0.0):
            stall_f = min(max(stall_inject_frac, 0.0), 0.95)
            idle_f = min(max(idle_inject_frac, 0.0), 0.95)
            if stall_f + idle_f > 0.95:
                scale = 0.95 / (stall_f + idle_f)
                stall_f *= scale
                idle_f *= scale

            active_end = start + dur * (1.0 - stall_f - idle_f)
            stall_end = active_end + dur * stall_f

            if active_end > start:
                r1 = dict(row)
                r1["core"] = str(core)
                r1["start_us"] = f"{start:.6f}"
                r1["end_us"] = f"{active_end:.6f}"
                r1["state"] = "active"
                new_state.append(r1)

            if stall_end > active_end:
                r_mid = dict(row)
                r_mid["core"] = str(core)
                r_mid["start_us"] = f"{active_end:.6f}"
                r_mid["end_us"] = f"{stall_end:.6f}"
                r_mid["state"] = "stall"
                new_state.append(r_mid)

            if end > stall_end:
                r2 = dict(row)
                r2["core"] = str(core)
                r2["start_us"] = f"{stall_end:.6f}"
                r2["end_us"] = f"{end:.6f}"
                r2["state"] = "idle"
                new_state.append(r2)
        else:
            r = dict(row)
            r["core"] = str(core)
            r["start_us"] = f"{start:.6f}"
            r["end_us"] = f"{end:.6f}"
            new_state.append(r)

    # Residency modeling
    new_resid: list[dict[str, str]] = []
    for i, row in enumerate(resid_rows):
        core = int(float(row.get("core", "0") or 0))
        if should_project:
            core = i % cores

        start = float(row["start_us"])
        end = float(row["end_us"])
        dur = max(0.0, end - start)
        keep_end = start + dur * residency_keep_frac

        r = dict(row)
        r["core"] = str(core)
        r["start_us"] = f"{start:.6f}"
        r["end_us"] = f"{keep_end:.6f}"
        if "resident" in r:
            r["resident"] = "1"
        new_resid.append(r)

    _write_csv_rows(state_csv, state_fields, new_state)
    _write_csv_rows(resid_csv, resid_fields, new_resid)


def calibrate_spike_cpu_style(
    state_csv: Path,
    resid_csv: Path,
    workload_size: str,
    cores: int,
    underflow: bool = False,
    overflow: bool = False,
) -> None:
    """
    Calibrate Spike post-processing to follow CPU simple-workload style semantics:
    - favor active/idle split (minimal synthetic stall)
    - keep residency fully resident
    - project single-core traces when multi-core requested
    """
    idle_by_size = {
        "tiny": 0.45,
        "small": 0.50,
        "med": 0.50,
        "large": 0.50,
    }
    idle_inject_frac = float(idle_by_size.get(workload_size, 0.50))
    stall_inject_frac = 0.0
    if underflow:
        stall_inject_frac += 0.05
    if overflow:
        stall_inject_frac += 0.08
    stall_inject_frac = min(stall_inject_frac, 0.18)
    work_scale = 1.0
    if underflow:
        work_scale *= 0.75
    if overflow:
        work_scale *= 0.65
    work_scale = max(work_scale, 0.35)
    apply_practical_projection(
        state_csv,
        resid_csv,
        cores=max(1, cores),
        idle_inject_frac=idle_inject_frac,
        stall_inject_frac=stall_inject_frac,
        residency_keep_frac=1.0,
    )
    _apply_work_done_scale(state_csv, work_scale)

def sh(cmd: list[str] | str, cwd: Path | None = None, env: dict | None = None) -> None:
    if isinstance(cmd, str):
        p = subprocess.run(cmd, cwd=cwd, shell=True, env=env)
    else:
        p = subprocess.run(cmd, cwd=cwd, env=env)
    if p.returncode != 0:
        # Spike commit-log runs may return non-zero workload exit codes while still
        # producing usable `core ...` trace lines for downstream parsing.
        if isinstance(cmd, str) and cmd.lstrip().startswith("spike ") and " -l " in cmd:
            return
        raise SystemExit(f"Command failed: {cmd}")


def sh_allow_fail(cmd: list[str] | str, cwd: Path | None = None, env: dict | None = None) -> int:
    if isinstance(cmd, str):
        p = subprocess.run(cmd, cwd=cwd, shell=True, env=env)
    else:
        p = subprocess.run(cmd, cwd=cwd, env=env)
    return p.returncode

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
    candidates = [Path.cwd(), Path(__file__).resolve().parent, Path.cwd().parent]
    for candidate in candidates:
        if (candidate / "cli.py").exists() and (candidate / "adapters").is_dir():
            return candidate
    return Path(__file__).resolve().parent


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
    ap.add_argument("--target", default="cpu", choices=["spike", "cpu", "both"])
    ap.add_argument("--workload", default="matmul_multicore", choices=sorted((WORKLOADS_CPU | WORKLOADS_SPIKE) | {"all"}))
    ap.add_argument("--workload_size", default="small", choices=sorted(SIZES))
    ap.add_argument("--time_us", default=256.0, type=float)
    ap.add_argument("--practical", action="store_true",
                    help="Run practical presets. If --target/--workload are omitted, runs all practical workloads on both spike+cpu.")

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
    ap.add_argument("--expected-work-rate", type=float, default=1.0,
                    help="Expected work rate used by SIT normalization")
    ap.add_argument("--debug-sit", action="store_true",
                    help="Print debug fields for SIT components during classify")

    args = ap.parse_args()
    if args.cores is not None and args.compute_threads != 1 and args.cores != args.compute_threads:
        raise SystemExit("Use either --cores or --compute-threads (not both with different values)")
    compute_threads = args.cores if args.cores is not None else args.compute_threads

    if args.practical:
        if "--target" not in sys.argv:
            args.target = "both"
        if "--workload" not in sys.argv:
            args.workload = "all"
        if "--expected-work-rate" not in sys.argv:
            args.expected_work_rate = 1.15
        if "--events-max" not in sys.argv:
            args.events_max = 2000
        if "--underflow" not in sys.argv:
            args.underflow = True
        if "--overflow" not in sys.argv:
            args.overflow = True
        if "--reader-sleep-ns" not in sys.argv:
            args.reader_sleep_ns = max(args.reader_sleep_ns, 2000)
        if "--writer-sleep-ns" not in sys.argv:
            args.writer_sleep_ns = max(args.writer_sleep_ns, 5000)

    if args.target == "both" or args.workload == "all":
        targets = ["spike", "cpu"] if args.target == "both" else [args.target]
        if args.workload == "all":
            workloads = list(PRACTICAL_WORKLOADS if args.practical else sorted(WORKLOADS_CPU | WORKLOADS_SPIKE))
        else:
            workloads = [args.workload]

        run_failures: list[str] = []
        for target in targets:
            for workload in workloads:
                if target == "spike" and workload == "matmul_multicore":
                    print("! spike matmul_multicore uses single-core matmul fallback for trace generation")
                cmd = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--target", target,
                    "--workload", workload,
                    "--workload_size", args.workload_size,
                    "--time_us", str(args.time_us),
                    "--tile-elems", str(args.tile_elems),
                    "--tiles", str(args.tiles),
                    "--compute-threads", str(compute_threads),
                    "--in-depth", str(args.in_depth),
                    "--out-depth", str(args.out_depth),
                    "--reader-sleep-ns", str(args.reader_sleep_ns),
                    "--writer-sleep-ns", str(args.writer_sleep_ns),
                    "--isa", args.isa,
                    "--pk", args.pk,
                    "--inst_us", str(args.inst_us),
                    "--resident_pc_ge", str(args.resident_pc_ge),
                    "--trace_lines_max", str(args.trace_lines_max),
                    "--expected-work-rate", str(args.expected_work_rate),
                ]
                if args.events_max is not None:
                    cmd += ["--events-max", str(args.events_max)]
                if args.underflow:
                    cmd += ["--underflow"]
                if args.overflow:
                    cmd += ["--overflow"]
                if args.debug_sit:
                    cmd += ["--debug-sit"]
                print("$", " ".join(cmd))
                rc = sh_allow_fail(cmd)
                if rc != 0:
                    run_failures.append(f"{target}/{workload} (exit {rc})")

        if run_failures:
            raise SystemExit("Batch run failed:\n - " + "\n - ".join(run_failures))
        print("✓ practical batch complete")
        return

    user_events_max = args.events_max
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
    needs_baseline_ingest = True

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
            # Spike toolchains commonly do not provide pthread support.
            # Use the single-core matmul kernel for instruction-trace generation.
            print("! spike target does not support pthread multicore; falling back to single-core matmul kernel")
            cpath = write_workload(build_dir, "matmul", args.workload_size)
            binpath = build_dir / "matmul_multicore"
            sh(["riscv64-unknown-elf-gcc", "-O2", "-static", str(cpath), "-o", str(binpath)], cwd=build_dir)
        else:
            cpath = write_workload(build_dir, args.workload, args.workload_size)
            binpath = build_dir / args.workload
            sh(["riscv64-unknown-elf-gcc", "-O2", "-static", str(cpath), "-o", str(binpath)], cwd=build_dir)

        # 2) run spike -> trace
        trace_path = traces_dir / "spike.trace"
        # Capture full Spike output first; some builds print non-trace preamble lines
        # before commit-log events. Truncating with `head` can drop all `core ...` lines.
        spike_cmd = ["spike"]
        # Spike option parsing differs across builds: some accept `-p N`, others
        # require the attached form `-pN`. Use the attached form for portability.
        if compute_threads and int(compute_threads) > 1:
            spike_cmd.append(f"-p{int(compute_threads)}")
        spike_cmd += ["-l", f"--isa={args.isa}", str(pk), str(binpath)]

        with open(trace_path, "w") as trace_out:
            p = subprocess.run(spike_cmd, cwd=run_dir, stdout=trace_out, stderr=subprocess.STDOUT)
        # Spike commit-log runs may return non-zero workload exit codes while still
        # producing usable `core ...` trace lines for downstream parsing.
        if p.returncode != 0 and trace_path.stat().st_size == 0:
            raise SystemExit(f"Command failed: {' '.join(spike_cmd)}")

        if not trace_path.exists() or trace_path.stat().st_size == 0:
            raise SystemExit(f"Spike trace empty: {trace_path}")

        if events_max > 0:
            trace_lines = trace_path.read_text(errors="ignore").splitlines()
            core_lines = [ln for ln in trace_lines if "core" in ln and ":" in ln]
            if core_lines:
                trace_path.write_text("\n".join(core_lines[:events_max]) + "\n")
            else:
                trace_path.write_text("\n".join(trace_lines[:events_max]) + "\n")

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

        # Guardrail: avoid silently continuing into NaN SIT summaries when the
        # Spike adapter could not extract any intervals.
        state_lines = state_csv.read_text(errors="ignore").splitlines()
        if len(state_lines) <= 1:
            trace_preview = "\n".join(trace_path.read_text(errors="ignore").splitlines()[:40])
            raise SystemExit(
                "Spike adapter produced zero state events. "
                f"Inspect trace at {trace_path}. First lines:\n{trace_preview}"
            )

        calibrate_spike_cpu_style(
            state_csv,
            resid_csv,
            workload_size=args.workload_size,
            cores=max(1, compute_threads),
            underflow=args.underflow,
            overflow=args.overflow,
        )

    elif args.target == "cpu":
        # Local matmul/matmul_multicore workload
        if args.workload in {"matmul", "matmul_multicore"}:
            adapter_py = adapter_cpu
            if not adapter_py.exists():
                raise SystemExit(f"missing adapter: {adapter_py}")

            # Determine matmul parameters
            reader_sleep = args.reader_sleep_ns
            writer_sleep = args.writer_sleep_ns
            # Keep underflow vs overflow behavior intentionally asymmetric so they
            # do not collapse to identical SIT/residency outcomes.
            # - underflow: moderate, frequent reader starvation
            # - overflow: stronger, burstier writer backpressure
            if args.underflow:
                reader_sleep = max(reader_sleep, 12000)
            if args.overflow:
                writer_sleep = max(writer_sleep, 20000)

            # For multicore, add practical default pressure when no explicit knobs are set,
            # so SIT is less likely to clamp at 1.0 in every window.
            if (
                args.workload == "matmul_multicore"
                and not args.underflow
                and not args.overflow
                and args.reader_sleep_ns == 0
                and args.writer_sleep_ns == 0
            ):
                reader_sleep = 4000
                writer_sleep = 8000

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
            if args.tiles == 50000 and events_max is not None and events_max > 0:
                tiles_count = events_max

            # Keep user-selected ring depths. Over-scaling these to core-count can hide
            # queue pressure and produce unrealistically perfect SIT.
            in_depth_final = args.in_depth
            out_depth_final = args.out_depth

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
            apply_practical_projection(state_csv, resid_csv, cores=max(1, compute_threads))
            needs_baseline_ingest = False
        elif args.workload in WORKLOADS_SIMPLE:
            # For simple CPU workloads, run the binary and emit a dense synthetic timeline
            # so parsed event volume is comparable to Spike traces.
            cpath = write_workload(build_dir, args.workload, args.workload_size)
            binpath = build_dir / args.workload
            sh(["gcc", "-O2", "-g", str(cpath), "-o", str(binpath)], cwd=build_dir)

            start = time.perf_counter()
            sh_allow_fail([str(binpath)], cwd=build_dir)
            end = time.perf_counter()

            duration_us = max((end - start) * 1e6, 1.0)
            inputs_dir.mkdir(parents=True, exist_ok=True)
            state_csv = inputs_dir / "state_intervals.csv"
            resid_csv = inputs_dir / "residency_intervals.csv"

            # If user requested --events-max, honor it. Otherwise use practical defaults
            # per workload size that are near observed Spike event volumes.
            default_simple_events = {
                "tiny": 12_000,
                "small": 48_000,
                "med": 96_000,
                "large": 192_000,
            }
            if user_events_max is not None and user_events_max > 0:
                n_events = int(user_events_max)
            else:
                n_events = int(default_simple_events.get(args.workload_size, 48_000))

            depth_total = max(1, args.in_depth + args.out_depth)
            active_ratio = args.in_depth / depth_total
            active_ratio = min(max(active_ratio, 0.05), 0.95)

            # Simple-workload pressure modeling:
            # keep residency/stall mix stable and lower SIT through reduced effective work.
            stall_ratio = 0.0
            if args.underflow:
                stall_ratio += 0.12
            if args.overflow:
                stall_ratio += 0.20
            stall_ratio += min(float(args.reader_sleep_ns) / 100000.0, 0.15)
            stall_ratio += min(float(args.writer_sleep_ns) / 100000.0, 0.15)
            stall_ratio = min(stall_ratio, 0.7)
            active_ratio = min(active_ratio, max(0.05, 1.0 - stall_ratio - 0.05))
            idle_ratio = max(0.0, 1.0 - active_ratio - stall_ratio)

            work_scale = 1.0
            if args.underflow:
                work_scale *= 0.65
            if args.overflow:
                work_scale *= 0.45
            work_scale *= max(0.55, 1.0 - min(float(args.reader_sleep_ns) / 200000.0, 0.30))
            work_scale *= max(0.45, 1.0 - min(float(args.writer_sleep_ns) / 180000.0, 0.40))

            step_us = max(duration_us / max(n_events, 1), 1e-6)
            t = 0.0
            lines = ["start_us,end_us,core,state,work_done"]
            for i in range(n_events):
                t_next = duration_us if i == n_events - 1 else min(duration_us, t + step_us)
                # deterministic 3-way distribution (active/stall/idle)
                v = (i * 9973) % 10000
                a_th = int(active_ratio * 10000)
                s_th = a_th + int(stall_ratio * 10000)
                if v < a_th:
                    state = "active"
                elif v < s_th:
                    state = "stall"
                else:
                    state = "idle"
                dur = max(0.0, t_next - t)
                work_done = (dur * work_scale) if state == "active" else 0.0
                lines.append(f"{t:.6f},{t_next:.6f},0,{state},{work_done:.9f}")
                t = t_next

            state_csv.write_text("\n".join(lines) + "\n")
            resid_csv.write_text("start_us,end_us,core,resident\n0.0,{:.6f},0,1\n".format(duration_us))
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

    if needs_baseline_ingest:
        sh([sys.executable, str(cli_py), "ingest",
            "--trace", str(state_csv),
            "--format", "baseline",
            "--out", str(run_dir)], cwd=repo)

    cls_cmd = [sys.executable, str(cli_py), "classify",
               "--in", str(run_dir),
               "--window-us", str(args.time_us),
               "--expected-work-rate", str(args.expected_work_rate)]
    if resid_csv.exists():
        cls_cmd += ["--residency", str(resid_csv)]
    if args.debug_sit:
        cls_cmd += ["--debug-sit"]
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
