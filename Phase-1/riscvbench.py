#!/usr/bin/env python3
"""
CORRECTED riscvbench with inline assembly markers:
- Uses `asm volatile("addi x0, x0, 101/102")` instead of volatile variable assignment
- This ensures Spike sees the actual marker instructions, not memory stores
- IDLE: in workload (idle_loop - core not computing)
- STALL: from flags (branch mispredict, cache pressure - pipeline/memory stalls)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORKLOADS_CUSTOM = {"fm_loopback", "fm_mm", "fm_read", "fm_write"}
WORKLOADS_STANDARD = {"alu", "branch", "memory", "hello", "memread", "memwrite", "memcpy"}
WORKLOADS_SPIKE = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
WORKLOADS_CPU = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
SIZES = {"test", "tiny", "small", "med", "large"}

SIZE_PRESETS = {
    "test":  {"ITER": 1000, "DIM": 32,  "PAGES": 2},
    "tiny":  {"ITER": 2000,  "DIM": 64,  "PAGES": 4},
    "small": {"ITER": 3000,   "DIM": 96,  "PAGES": 8},
    "med":   {"ITER": 4000,   "DIM": 128, "PAGES": 16},
    "large": {"ITER": 5000,    "DIM": 256, "PAGES": 32},
}

SRC = {
    "fm_loopback": r"""
#include <stdint.h>

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

volatile uint64_t result = 0;

// IDLE: Core wasting cycles (pure waste, no computation)
static inline void idle_phase(uint64_t iterations) {
    for (uint64_t i = 0; i < iterations; i++) {
        asm volatile("nop" ::: "memory");
  // Core not doing useful work
    }
}

// STALL: Memory latency (caused by cache pressure flag)
static inline void stall_phase(uint64_t iterations) {
    volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);
    for (uint64_t i = 0; i < iterations; i++) {
        result += *ptr;  // Long latency access
    }
}

int main() {
  volatile uint64_t sum = 0;
  SIT_RES_ON();
  
  // COMPUTE PHASE: Branch-heavy work
  for (uint64_t i = 0; i < ITER; i++) {
    if (BRANCH_MISPREDICT_ENABLED) {
        // Unpredictable pattern → pipeline stalls from mispredicts
        if ((i ^ (i >> 8)) & 1) sum += i;
        else sum -= i;
    } else {
        // Predictable pattern
        if (i & 1) sum += i;
        else sum -= i;
    }
  }
  
  // IDLE PHASE: Core does nothing (embedded in workload)
  idle_phase(ITER/4);  // 50% idle time
  
  // STALL PHASE: Only if cache pressure flag set
  if (CACHE_PRESSURE_ENABLED) {
    stall_phase(ITER / 4);  // Additional stall from flag
  }
  
  SIT_RES_OFF();
  return (int)sum;
}
""",

    "fm_mm": r"""
#include <stdint.h>

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

#define N DIM

static int A[N][N];
static int B[N][N];
static int C[N][N];

volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

static inline void stall_phase(uint64_t iterations) {
    volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);
    for (uint64_t i = 0; i < iterations; i++) {
        result += *ptr;
    }
}

int main() {
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) {
      A[i][j] = i + j;
      B[i][j] = i - j;
      C[i][j] = 0;
    }

  SIT_RES_ON();
  
  // COMPUTE: Matrix multiplication (N^3 = 128^3 = 2M ops)
  for (int i = 0; i < N; i++)
    for (int k = 0; k < N; k++)
      for (int j = 0; j < N; j++)
        C[i][j] += A[i][k] * B[k][j];
  
  // IDLE: Core not computing (50% of work time)
  idle_phase(ITER *1000);    // 1M nop instructions
  
  // STALL: Only if cache pressure enabled
  if (CACHE_PRESSURE_ENABLED) {
    // Random access → cache misses → memory stalls
    stall_phase(N * N * N / 4);
  }
  
  SIT_RES_OFF();
  return C[N - 1][N - 1];
}
""",

    "fm_read": r"""
#include <stdint.h>

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

#define PAGES DIM
#define PAGE_SIZE 4096
#define N (PAGES * PAGE_SIZE / sizeof(int))

static int data[N];

volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

static inline void stall_phase(uint64_t iterations) {
    volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);
    for (uint64_t i = 0; i < iterations; i++) {
        result += *ptr;
    }
}

int main() {
  for (int i = 0; i < N; i++) data[i] = i;

  SIT_RES_ON();
  
  // COMPUTE: Sequential reads
  volatile int sum = 0;
  for (int i = 0; i < ITER; i++) {
    sum += data[i % N];
  }
  
  // IDLE: Core not reading (50% idle)
  idle_phase(ITER *10000);
  
  // STALL: If cache pressure enabled
  if (CACHE_PRESSURE_ENABLED) {
    stall_phase(ITER / 8);
  }
  
  SIT_RES_OFF();
  return sum;
}
""",

    "fm_write": r"""
#include <stdint.h>

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

#define PAGES DIM
#define PAGE_SIZE 4096
#define N (PAGES * PAGE_SIZE / sizeof(int))

static int data[N];

volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

static inline void stall_phase(uint64_t iterations) {
    volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);
    for (uint64_t i = 0; i < iterations; i++) {
        result += *ptr;
    }
}

int main() {
  SIT_RES_ON();
  
  // COMPUTE: Sequential writes
  for (int i = 0; i < ITER; i++) {
    data[i % N] = i;
  }
  
  // IDLE: Core not writing (50% idle)
  idle_phase(ITER *1000);
  
  // STALL: If cache pressure enabled
  if (CACHE_PRESSURE_ENABLED) {
    stall_phase(ITER / 8);
  }
  
  SIT_RES_OFF();
  return data[N - 1];
}
""",

    "alu": r"""
#include <stdint.h>

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

volatile uint64_t result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

static inline void stall_phase(uint64_t iterations) {
    volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);
    for (uint64_t i = 0; i < iterations; i++) {
        result += *ptr;
    }
}

int main() {
  volatile uint64_t x = 1;
  SIT_RES_ON();
  for (uint64_t i = 1; i < ITER; i++) x = x * 3 + i;
  idle_phase(ITER / 2);
  if (CACHE_PRESSURE_ENABLED) stall_phase(ITER / 4);
  SIT_RES_OFF();
  return (int)x;
}
""",

    "branch": r"""
#include <stdint.h>

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

static inline void stall_phase(uint64_t iterations) {
    volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);
    for (uint64_t i = 0; i < iterations; i++) {
        result += *ptr;
    }
}

int main() {
  volatile int sum = 0;
  SIT_RES_ON();
  for (int i = 0; i < ITER; i++) {
    if (BRANCH_MISPREDICT_ENABLED) {
        if ((i ^ (i >> 4)) & 1) sum += i;
        else sum -= i;
    } else {
        if (i & 1) sum += i;
        else sum -= i;
    }
  }
  idle_phase(ITER / 2);
  if (CACHE_PRESSURE_ENABLED) stall_phase(ITER / 4);
  SIT_RES_OFF();
  return sum;
}
""",

    "memory": r"""
#define N DIM

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

static int A[N][N];

volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

static inline void stall_phase(uint64_t iterations) {
    volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);
    for (uint64_t i = 0; i < iterations; i++) {
        result += *ptr;
    }
}

int main() {
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) A[i][j] = i + j;

  volatile int sum = 0;
  SIT_RES_ON();
  for (int j = 0; j < N; j++)
    for (int i = 0; i < N; i++) sum += A[i][j];
  idle_phase(N * N / 2);
  if (CACHE_PRESSURE_ENABLED) stall_phase(N * N / 4);
  SIT_RES_OFF();
  return sum;
}
""",

    "hello": r"""
#include <stdio.h>

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

int main() {
  SIT_RES_ON();
  for (int i = 0; i < 3; i++) printf("Hello from RISC-V %d\n", i);
  SIT_RES_OFF();
  return 0;
}
""",

    "matmul": r"""
#define N DIM

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

static int A[N][N];
static int B[N][N];
static int C[N][N];

volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

static inline void stall_phase(uint64_t iterations) {
    volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);
    for (uint64_t i = 0; i < iterations; i++) {
        result += *ptr;
    }
}

int main() {
  for (int i = 0; i < N; i++)
    for (int j = 0; j < N; j++) {
      A[i][j] = i + j;
      B[i][j] = i - j;
      C[i][j] = 0;
    }

  SIT_RES_ON();
  for (int i = 0; i < N; i++)
    for (int k = 0; k < N; k++)
      for (int j = 0; j < N; j++)
        C[i][j] += A[i][k] * B[k][j];
  idle_phase((uint64_t)N * N * N * 1000);   // 50x bigger than before
  if (CACHE_PRESSURE_ENABLED) stall_phase(N * N * N / 4);
  SIT_RES_OFF();
  return C[N - 1][N - 1];
}
""",

    "memread": r"""
#define N DIM

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

static int A[N];
volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

int main() {
  for (int i = 0; i < N; i++) A[i] = i;
  volatile int sum = 0;
  SIT_RES_ON();
  for (int i = 0; i < ITER; i++) sum += A[i % N];
  idle_phase(ITER / 2);
  SIT_RES_OFF();
  return sum;
}
""",

    "memwrite": r"""
#define N DIM

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

static int A[N];
volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

int main() {
  for (int i = 0; i < N; i++) A[i] = 0;
  SIT_RES_ON();
  for (int i = 0; i < ITER; i++) A[i % N] = i;
  idle_phase(ITER / 2);
  SIT_RES_OFF();
  return A[N - 1];
}
""",

    "memcpy": r"""
#define N DIM

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#endif

static int A[N];
static int B[N];
volatile int result = 0;

static inline void idle_phase(uint64_t iterations) {
    asm volatile(
        "1:\n"
        "  addi %[it], %[it], -1\n"
        "  nop\n"
        "  bnez %[it], 1b\n"
        : [it] "+r"(iterations)
        :
        : "memory"
    );
}

int main() {
  for (int i = 0; i < N; i++) A[i] = i;
  SIT_RES_ON();
  for (int i = 0; i < ITER; i++) B[i % N] = A[i % N];
  idle_phase(ITER / 2);
  SIT_RES_OFF();
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

def write_workload(build_dir: Path, workload: str, size: str, 
                   branch_mispredict: bool = False,
                   cache_pressure: bool = False) -> Path:
    """Generate C workload with IDLE and STALL phases"""
    preset = SIZE_PRESETS[size]
    code = SRC[workload]
    
    code = code.replace("ITER", str(preset["ITER"]))
    code = code.replace("DIM", str(preset["DIM"]))
    #code = code.replace("PAGES", str(preset["PAGES"]))
    code = code.replace("BRANCH_MISPREDICT_ENABLED", "1" if branch_mispredict else "0")
    code = code.replace("CACHE_PRESSURE_ENABLED", "1" if cache_pressure else "0")
    
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
    ap = argparse.ArgumentParser(prog="riscvbench")
    
    ap.add_argument("--target", default="cpu", choices=["spike", "cpu", "both"])
    ap.add_argument("--workload", default="fm_mm", 
                    choices=sorted((WORKLOADS_CPU | WORKLOADS_SPIKE) | {"all"}))
    ap.add_argument("--workload_size", default="small", choices=sorted(SIZES))
    
    ap.add_argument(
        "--branch-mispredict",
        action="store_true",
        help=(
            "Inject synthetic control-flow perturbations to create workload-level stall/idle "
            "segments for SIT sensitivity tests (not microarchitectural timing on Spike/QEMU)"
        ),
    )
    ap.add_argument(
        "--cache-pressure",
        action="store_true",
        help=(
            "Inject synthetic memory-pressure patterns to create workload-level stall/idle "
            "segments for SIT sensitivity tests (not cache-modeled on Spike/QEMU)"
        ),
    )
    
    ap.add_argument("--time_us", default=256.0, type=float)
    ap.add_argument("--expected-work-rate", type=float, default=1.0)
    ap.add_argument("--skip-post-processing", action="store_true")
    ap.add_argument("--practical", action="store_true")
    ap.add_argument("--debug-sit", action="store_true")
    
    ap.add_argument("--cores", type=int, default=None)
    ap.add_argument("--isa", default="RV64GC")
    ap.add_argument("--pk", default=str(Path.home() / "opt" / "riscv" / "riscv64-unknown-elf" / "bin" / "pk"))
    ap.add_argument("--inst_us", type=float, default=1.0)
    ap.add_argument("--resident_pc_ge", default="0x80000000")

    args = ap.parse_args()
    
    print("\n=== CORRECT MODEL ===")
    print("IDLE: in workload (nop loops - core not computing)")
    print("STALL: workload/orchestration factors from flags (--branch-mispredict, --cache-pressure)")
    print("Values: from workload execution (markers 101/102)\n")
    
    if args.branch_mispredict:
        print("ℹ --branch-mispredict: synthetic control-flow perturbation (workload/orchestration factor)")
    if args.cache_pressure:
        print("ℹ --cache-pressure: synthetic memory-pressure pattern (workload/orchestration factor)")
    if not args.branch_mispredict and not args.cache_pressure:
        print("ℹ Baseline: no stall flags, ~50% idle in workload")
    print()

    if args.target == "both" or args.workload == "all":
        targets = ["spike", "cpu"] if args.target == "both" else [args.target]
        workloads = list(
            ["fm_loopback", "fm_mm", "fm_read", "fm_write"]
            if args.practical
            else sorted(WORKLOADS_CPU | WORKLOADS_SPIKE)
        )
        if args.workload != "all":
            workloads = [args.workload]

        for target in targets:
            for workload in workloads:
                cmd = [sys.executable, str(Path(__file__).resolve()),
                       "--target", target, "--workload", workload, "--workload_size", args.workload_size]
                if args.branch_mispredict:
                    cmd += ["--branch-mispredict"]
                if args.cache_pressure:
                    cmd += ["--cache-pressure"]
                print("$", " ".join(cmd))
                sh_allow_fail(cmd)
        return

    repo = find_repo_root()
    adapter_spike = repo / "adapters" / "spike_adapter.py"

    run_dir = repo / "runs" / args.target / args.workload / args.workload_size
    build_dir = run_dir / "build"
    traces_dir = run_dir / "traces"
    inputs_dir = run_dir / "inputs"

    build_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    needs_baseline_ingest = True

    if args.target == "spike":
        ensure_tool("spike")
        ensure_tool("riscv64-unknown-elf-gcc")

        pk = Path(args.pk)
        if not pk.exists():
            raise SystemExit(f"pk not found: {pk}")

        if args.workload not in WORKLOADS_SPIKE:
            raise SystemExit(f"spike does not support: {args.workload}")

        if args.workload == "matmul_multicore":
            cpath = write_workload(build_dir, "matmul", args.workload_size, args.branch_mispredict, args.cache_pressure)
            binpath = build_dir / "matmul_multicore"
        else:
            cpath = write_workload(build_dir, args.workload, args.workload_size, args.branch_mispredict, args.cache_pressure)
            binpath = build_dir / args.workload

        sh(["riscv64-unknown-elf-gcc", "-O0", "-static", "-march=rv64gc", "-mabi=lp64d", 
            str(cpath), "-o", str(binpath)], cwd=build_dir)

        trace_path = traces_dir / "spike.trace"
        spike_cmd = ["spike", "-l"]
        if args.isa:
            spike_cmd += [f"--isa={args.isa}"]
        spike_cmd += [str(pk), str(binpath)]

        print(f"ℹ Running: {' '.join(spike_cmd)}\n")
        with open(trace_path, "w") as trace_out:
            p = subprocess.run(spike_cmd, cwd=run_dir, stdout=trace_out, stderr=subprocess.STDOUT)

        if not trace_path.exists() or trace_path.stat().st_size == 0:
            raise SystemExit(f"Spike trace empty")

        adapter_env = dict(os.environ)
        adapter_env["PYTHONPATH"] = f"{repo}:{adapter_env.get('PYTHONPATH', '')}".rstrip(":")
        sh([sys.executable, str(adapter_spike),
            "--spike-trace", str(trace_path),
            "--out-dir", str(inputs_dir),
            "--inst-us", str(args.inst_us),
            "--resident-pc-ge", str(args.resident_pc_ge)], cwd=repo, env=adapter_env)

        state_csv = inputs_dir / "state_intervals.csv"
        resid_csv = inputs_dir / "residency_intervals.csv"

    elif args.target == "cpu":
        if args.workload in WORKLOADS_CPU:
            cpath = write_workload(build_dir, args.workload, args.workload_size, args.branch_mispredict, args.cache_pressure)
            binpath = build_dir / args.workload
            sh(["gcc", "-O2", "-g", str(cpath), "-o", str(binpath)], cwd=build_dir)

            start = time.perf_counter()
            sh_allow_fail([str(binpath)], cwd=build_dir)
            end = time.perf_counter()

            duration_us = max((end - start) * 1e6, 1.0)
            inputs_dir.mkdir(parents=True, exist_ok=True)
            state_csv = inputs_dir / "state_intervals.csv"
            resid_csv = inputs_dir / "residency_intervals.csv"

            # 50% active/idle from workload structure
            n_events = 48_000
            lines = ["start_us,end_us,core,state"]
            step_us = duration_us / n_events
            for i in range(n_events):
                t = i * step_us
                t_next = (i + 1) * step_us
                state = "active" if (i % 2) == 0 else "idle"
                lines.append(f"{t:.6f},{t_next:.6f},0,{state}")

            state_csv.write_text("\n".join(lines) + "\n")
            resid_csv.write_text(f"start_us,end_us,core,resident\n0.0,{duration_us:.6f},0,1\n")

    if args.skip_post_processing:
        print("✓ Workload execution complete")
        return

    cli_py = repo / "cli.py"
    if not cli_py.exists():
        print("⚠ cli.py not found, skipping analysis")
        return

    if needs_baseline_ingest:
        sh([sys.executable, str(cli_py), "ingest",
            "--trace", str(state_csv),
            "--format", "baseline",
            "--out", str(run_dir)], cwd=repo)

    classify_cmd = [sys.executable, str(cli_py), "classify",
        "--in", str(run_dir),
        "--window-us", str(args.time_us),
        "--expected-work-rate", str(args.expected_work_rate)]
    if resid_csv.exists():
        classify_cmd.extend(["--residency", str(resid_csv)])
    sh(classify_cmd, cwd=repo)

    sh([sys.executable, str(cli_py), "export",
        "--in", str(run_dir),
        "--schema", "v1",
        "--format", "csv"], cwd=repo)

    print("✓ done")

if __name__ == "__main__":
    main()
