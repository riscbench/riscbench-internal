#!/usr/bin/env python3
"""
RISCBench runner for TT ingest plus simulator backends.

In this bundle, simulator workloads default to baseline execution:
- no injected workload idle/stall phases
- no synthetic branch/cache pressure segments unless explicitly requested
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

_BUNDLE_ROOT = Path(__file__).resolve().parent.parent
if str(_BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUNDLE_ROOT))

from sit_classifier.adapters.work_markers import encode_work_units_to_imm
from sit_classifier.workload_calibration import resolve_auto_ops_per_zone, resolve_size_active_boost

WORKLOADS_ACCEL = {
    "vecadd",
    "eltwise_binary",
    "eltwise_binary_mul",
    "eltwise_sfpu",
    "custom_sfpi_add",
    "custom_sfpi_smoothstep",
}
WORKLOADS_CUSTOM = {"fm_loopback", "fm_mm", "fm_sparse", "fm_read", "fm_write"} | WORKLOADS_ACCEL
WORKLOADS_STANDARD = {"alu", "branch", "memory", "hello", "memread", "memwrite", "memcpy"}
WORKLOADS_SPIKE = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
WORKLOADS_CPU = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
WORKLOADS_GEM5 = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore", "matmul_shared"}
WORKLOADS_QEMU = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
WORKLOADS_ALL_STANDARD = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
WORKLOAD_ALIASES = {
    "tt_vecadd": "vecadd",
    "tt_eltwise_binary": "eltwise_binary",
    "tt_eltwise_sfpu": "eltwise_sfpu",
    "tt_custom_sfpi_add": "custom_sfpi_add",
    "tt_custom_sfpi_smoothstep": "custom_sfpi_smoothstep",
}
TT_DYNAMIC_TILE_SIZE_RE = re.compile(r"^tt_(\d+)tile$")
TT_DYNAMIC_MATMUL_SIZE_RE = re.compile(r"^tt_m(\d+)_n(\d+)_k(\d+)$")
SIZES = {
    "test",
    "tt_tile",
    "tiny",
    "small",
    "med",
    "large",
    "tt_1tile",
    "tt_4tile",
    "tt_64tile",
    "tt_256tile",
    "tt_1024tile",
}

SIZE_PRESETS = {
    "test":  {"ITER": 256, "DIM": 16,  "PAGES": 2,  "ACTIVE_BOOST": 1},
    "tt_tile": {"ITER": 1024, "DIM": 32, "PAGES": 2, "ACTIVE_BOOST": 1},
    "tiny":  {"ITER": 2000, "DIM": 64,  "PAGES": 4,  "ACTIVE_BOOST": 2},
    "small": {"ITER": 3000, "DIM": 96,  "PAGES": 8,  "ACTIVE_BOOST": 3},
    "med":   {"ITER": 4000, "DIM": 128, "PAGES": 16, "ACTIVE_BOOST": 4},
    "large": {"ITER": 5000, "DIM": 256, "PAGES": 32, "ACTIVE_BOOST": 5},
    "tt_1tile": {"ITER": 1, "DIM": 32, "PAGES": 2, "ACTIVE_BOOST": 1},
    "tt_4tile": {"ITER": 1, "DIM": 32, "PAGES": 2, "ACTIVE_BOOST": 4},
    "tt_64tile": {"ITER": 1, "DIM": 32, "PAGES": 2, "ACTIVE_BOOST": 64},
    "tt_256tile": {"ITER": 1, "DIM": 32, "PAGES": 2, "ACTIVE_BOOST": 256},
    "tt_1024tile": {"ITER": 1, "DIM": 32, "PAGES": 2, "ACTIVE_BOOST": 1024},
}

TT_WORK_RATE_SIZES = {
    "tt_tile",
    "tt_1tile",
    "tt_4tile",
    "tt_64tile",
    "tt_256tile",
    "tt_1024tile",
}

DEFAULT_WINDOW_US = 256.0
DEFAULT_EXPECTED_WORK_RATE = 1.0
DEFAULT_TT_WINDOW_US = 256.0
DEFAULT_TT_RESIDENCY_MODEL = "kernel_envelope"
DEFAULT_TT_OPS_PER_ZONE = 1024.0
DEFAULT_TT_STRICT = True


def canonicalize_workload_name(workload: str) -> str:
    return WORKLOAD_ALIASES.get(str(workload), str(workload))


def is_tt_tile_size(size: str) -> bool:
    raw = str(size or "").strip()
    return resolve_size_active_boost(raw) is not None


def is_supported_workload_size(size: str) -> bool:
    raw = str(size or "").strip()
    if raw in SIZES:
        return True
    if TT_DYNAMIC_TILE_SIZE_RE.match(raw):
        return True
    if TT_DYNAMIC_MATMUL_SIZE_RE.match(raw):
        return True
    return False


def parse_workload_size(value: str) -> str:
    raw = str(value or "").strip()
    if is_supported_workload_size(raw):
        return raw
    choices = sorted(SIZES) + ["tt_<N>tile", "tt_m<M>_n<N>_k<K>"]
    raise argparse.ArgumentTypeError(
        f"invalid workload size '{raw}' (expected one of {', '.join(choices)})"
    )


def resolve_size_preset(size: str) -> dict | None:
    raw = str(size or "").strip()
    preset = SIZE_PRESETS.get(raw)
    if preset is not None:
        return dict(preset)

    active_boost = resolve_size_active_boost(raw)
    if active_boost is not None:
        return {"ITER": 1, "DIM": 32, "PAGES": 2, "ACTIVE_BOOST": int(active_boost)}

    match = TT_DYNAMIC_MATMUL_SIZE_RE.match(raw)
    if match:
        dim = max(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return {"ITER": 1, "DIM": dim, "PAGES": 2, "ACTIVE_BOOST": 1}

    return None

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
#define SIT_STALL_ON() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 103" ::: "memory"); \
} while(0)
#define SIT_STALL_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 104" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#define SIT_STALL_ON()  ((void)0)
#define SIT_STALL_OFF() ((void)0)
#endif

volatile uint64_t result = 0;
static volatile uint64_t STALL_BUF[4096];

// IDLE: Core wasting cycles (pure waste, no computation)
static inline void idle_phase(uint64_t iterations) {
    for (uint64_t i = 0; i < iterations; i++) {
        asm volatile("nop" ::: "memory");
  // Core not doing useful work
    }
}

// STALL: Memory latency (caused by cache pressure flag)
static inline void stall_phase(uint64_t iterations) {
    for (uint64_t i = 0; i < iterations; i++) {
        uint64_t idx = (i * 1315423911ULL) & 4095ULL;
        uint64_t v = STALL_BUF[idx];
        result += v;
        STALL_BUF[idx] = result;
    }
}

int main() {
  uint64_t sum = 0;
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

  // Size-scaled compute boost: keeps higher sizes more compute-dense.
  for (uint64_t i = 0; i < ((uint64_t)ACTIVE_BOOST * ITER); i++) {
    sum = (sum * 1103515245ULL + 12345ULL + i) ^ (sum >> 13);
  }

  // Explicitly model branch mispredict penalty as a stall segment.
  // Use a meaningful duration so ordering is visible in SIT summaries.
  if (BRANCH_MISPREDICT_ENABLED) {
    SIT_STALL_ON();
    stall_phase(ITER * 2);
    SIT_STALL_OFF();
  }
  
  // IDLE PHASE: Core does nothing (embedded in workload)
  idle_phase(ITER/4);  // 50% idle time
  
  // STALL PHASE: cache pressure is stronger than branch-only penalty.
  if (CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase(ITER * 4);  // Additional stall from flag
    SIT_STALL_OFF();
  }

  // Combined mode should be strictly harsher than either flag alone.
  if (BRANCH_MISPREDICT_ENABLED && CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase(ITER * 8);
    SIT_STALL_OFF();
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
#define SIT_STALL_ON() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 103" ::: "memory"); \
} while(0)
#define SIT_STALL_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 104" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#define SIT_STALL_ON()  ((void)0)
#define SIT_STALL_OFF() ((void)0)
#endif

#define N DIM

static int A[N][N];
static int B[N][N];
static int C[N][N];

volatile int result = 0;
static volatile uint64_t stall_sink = 0;
static volatile uint64_t STALL_BUF[4096];

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
    for (uint64_t i = 0; i < iterations; i++) {
        uint64_t idx = (i * 2654435761ULL) & 4095ULL;
        stall_sink += STALL_BUF[idx];
        STALL_BUF[idx] = stall_sink;
    }
    result = (int)(result + (int)stall_sink);
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

  // Branch-pressure phase: emulate mispredict-driven pipeline disruption.
  if (BRANCH_MISPREDICT_ENABLED) {
    volatile int branch_acc = 0;
    for (int i = 0; i < ITER * 6; i++) {
      if ((i ^ (i >> 3) ^ (i * 7)) & 1) branch_acc += i;
      else branch_acc -= i;
    }
    result += branch_acc;
    SIT_STALL_ON();
    // fm_mm is compute-dense; raise branch-stall duration so branch perturbation
    // remains visible versus baseline in reduced-matrix sweep plots.
    stall_phase((uint64_t)N * (uint64_t)N * 2);
    SIT_STALL_OFF();
  }
  
  // IDLE: Core not computing (50% of work time)
  // Keep traces practical for full size/flag sweeps.
  idle_phase(ITER * 60);
  
  // STALL: Only if cache pressure enabled
  if (CACHE_PRESSURE_ENABLED) {
    // Random access → cache misses → memory stalls
    stall_phase(N * N * N / 4);
  }

  if (BRANCH_MISPREDICT_ENABLED && CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase((uint64_t)N * (uint64_t)N);
    SIT_STALL_OFF();
  }
  
  SIT_RES_OFF();
  return C[N - 1][N - 1];
}
""",

    "fm_sparse": r"""
#include <stdint.h>

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#define SIT_STALL_ON() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 103" ::: "memory"); \
} while(0)
#define SIT_STALL_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 104" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#define SIT_STALL_ON()  ((void)0)
#define SIT_STALL_OFF() ((void)0)
#endif

#define N DIM
#define NNZ_PER_ROW 8
#define NNZ (N * NNZ_PER_ROW)

static int row_ptr[N + 1];
static int col_idx[NNZ];
static int values[NNZ];
static int x_vec[N];
static int y_vec[N];

volatile int result = 0;
static volatile uint64_t stall_sink = 0;
static volatile uint64_t STALL_BUF[4096];

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
    for (uint64_t i = 0; i < iterations; i++) {
        uint64_t idx = (i * 2246822519ULL) & 4095ULL;
        stall_sink += STALL_BUF[idx];
        STALL_BUF[idx] = stall_sink + i;
    }
    result = (int)(result + (int)stall_sink);
}

int main() {
  // Match fm_mm arithmetic scale: N^3 dense MACs ~= sparse_reps * N * NNZ_PER_ROW.
  int sparse_reps = (N * N) / NNZ_PER_ROW;
  if (sparse_reps < 1) sparse_reps = 1;

  for (int row = 0; row < N; row++) {
    row_ptr[row] = row * NNZ_PER_ROW;
    x_vec[row] = (row % 17) + 1;
    y_vec[row] = 0;
    for (int k = 0; k < NNZ_PER_ROW; k++) {
      int idx = row * NNZ_PER_ROW + k;
      col_idx[idx] = (row * 17 + k * 13 + 3) % N;
      values[idx] = ((row + 1) * (k + 3)) & 31;
      if (values[idx] == 0) values[idx] = 1;
    }
  }
  row_ptr[N] = NNZ;

  SIT_RES_ON();

  // COMPUTE: sparse matrix-vector multiply.
  // Keep baseline compute pressure comparable to fm_mm at test size.
  for (int rep = 0; rep < sparse_reps; rep++) {
    int local = 0;
    for (int row = 0; row < N; row++) {
      int acc = 0;
      for (int idx = row_ptr[row]; idx < row_ptr[row + 1]; idx++) {
        acc += values[idx] * x_vec[col_idx[idx]];
      }
      local += acc;
      y_vec[row] = acc;
    }
    for (int row = 0; row < N; row++) {
      x_vec[row] = (y_vec[row] + row + rep) & 1023;
    }
    result += local;
  }

  if (BRANCH_MISPREDICT_ENABLED) {
    volatile int branch_acc = 0;
    for (int i = 0; i < ITER * 6; i++) {
      if ((i ^ (i >> 3) ^ (i * 7)) & 1) branch_acc += i;
      else branch_acc -= i;
    }
    result += branch_acc;
    SIT_STALL_ON();
    // Keep sparse perturbation magnitudes aligned with fm_mm for fair comparison.
    stall_phase((uint64_t)N * (uint64_t)N * 2ULL);
    SIT_STALL_OFF();
  }

  // Match fm_mm idle shaping so sparse does not dominate via lower idle ratio.
  idle_phase((uint64_t)ITER * 60ULL);

  if (CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase((uint64_t)N * (uint64_t)N * (uint64_t)N / 4ULL);
    SIT_STALL_OFF();
  }

  if (BRANCH_MISPREDICT_ENABLED && CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase((uint64_t)N * (uint64_t)N);
    SIT_STALL_OFF();
  }

  SIT_RES_OFF();
  return result ^ y_vec[N - 1];
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
  // Keep traces practical for full size/flag sweeps.
  idle_phase(ITER * 20);
  
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
  // Keep traces practical for full size/flag sweeps.
  idle_phase(ITER * 20);
  
  // STALL: If cache pressure enabled
  if (CACHE_PRESSURE_ENABLED) {
    stall_phase(ITER / 8);
  }
  
  SIT_RES_OFF();
  return data[N - 1];
}
""",

    "vecadd": r"""
#include <stdint.h>

#ifdef __riscv
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

#define N (DIM * DIM)

static int32_t a_vec[N];
static int32_t b_vec[N];
static int32_t out_vec[N];

volatile int32_t result = 0;

int main() {
  for (int i = 0; i < N; i++) {
    a_vec[i] = (int32_t)((i * 3 + 1) & 1023);
    b_vec[i] = (int32_t)((i * 5 + 7) & 511);
    out_vec[i] = 0;
  }

  SIT_RES_ON();
  for (int rep = 0; rep < ACTIVE_BOOST; rep++) {
    int32_t acc = 0;
    for (int i = 0; i < N; i++) {
      int32_t value = a_vec[i] + b_vec[i] + rep;
      out_vec[i] = value;
      acc ^= (value + (int32_t)(i & 31));
    }
    result ^= acc;
  }
  SIT_RES_OFF();
  return result;
}
""",

    "eltwise_binary": r"""
#include <stdint.h>

#ifdef __riscv
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

#define N (DIM * DIM)

static int32_t lhs[N];
static int32_t rhs[N];
static int32_t out_binary[N];

volatile int32_t result = 0;

int main() {
  for (int i = 0; i < N; i++) {
    lhs[i] = (int32_t)((i * 11 + 5) & 1023);
    rhs[i] = (int32_t)((i * 7 + 9) & 255);
    out_binary[i] = 0;
  }

  SIT_RES_ON();
  for (int rep = 0; rep < ACTIVE_BOOST; rep++) {
    int32_t acc = 0;
    int32_t bias = (int32_t)((rep + 1) * 3);
    for (int i = 0; i < N; i++) {
      int32_t value = lhs[i] + rhs[i] + bias;
      out_binary[i] = value;
      acc += (value ^ (int32_t)(i & 15));
    }
    result ^= acc;
  }
  SIT_RES_OFF();
  return result;
}
""",

    "eltwise_binary_mul": r"""
#include <stdint.h>

#ifdef __riscv
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

#define N (DIM * DIM)

static int32_t lhs_mul[N];
static int32_t rhs_mul[N];
static int32_t out_mul[N];

volatile int32_t result = 0;

int main() {
  for (int i = 0; i < N; i++) {
    lhs_mul[i] = (int32_t)(((i * 13 + 17) & 255) + 1);
    rhs_mul[i] = (int32_t)(((i * 9 + 3) & 15) + 1);
    out_mul[i] = 0;
  }

  SIT_RES_ON();
  for (int rep = 0; rep < ACTIVE_BOOST; rep++) {
    int32_t acc = 0;
    int32_t scale = (int32_t)(rep + 1);
    for (int i = 0; i < N; i++) {
      int32_t value = lhs_mul[i] * (rhs_mul[i] + scale);
      out_mul[i] = value;
      acc ^= (value >> (i & 3));
    }
    result += acc;
  }
  SIT_RES_OFF();
  return result;
}
""",

    "eltwise_sfpu": r"""
#include <stdint.h>

#ifdef __riscv
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

#define N (DIM * DIM)

static int32_t sfpu_in[N];
static int32_t sfpu_out[N];

volatile int32_t result = 0;

int main() {
  for (int i = 0; i < N; i++) {
    sfpu_in[i] = (int32_t)((i * 19) - (N / 2));
    sfpu_out[i] = 0;
  }

  SIT_RES_ON();
  for (int rep = 0; rep < ACTIVE_BOOST; rep++) {
    int32_t acc = 0;
    int32_t shift = (int32_t)(rep * 4);
    for (int i = 0; i < N; i++) {
      int32_t value = sfpu_in[i] + shift;
      int32_t relu = value > 0 ? value : 0;
      sfpu_out[i] = relu;
      acc ^= (relu + (int32_t)(i & 7));
    }
    result ^= acc;
  }
  SIT_RES_OFF();
  return result;
}
""",

    "custom_sfpi_add": r"""
#include <stdint.h>

#ifdef __riscv
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

#define N (DIM * DIM)

static int32_t sfpi_a[N];
static int32_t sfpi_b[N];
static int32_t sfpi_out[N];

volatile int32_t result = 0;

static inline int32_t sfpi_add_emulated(int32_t lhs, int32_t rhs) {
  int32_t sum = lhs;
  sum += rhs;
  return sum;
}

int main() {
  for (int i = 0; i < N; i++) {
    sfpi_a[i] = (int32_t)((i * 23 + 1) & 511);
    sfpi_b[i] = (int32_t)((i * 29 + 5) & 511);
    sfpi_out[i] = 0;
  }

  SIT_RES_ON();
  for (int rep = 0; rep < ACTIVE_BOOST; rep++) {
    int32_t acc = 0;
    for (int i = 0; i < N; i++) {
      int32_t value = sfpi_add_emulated(sfpi_a[i], sfpi_b[i] + rep);
      sfpi_out[i] = value;
      acc += (value ^ (int32_t)(i & 31));
    }
    result ^= acc;
  }
  SIT_RES_OFF();
  return result;
}
""",

    "custom_sfpi_smoothstep": r"""
#include <stdint.h>

#ifdef __riscv
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

#define N (DIM * DIM)
#define Q15_ONE 32768

static int32_t smooth_in[N];
static int32_t smooth_out[N];

volatile int32_t result = 0;

static inline int32_t clamp_q15(int32_t x) {
  if (x < 0) return 0;
  if (x > Q15_ONE) return Q15_ONE;
  return x;
}

static inline int32_t smoothstep_q15(int32_t x) {
  int64_t x1 = clamp_q15(x);
  int64_t x2 = (x1 * x1) >> 15;
  int64_t x3 = (x2 * x1) >> 15;
  return (int32_t)(3 * x2 - 2 * x3);
}

int main() {
  for (int i = 0; i < N; i++) {
    smooth_in[i] = (int32_t)((i * 97 + 11) & (Q15_ONE - 1));
    smooth_out[i] = 0;
  }

  SIT_RES_ON();
  for (int rep = 0; rep < ACTIVE_BOOST; rep++) {
    int32_t acc = 0;
    for (int i = 0; i < N; i++) {
      int32_t input = smooth_in[i] + (rep * 257);
      int32_t value = smoothstep_q15(input);
      smooth_out[i] = value;
      acc ^= (value >> (i & 7));
    }
    result += acc;
  }
  SIT_RES_OFF();
  return result;
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
#define SIT_STALL_ON() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 103" ::: "memory"); \
} while(0)
#define SIT_STALL_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 104" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#define SIT_STALL_ON()  ((void)0)
#define SIT_STALL_OFF() ((void)0)
#endif

volatile int result = 0;
static volatile uint64_t stall_sink = 0;
static volatile uint64_t STALL_BUF[4096];

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
    for (uint64_t i = 0; i < iterations; i++) {
        uint64_t idx = (i * 2654435761ULL) & 4095ULL;
        stall_sink += STALL_BUF[idx];
        STALL_BUF[idx] = stall_sink;
    }
    result = (int)(result + (int)stall_sink);
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
  if (BRANCH_MISPREDICT_ENABLED) {
    SIT_STALL_ON();
    stall_phase(ITER * 2);
    SIT_STALL_OFF();
  }
  idle_phase(ITER / 2);
  if (CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase(ITER * 4);
    SIT_STALL_OFF();
  }
  if (BRANCH_MISPREDICT_ENABLED && CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase(ITER * 8);
    SIT_STALL_OFF();
  }
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

    "matmul_multicore": r"""
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define N DIM

#ifdef __riscv
// FIX: Force exact instruction encoding to prevent compiler optimization
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#define SIT_STALL_ON() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 103" ::: "memory"); \
} while(0)
#define SIT_STALL_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 104" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#define SIT_STALL_ON()  ((void)0)
#define SIT_STALL_OFF() ((void)0)
#endif

static int A[N][N];
static int B[N][N];
static int C[N][N];

volatile int result = 0;
static volatile uint64_t stall_sink = 0;
static volatile uint64_t STALL_BUF[4096];

static int get_arg_int(int argc, char **argv, const char *key, int defval) {
    for (int i = 1; i + 1 < argc; i++) {
        if (strcmp(argv[i], key) == 0) {
            return atoi(argv[i + 1]);
        }
    }
    return defval;
}

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
    for (uint64_t i = 0; i < iterations; i++) {
        uint64_t idx = (i * 2654435761ULL) & 4095ULL;
        stall_sink += STALL_BUF[idx];
        STALL_BUF[idx] = stall_sink + i;
    }
    result = (int)(result + (int)stall_sink);
}

int main(int argc, char **argv) {
  int worker_id = get_arg_int(argc, argv, "--worker-id", 0);
  int num_workers = get_arg_int(argc, argv, "--num-workers", 1);
  if (num_workers < 1) num_workers = 1;
  if (worker_id < 0) worker_id = 0;
  if (worker_id >= num_workers) worker_id = num_workers - 1;

  int row_start = (N * worker_id) / num_workers;
  int row_end = (N * (worker_id + 1)) / num_workers;
  int span = row_end - row_start;
  if (span < 0) span = 0;

  for (int i = row_start; i < row_end; i++) {
    for (int j = 0; j < N; j++) {
      A[i][j] = i + j;
      C[i][j] = 0;
    }
  }
  for (int i = 0; i < N; i++) {
    for (int j = 0; j < N; j++) {
      B[i][j] = i - j;
    }
  }

  SIT_RES_ON();

  for (int i = row_start; i < row_end; i++)
    for (int k = 0; k < N; k++)
      for (int j = 0; j < N; j++)
        C[i][j] += A[i][k] * B[k][j];

  uint64_t shard_mix = (uint64_t)(worker_id + 1);
  for (uint64_t i = 0; i < ((uint64_t)ACTIVE_BOOST * ITER); i++) {
    shard_mix = (shard_mix * 1103515245ULL + 12345ULL + i) ^ (shard_mix >> 13);
  }
  result ^= (int)shard_mix;

  if (BRANCH_MISPREDICT_ENABLED) {
    volatile int branch_acc = 0;
    for (int i = 0; i < ITER * 6; i++) {
      if ((i ^ (i >> 3) ^ ((worker_id + 1) * 7)) & 1) branch_acc += i;
      else branch_acc -= i;
    }
    result += branch_acc;
    SIT_STALL_ON();
    stall_phase((uint64_t)(span > 0 ? span : 1) * (uint64_t)N * 2ULL + (uint64_t)ITER);
    SIT_STALL_OFF();
  }

  idle_phase((uint64_t)ITER * 60ULL);

  if (CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase((uint64_t)(span > 0 ? span : 1) * (uint64_t)N * 4ULL + (uint64_t)ITER);
    SIT_STALL_OFF();
  }

  if (BRANCH_MISPREDICT_ENABLED && CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase((uint64_t)(span > 0 ? span : 1) * (uint64_t)N * 8ULL + (uint64_t)ITER);
    SIT_STALL_OFF();
  }

  SIT_RES_OFF();

  int tail = 0;
  if (row_end > row_start) {
    tail = C[row_end - 1][N - 1];
  }
  result ^= tail ^ span;
  return 0;
}
""",

    "matmul_shared": r"""
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define N DIM

#ifdef __riscv
#define SIT_RES_ON()  do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 101" ::: "memory"); \
} while(0)
#define SIT_RES_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 102" ::: "memory"); \
} while(0)
#define SIT_STALL_ON() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 103" ::: "memory"); \
} while(0)
#define SIT_STALL_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 104" ::: "memory"); \
} while(0)
#define SIT_IDLE_ON() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 105" ::: "memory"); \
} while(0)
#define SIT_IDLE_OFF() do { \
    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 106" ::: "memory"); \
} while(0)
#else
#define SIT_RES_ON()  ((void)0)
#define SIT_RES_OFF() ((void)0)
#define SIT_STALL_ON()  ((void)0)
#define SIT_STALL_OFF() ((void)0)
#define SIT_IDLE_ON()  ((void)0)
#define SIT_IDLE_OFF() ((void)0)
#endif

static int A[N][N];
static int B[N][N];
static int C[N][N];
static volatile uint64_t STALL_BUF[4096];
static volatile uint64_t stall_sink = 0;
static volatile int result = 0;

typedef struct {
  volatile int count;
  volatile int sense;
  int total;
} spin_barrier_t;

typedef struct {
  int worker_id;
  int num_workers;
  spin_barrier_t *init_barrier;
  spin_barrier_t *compute_barrier;
  int *checksums;
} worker_args_t;

static int get_arg_int(int argc, char **argv, const char *key, int defval) {
  for (int i = 1; i + 1 < argc; i++) {
    if (strcmp(argv[i], key) == 0) {
      return atoi(argv[i + 1]);
    }
  }
  return defval;
}

static inline void barrier_init(spin_barrier_t *barrier, int total) {
  barrier->count = 0;
  barrier->sense = 0;
  barrier->total = total > 0 ? total : 1;
}

static inline void barrier_wait(spin_barrier_t *barrier, int *local_sense) {
  *local_sense = !(*local_sense);
  int arrival = __sync_add_and_fetch(&barrier->count, 1);
  if (arrival == barrier->total) {
    __sync_synchronize();
    barrier->count = 0;
    barrier->sense = *local_sense;
  } else {
    while (barrier->sense != *local_sense) {
      __asm__ __volatile__("nop" ::: "memory");
    }
  }
}

static inline void idle_phase(uint64_t iterations) {
  __asm__ __volatile__("" ::: "memory");
  for (uint64_t i = 0; i < iterations; i++) {
#ifdef __riscv
    __asm__ __volatile__("nop" ::: "memory");
#else
    __asm__ __volatile__("" ::: "memory");
#endif
  }
}

static inline void stall_phase(uint64_t iterations) {
  for (uint64_t i = 0; i < iterations; i++) {
    uint64_t idx = (i * 2654435761ULL) & 4095ULL;
    stall_sink += STALL_BUF[idx];
    STALL_BUF[idx] = stall_sink + i;
  }
}

static void *worker_main(void *ptr) {
  worker_args_t *args = (worker_args_t *)ptr;
  int worker_id = args->worker_id;
  int num_workers = args->num_workers;
  int row_start = (N * worker_id) / num_workers;
  int row_end = (N * (worker_id + 1)) / num_workers;
  int span = row_end - row_start;
  if (span < 0) span = 0;
  int local_sense = 0;

  for (int i = row_start; i < row_end; i++) {
    for (int j = 0; j < N; j++) {
      A[i][j] = i + j;
      B[i][j] = i - j;
      C[i][j] = 0;
    }
  }

  barrier_wait(args->init_barrier, &local_sense);

  SIT_RES_ON();

  for (int i = row_start; i < row_end; i++) {
    for (int k = 0; k < N; k++) {
      for (int j = 0; j < N; j++) {
        C[i][j] += A[i][k] * B[k][j];
      }
    }
  }

  uint64_t shard_mix = (uint64_t)(worker_id + 1);
  for (uint64_t i = 0; i < ((uint64_t)ACTIVE_BOOST * ITER); i++) {
    shard_mix = (shard_mix * 1103515245ULL + 12345ULL + i) ^ (shard_mix >> 13);
  }

  SIT_IDLE_ON();
  barrier_wait(args->compute_barrier, &local_sense);
  SIT_IDLE_OFF();

  if (BRANCH_MISPREDICT_ENABLED) {
    volatile int branch_acc = 0;
    for (int i = 0; i < ITER * 6; i++) {
      if ((i ^ (i >> 3) ^ ((worker_id + 1) * 7)) & 1) branch_acc += i;
      else branch_acc -= i;
    }
    shard_mix ^= (uint64_t)branch_acc;
    SIT_STALL_ON();
    stall_phase((uint64_t)(span > 0 ? span : 1) * (uint64_t)N * 2ULL + (uint64_t)ITER);
    SIT_STALL_OFF();
  }

  idle_phase((uint64_t)ITER * 60ULL);

  if (CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase((uint64_t)(span > 0 ? span : 1) * (uint64_t)N * 4ULL + (uint64_t)ITER);
    SIT_STALL_OFF();
  }

  if (BRANCH_MISPREDICT_ENABLED && CACHE_PRESSURE_ENABLED) {
    SIT_STALL_ON();
    stall_phase((uint64_t)(span > 0 ? span : 1) * (uint64_t)N * 8ULL + (uint64_t)ITER);
    SIT_STALL_OFF();
  }

  SIT_RES_OFF();

  int tail = 0;
  if (row_end > row_start) {
    tail = C[row_end - 1][N - 1];
  }
  args->checksums[worker_id] = tail ^ (int)shard_mix ^ span;
  return NULL;
}

int main(int argc, char **argv) {
  int num_threads = get_arg_int(argc, argv, "--num-threads", 1);
  if (num_threads < 1) num_threads = 1;

  pthread_t *threads = (pthread_t *)calloc((size_t)num_threads, sizeof(pthread_t));
  worker_args_t *args = (worker_args_t *)calloc((size_t)num_threads, sizeof(worker_args_t));
  int *checksums = (int *)calloc((size_t)num_threads, sizeof(int));
  if (!threads || !args || !checksums) {
    return 2;
  }

  spin_barrier_t init_barrier;
  spin_barrier_t compute_barrier;
  barrier_init(&init_barrier, num_threads);
  barrier_init(&compute_barrier, num_threads);

  for (int i = 0; i < num_threads; i++) {
    args[i].worker_id = i;
    args[i].num_workers = num_threads;
    args[i].init_barrier = &init_barrier;
    args[i].compute_barrier = &compute_barrier;
    args[i].checksums = checksums;
  }

  for (int i = 1; i < num_threads; i++) {
    if (pthread_create(&threads[i], NULL, worker_main, &args[i]) != 0) {
      return 2;
    }
  }

  worker_main(&args[0]);

  for (int i = 1; i < num_threads; i++) {
    pthread_join(threads[i], NULL);
  }

  for (int i = 0; i < num_threads; i++) {
    result ^= checksums[i];
  }

  free(threads);
  free(args);
  free(checksums);
  return 0;
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_combined_sha256(named_hashes: dict[str, str]) -> str:
    h = hashlib.sha256()
    for k in sorted(named_hashes.keys()):
        h.update(k.encode("utf-8"))
        h.update(b":")
        h.update(named_hashes[k].encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def resolve_repo_commit(repo: Path) -> str:
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    if p.returncode == 0:
        out = (p.stdout or "").strip()
        if out:
            return out
    return "unknown"


def resolve_tool_version(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
    except Exception:
        return "unknown"
    text = (p.stdout or "") + "\n" + (p.stderr or "")
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return first if first else "unknown"


def resolve_gem5_binary(gem5_bin: str) -> str:
    found = shutil.which(gem5_bin)
    if found:
        return found
    if Path(gem5_bin).exists():
        return str(Path(gem5_bin).resolve())
    raise SystemExit(f"gem5 binary not found: {gem5_bin}")


def resolve_qemu_binary(qemu_bin: str) -> str:
    found = shutil.which(qemu_bin)
    if found:
        return found
    if Path(qemu_bin).exists():
        return str(Path(qemu_bin).resolve())
    raise SystemExit(f"qemu binary not found: {qemu_bin}")


def validate_workload_arg(target: str, workload: str) -> None:
    if not str(workload).strip():
        raise SystemExit("--workload must be a non-empty label")
    if workload == "all":
        return
    if target == "tt_wormhole":
        return
    canonical = canonicalize_workload_name(workload)
    if target == "cpu" and canonical not in WORKLOADS_CPU:
        raise SystemExit(f"cpu does not support: {workload}")
    if target == "spike" and canonical not in WORKLOADS_SPIKE:
        raise SystemExit(f"spike does not support: {workload}")
    if target == "gem5" and canonical not in WORKLOADS_GEM5:
        raise SystemExit(f"gem5 does not support: {workload}")
    if target == "qemu" and canonical not in WORKLOADS_QEMU:
        raise SystemExit(f"qemu does not support: {workload}")


def resolve_requested_cores(requested: int | None) -> int:
    if requested is None:
        return 1
    try:
        cores = int(requested)
    except Exception as exc:
        raise SystemExit(f"invalid --cores value: {requested}") from exc
    return max(1, cores)


def parse_cpu_type_list(spec: str) -> list[str]:
    return [tok.strip() for tok in str(spec).split(",") if tok.strip()]


def resolve_gem5_cpu_type_plan(
    default_cpu_type: str,
    cpu_types_spec: str,
    requested_cores: int,
    cores_explicit: bool,
) -> list[str]:
    if not str(cpu_types_spec).strip():
        return [str(default_cpu_type)] * max(1, int(requested_cores))

    cpu_types = parse_cpu_type_list(cpu_types_spec)
    if not cpu_types:
        raise SystemExit("--gem5-cpu-types must contain at least one CPU type")

    if cores_explicit:
        if len(cpu_types) == 1:
            return cpu_types * max(1, int(requested_cores))
        if len(cpu_types) != int(requested_cores):
            raise SystemExit(
                f"--gem5-cpu-types count ({len(cpu_types)}) must match --cores ({requested_cores})"
            )
        return cpu_types

    return cpu_types


def build_gem5_mix_suffix(cpu_types: list[str]) -> str:
    uniq = list(dict.fromkeys(cpu_types))
    if len(uniq) <= 1:
        return ""
    joined = "-".join(cpu_types)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", joined).strip("-").lower()
    if not slug:
        slug = "mixed"
    if len(slug) > 48:
        slug = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]
    return f"__mix-{slug}"


def workload_needs_pthread(workload: str) -> bool:
    return workload == "matmul_shared"


def resolve_sim_work_units(
    workload: str,
    size: str,
    preset: dict,
    sim_ops_per_zone: int | None = None,
) -> int:
    canonical = canonicalize_workload_name(workload)
    active_boost = resolve_size_active_boost(size)
    if active_boost is None:
        return 0
    if canonical in {"matmul_multicore", "matmul_shared"}:
        return 0
    active_boost = max(1, int(active_boost))
    effective_ops_per_zone = sim_ops_per_zone
    if effective_ops_per_zone is None:
        auto_ops_per_zone = resolve_auto_ops_per_zone(canonical)
        if auto_ops_per_zone is not None:
            effective_ops_per_zone = int(auto_ops_per_zone)
    if effective_ops_per_zone is not None:
        return active_boost * max(0, int(effective_ops_per_zone))
    return active_boost


def resolve_tt_total_work_units(size: str, ops_per_zone: float) -> float | None:
    active_boost = resolve_size_active_boost(size)
    if active_boost is None:
        return None
    return max(1, int(active_boost)) * float(ops_per_zone)


def total_resident_us_from_csv(resid_csv: Path) -> float:
    total = 0.0
    with open(resid_csv, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                start_us = float(row["start_us"])
                end_us = float(row["end_us"])
            except (KeyError, TypeError, ValueError):
                continue
            total += max(0.0, end_us - start_us)
    return total


def total_work_done_from_state_csv(state_csv: Path) -> float:
    total = 0.0
    with open(state_csv, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                total += float(row.get("work_done") or 0.0)
            except (TypeError, ValueError):
                continue
    return total


def load_key_value_text(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def resolve_tt_expected_work_rate(
    size: str,
    ops_per_zone: float,
    resid_csv: Path,
    state_csv: Path | None = None,
    workload: str = "",
    chip_freq_mhz: float | None = None,
) -> float | None:
    # Legacy per-run normalization: expected = (zone_count × ops_per_zone) / measured resident_us.
    # Publication-quality reference plots should use an external or cohort-derived ideal ceiling instead.
    resident_us = total_resident_us_from_csv(resid_csv)
    if resident_us <= 0.0:
        return None
    total_work_units = resolve_tt_total_work_units(size, ops_per_zone)
    if total_work_units is None:
        return None
    return total_work_units / resident_us


def derive_tt_work_audit(
    size: str,
    ops_per_zone: float,
    state_csv: Path,
    adapter_debug_summary: Path | None = None,
) -> dict[str, object]:
    observed_work_total = total_work_done_from_state_csv(state_csv)
    active_boost = resolve_size_active_boost(size)
    expected_work_total = None
    effective_zone_count = None
    effective_ops_per_zone = None
    zone_count_ratio = None
    warning = None

    if active_boost is not None and active_boost > 0:
        expected_work_total = float(active_boost) * float(ops_per_zone)
        effective_ops_per_zone = observed_work_total / float(active_boost)
    if float(ops_per_zone) > 0.0:
        effective_zone_count = observed_work_total / float(ops_per_zone)
    if active_boost is not None and active_boost > 0 and effective_zone_count is not None:
        zone_count_ratio = effective_zone_count / float(active_boost)
        if abs(zone_count_ratio - 1.0) > 0.05:
            warning = (
                f"TT effective zone count {effective_zone_count:.3f} differs from ACTIVE_BOOST "
                f"{active_boost} by {((zone_count_ratio - 1.0) * 100.0):.1f}%."
            )

    raw_observed_work_total = None
    raw_effective_zone_count = None
    raw_zone_count_ratio = None
    raw_work_scale_factor = None
    normalization_applied = None
    raw_warning = None
    if adapter_debug_summary is not None:
        debug_values = load_key_value_text(adapter_debug_summary)
        try:
            raw_observed_work_total = float(debug_values.get("raw_total_work", "nan"))
        except ValueError:
            raw_observed_work_total = None
        try:
            raw_effective_zone_count = float(debug_values.get("raw_zone_equivalent", "nan"))
        except ValueError:
            raw_effective_zone_count = None
        try:
            raw_work_scale_factor = float(debug_values.get("work_scale_factor", "nan"))
        except ValueError:
            raw_work_scale_factor = None
        raw_norm_flag = str(debug_values.get("normalization_applied", "")).strip().lower()
        if raw_norm_flag in {"true", "false"}:
            normalization_applied = raw_norm_flag == "true"
        if active_boost is not None and active_boost > 0 and raw_effective_zone_count is not None:
            raw_zone_count_ratio = raw_effective_zone_count / float(active_boost)
            if abs(raw_zone_count_ratio - 1.0) > 0.05:
                raw_warning = (
                    f"TT raw throughput-zone count {raw_effective_zone_count:.3f} differs from ACTIVE_BOOST "
                    f"{active_boost} by {((raw_zone_count_ratio - 1.0) * 100.0):.1f}% before normalization."
                )
                if raw_work_scale_factor is not None:
                    raw_warning += f" Applied work scale factor {raw_work_scale_factor:.6f}."
        if raw_warning:
            warning = raw_warning

    return {
        "observed_work_total": observed_work_total,
        "expected_tile_count": active_boost,
        "configured_ops_per_zone": float(ops_per_zone),
        "expected_work_total_from_tiles": expected_work_total,
        "effective_zone_count": effective_zone_count,
        "effective_ops_per_zone_from_trace": effective_ops_per_zone,
        "zone_count_ratio_vs_active_boost": zone_count_ratio,
        "raw_observed_work_total": raw_observed_work_total,
        "raw_effective_zone_count": raw_effective_zone_count,
        "raw_zone_count_ratio_vs_active_boost": raw_zone_count_ratio,
        "raw_work_scale_factor": raw_work_scale_factor,
        "normalization_applied": normalization_applied,
        "warning": warning,
    }


def apply_target_defaults(args: argparse.Namespace) -> None:
    auto_ops_per_zone = resolve_auto_ops_per_zone(args.workload)
    gem5_stats_mode = (
        args.target == "gem5"
        and str(getattr(args, "gem5_adapter_mode", "exec")).strip() == "stats"
    )

    if args.target == "tt_wormhole":
        if args.time_us is None:
            args.time_us = DEFAULT_TT_WINDOW_US
        if args.tt_residency_model is None:
            args.tt_residency_model = DEFAULT_TT_RESIDENCY_MODEL
        if args.tt_strict_pairing is None:
            args.tt_strict_pairing = DEFAULT_TT_STRICT
        if args.tt_strict_map_hit is None:
            args.tt_strict_map_hit = DEFAULT_TT_STRICT
        if args.tt_ops_per_zone is None:
            args.tt_ops_per_zone = auto_ops_per_zone if auto_ops_per_zone is not None else DEFAULT_TT_OPS_PER_ZONE
        return

    if args.time_us is None:
        args.time_us = DEFAULT_WINDOW_US
    if gem5_stats_mode:
        # gem5 stats mode is a pure interval-classification path; it should
        # not inherit TT-style work-rate normalization.
        args.expected_work_rate = None
        args.sim_ops_per_zone = None
        if getattr(args, "no_work_sit_mode", None) is None:
            args.no_work_sit_mode = "window_active"
    sim_trace_only = bool(getattr(args, "sim_trace_only", False))
    if not gem5_stats_mode and not sim_trace_only and args.sim_ops_per_zone is None and auto_ops_per_zone is not None:
        args.sim_ops_per_zone = int(auto_ops_per_zone)
    if sim_trace_only:
        # Trace-only simulator runs intentionally avoid synthetic work_done so
        # SIT is derived directly from the classified residency timeline.
        args.expected_work_rate = None
        if getattr(args, "no_work_sit_mode", None) is None:
            args.no_work_sit_mode = "window_active"
    elif not gem5_stats_mode and args.expected_work_rate is None:
        _preset = resolve_size_preset(str(getattr(args, "workload_size", ""))) or {}
        _canonical = canonicalize_workload_name(getattr(args, "workload", ""))
        _sim_work = resolve_sim_work_units(
            _canonical, str(getattr(args, "workload_size", "")), _preset,
            sim_ops_per_zone=args.sim_ops_per_zone,
        )
        if _sim_work > 0 and float(args.time_us) > 0.0:
            args.expected_work_rate = float(_sim_work) / float(args.time_us)
        else:
            args.expected_work_rate = DEFAULT_EXPECTED_WORK_RATE
    if args.tt_residency_model is None:
        args.tt_residency_model = "kernel_envelope"
    if args.tt_strict_pairing is None:
        args.tt_strict_pairing = False
    if args.tt_strict_map_hit is None:
        args.tt_strict_map_hit = False


def inject_work_marker(code: str, work_units: int) -> str:
    total_work_units = max(0, int(work_units))
    if total_work_units <= 0:
        return code

    marker_insns: list[str] = []
    remaining = total_work_units
    while remaining > 0:
        chunk = min(remaining, 1023)
        marker_imm = encode_work_units_to_imm(chunk)
        marker_insns.append(
            f'    __asm__ __volatile__(".insn i 0x13, 0, x0, x0, {marker_imm}" ::: "memory");'
        )
        remaining -= chunk

    marker_body = "\n".join(marker_insns)
    support_block = f"""
#ifndef SIT_EMIT_WORK_MARKER_DEFINED
#define SIT_EMIT_WORK_MARKER_DEFINED 1
#ifdef __riscv
static __attribute__((noinline)) void sit_emit_work_marker(void) {{
{marker_body}
}}
#else
static inline void sit_emit_work_marker(void) {{ }}
#endif
#endif
"""

    lines = code.splitlines()
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("#include "):
            insert_idx = i + 1
        else:
            if insert_idx > 0:
                break
    lines.insert(insert_idx, support_block.rstrip("\n"))
    code = "\n".join(lines) + "\n"

    code, n = re.subn(
        r"(?m)^(\s*)SIT_RES_OFF\(\);\s*$",
        r"\1sit_emit_work_marker();\n\1SIT_RES_OFF();",
        code,
        count=1,
    )
    if n == 0:
        raise SystemExit("Failed to inject work marker: missing SIT_RES_OFF()")
    return code


def build_gem5_process_plan(
    workload: str,
    binpath: Path,
    cores: int,
) -> tuple[int, str, str | None, bool, str]:
    cores = max(1, int(cores))
    if cores > 1 and workload not in {"matmul_multicore", "matmul_shared"}:
        raise SystemExit(
            "--cores > 1 for gem5 currently requires --workload matmul_multicore "
            "or --workload matmul_shared so work can be split across CPUs."
        )

    if workload == "matmul_multicore":
        cmd_spec = ";".join([str(binpath)] * cores)
        option_spec = ";".join(
            f"--worker-id {worker_id} --num-workers {cores}"
            for worker_id in range(cores)
        )
        return cores, cmd_spec, option_spec, cores > 1, "process_sharded"

    if workload == "matmul_shared":
        option_spec = f"--num-threads {cores}"
        return cores, str(binpath), option_spec, False, "shared_threads"

    return 1, str(binpath), None, False, "single_process"

def resolve_gem5_config(gem5_bin_path: str, gem5_root: str = "", explicit_config: str | None = None) -> Path:
    if explicit_config:
        cfg = Path(explicit_config).expanduser().resolve()
        if cfg.exists():
            return cfg
        raise SystemExit(f"gem5 config not found: {cfg}")

    candidates: list[Path] = []
    if gem5_root:
        root = Path(gem5_root).expanduser().resolve()
        candidates += [
            root / "configs" / "deprecated" / "example" / "se.py",
            root / "configs" / "example" / "se.py",
        ]

    gem5_path = Path(gem5_bin_path).resolve()
    candidates += [
        gem5_path.parent.parent / "configs" / "deprecated" / "example" / "se.py",
        gem5_path.parent.parent / "configs" / "example" / "se.py",
        Path("/usr/share/gem5/configs/deprecated/example/se.py"),
        Path("/usr/share/gem5/configs/example/se.py"),
    ]

    for cand in candidates:
        if cand.exists():
            return cand

    raise SystemExit(
        "Could not find gem5 se.py config. Pass --gem5-config or --gem5-root."
    )

def _inject_unified_workload_phases(
    code: str,
    preset: dict,
    branch_mispredict: bool,
    cache_pressure: bool,
    workload: str,
) -> str:
    """
    Inject marker-driven IDLE/STALL phases into every workload so all targets
    observe consistent runtime behavior:
      none: includes an explicit IDLE phase
      branch: extra branch-pressure STALL phase
      cache: stronger cache-pressure STALL phase
      both: strongest combined STALL phase
    """
    iter_base = int(preset.get("ITER", 1000))
    unit = max(iter_base // 6, 64)
    idle_iters = unit * 6
    # Keep ordering pressure strong across workloads:
    # none > branch > cache > both (SIT decreases as pressure increases).
    branch_iters = unit * 8
    cache_iters = unit * 16
    both_iters = unit * 96
    if workload in {"matmul", "matmul_multicore", "matmul_shared"}:
        # Matmul is compute-dense; strengthen synthetic perturbation so
        # monotonic ordering remains visible in reduced-matrix checks.
        branch_iters = unit * 256
        cache_iters = unit * 2048
        both_iters = unit * 1536

    support_block = f"""
#ifndef BRANCH_MISPREDICT_ENABLED
#define BRANCH_MISPREDICT_ENABLED {1 if branch_mispredict else 0}
#endif
#ifndef CACHE_PRESSURE_ENABLED
#define CACHE_PRESSURE_ENABLED {1 if cache_pressure else 0}
#endif

#ifndef SIT_STALL_ON
#ifdef __riscv
#define SIT_STALL_ON() do {{ __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 103" ::: "memory"); }} while(0)
#define SIT_STALL_OFF() do {{ __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 104" ::: "memory"); }} while(0)
#else
#define SIT_STALL_ON() ((void)0)
#define SIT_STALL_OFF() ((void)0)
#endif
#endif

#ifndef SIT_IDLE_ON
#ifdef __riscv
#define SIT_IDLE_ON() do {{ __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 105" ::: "memory"); }} while(0)
#define SIT_IDLE_OFF() do {{ __asm__ __volatile__(".insn i 0x13, 0, x0, x0, 106" ::: "memory"); }} while(0)
#else
#define SIT_IDLE_ON() ((void)0)
#define SIT_IDLE_OFF() ((void)0)
#endif
#endif

static volatile uint64_t sit_injected_stall_buf[1024];

static inline void sit_injected_stall_phase(uint64_t iterations) {{
    uint64_t acc = 0;
    for (uint64_t i = 0; i < iterations; i++) {{
        uint64_t idx = (i * 2654435761ULL) & 1023ULL;
        acc += sit_injected_stall_buf[idx];
        sit_injected_stall_buf[idx] = acc + i;
    }}
}}

static inline void sit_injected_idle_phase(uint64_t iterations) {{
    for (uint64_t i = 0; i < iterations; i++) {{
#ifdef __riscv
        __asm__ __volatile__("nop" ::: "memory");
#else
        __asm__ __volatile__("" ::: "memory");
#endif
    }}
}}

static __attribute__((noinline)) void sit_emit_idle_on(void) {{ SIT_IDLE_ON(); }}
static __attribute__((noinline)) void sit_emit_idle_off(void) {{ SIT_IDLE_OFF(); }}
static __attribute__((noinline)) void sit_emit_stall_on(void) {{ SIT_STALL_ON(); }}
static __attribute__((noinline)) void sit_emit_stall_off(void) {{ SIT_STALL_OFF(); }}
"""

    lines = code.splitlines()
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("#include "):
            insert_idx = i + 1
        else:
            if insert_idx > 0:
                break
    lines.insert(insert_idx, support_block.rstrip("\n"))
    code = "\n".join(lines) + "\n"

    inject_block = (
        f"\\1/* Unified workload-controlled phases for consistent flag ordering */\n"
        f"\\1sit_emit_idle_on();\n"
        f"\\1sit_injected_idle_phase({idle_iters}ULL);\n"
        f"\\1sit_emit_idle_off();\n"
        f"\\1if (BRANCH_MISPREDICT_ENABLED) {{\n"
        f"\\1  sit_emit_stall_on();\n"
        f"\\1  sit_injected_stall_phase({branch_iters}ULL);\n"
        f"\\1  sit_emit_stall_off();\n"
        f"\\1}}\n"
        f"\\1if (CACHE_PRESSURE_ENABLED) {{\n"
        f"\\1  sit_emit_stall_on();\n"
        f"\\1  sit_injected_stall_phase({cache_iters}ULL);\n"
        f"\\1  sit_emit_stall_off();\n"
        f"\\1}}\n"
        f"\\1if (BRANCH_MISPREDICT_ENABLED && CACHE_PRESSURE_ENABLED) {{\n"
        f"\\1  sit_emit_stall_on();\n"
        f"\\1  sit_injected_stall_phase({both_iters}ULL);\n"
        f"\\1  sit_emit_stall_off();\n"
        f"\\1}}\n"
        f"\\1SIT_RES_OFF();"
    )
    code, n = re.subn(r"(?m)^(\s*)SIT_RES_OFF\(\);", inject_block, code, count=1)
    if n == 0:
        raise SystemExit("Failed to inject unified workload phases: missing SIT_RES_OFF()")
    return code


def _strip_conditioned_phase_blocks(code: str, conditions: tuple[str, ...]) -> str:
    lines = code.splitlines()
    kept: list[str] = []
    skip_depth = 0

    for line in lines:
        stripped = line.strip()
        if skip_depth > 0:
            skip_depth += line.count("{") - line.count("}")
            if skip_depth <= 0:
                skip_depth = 0
            continue

        matched_condition = next((cond for cond in conditions if stripped.startswith(cond)), None)
        if matched_condition is not None:
            brace_delta = line.count("{") - line.count("}")
            if brace_delta > 0:
                skip_depth = brace_delta
            continue

        kept.append(line)

    return "\n".join(kept) + "\n"


def _strip_simulator_baseline_phases(code: str, keep_conditioned_phases: bool = False) -> str:
    if not keep_conditioned_phases:
        code = _strip_conditioned_phase_blocks(
            code,
            (
                "if (BRANCH_MISPREDICT_ENABLED && CACHE_PRESSURE_ENABLED)",
                "if (CACHE_PRESSURE_ENABLED)",
                "if (BRANCH_MISPREDICT_ENABLED)",
            ),
        )

    phase_line_patterns = [
        re.compile(r"^\s*idle_phase\s*\([^;]*\);\s*(?://.*)?$"),
        re.compile(r"^\s*SIT_IDLE_ON\(\);\s*(?://.*)?$"),
        re.compile(r"^\s*SIT_IDLE_OFF\(\);\s*(?://.*)?$"),
        re.compile(r"^\s*barrier_wait\s*\(\s*args->compute_barrier\s*,\s*&local_sense\s*\);\s*$"),
    ]
    if not keep_conditioned_phases:
        phase_line_patterns.extend(
            (
                re.compile(r"^\s*stall_phase\s*\([^;]*\);\s*(?://.*)?$"),
                re.compile(r"^\s*SIT_STALL_ON\(\);\s*(?://.*)?$"),
                re.compile(r"^\s*SIT_STALL_OFF\(\);\s*(?://.*)?$"),
            )
        )

    kept: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if any(pattern.match(stripped) for pattern in phase_line_patterns):
            continue
        kept.append(line)

    return "\n".join(kept) + "\n"

def write_workload(build_dir: Path, workload: str, size: str, 
                   branch_mispredict: bool = False,
                   cache_pressure: bool = False,
                   baseline_case: bool = True,
                   sim_ops_per_zone: int | None = None,
                   emit_work_markers: bool = True) -> Path:
    """Generate C workload, defaulting simulator runs to baseline execution."""
    canonical = canonicalize_workload_name(workload)
    preset = resolve_size_preset(size)
    if preset is None:
        raise SystemExit(f"unsupported workload_size for generated workload: {size}")
    code = SRC[canonical]
    
    code = code.replace("ITER", str(preset["ITER"]))
    code = code.replace("DIM", str(preset["DIM"]))
    code = code.replace("ACTIVE_BOOST", str(preset["ACTIVE_BOOST"]))
    #code = code.replace("PAGES", str(preset["PAGES"]))

    # Some legacy templates model cache pressure via a fixed unmapped address
    # (0x80000000), which segfaults in qemu user-mode and can break gem5 SE.
    # Replace with a safe local buffer while preserving memory-access behavior.
    code = code.replace(
        "volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);",
        "static volatile uint64_t SAFE_STALL_BUF[4096];\n"
        "    volatile uint64_t* ptr = SAFE_STALL_BUF;",
    )

    if baseline_case:
        code = _strip_simulator_baseline_phases(
            code,
            keep_conditioned_phases=bool(branch_mispredict or cache_pressure),
        )
    elif canonical != "matmul_shared":
        code = _inject_unified_workload_phases(
            code,
            preset=preset,
            branch_mispredict=branch_mispredict,
            cache_pressure=cache_pressure,
            workload=canonical,
        )

    code = code.replace("BRANCH_MISPREDICT_ENABLED", "1" if branch_mispredict else "0")
    code = code.replace("CACHE_PRESSURE_ENABLED", "1" if cache_pressure else "0")
    if emit_work_markers:
        code = inject_work_marker(code, resolve_sim_work_units(canonical, size, preset, sim_ops_per_zone=sim_ops_per_zone))

    # Keep templates robust: some workloads use uint64_t and may miss the include.
    if "uint64_t" in code and "#include <stdint.h>" not in code:
        code = '#include <stdint.h>\n' + code
    
    cpath = build_dir / f"{workload}.c"
    cpath.write_text(code)
    return cpath

def find_repo_root() -> Path:
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent,
        Path.cwd().parent,
    ]
    for candidate in candidates:
        if (candidate / "result_handler" / "cli.py").exists() and (candidate / "sit_classifier" / "adapters").is_dir():
            return candidate
    return Path(__file__).resolve().parent.parent

def main():
    ap = argparse.ArgumentParser(prog="riscvbench")
    
    ap.add_argument("--target", default="cpu", choices=["spike", "cpu", "gem5", "qemu", "tt_wormhole", "both"])
    ap.add_argument(
        "--workload",
        default="fm_mm",
        help=(
            "Workload label. Standard targets accept: "
            + ", ".join(sorted(WORKLOADS_ALL_STANDARD))
            + ". Use 'all' for sweep mode. tt_wormhole accepts any non-empty label."
        ),
    )
    ap.add_argument(
        "--workload_size",
        default="small",
        type=parse_workload_size,
        help="Workload size preset. Supports built-in sizes, tt_<N>tile, and tt_m<M>_n<N>_k<K> sweep labels.",
    )
    
    ap.add_argument(
        "--branch-mispredict",
        action="store_true",
        help=(
            "Inject synthetic control-flow perturbations to create workload-level stall/idle "
            "segments for SIT sensitivity tests. In this bundle, baseline simulator mode "
            "still honors workload-native branch-conditioned phases when this flag is set."
        ),
    )
    ap.add_argument(
        "--cache-pressure",
        action="store_true",
        help=(
            "Inject synthetic memory-pressure patterns to create workload-level stall/idle "
            "segments for SIT sensitivity tests. In this bundle, baseline simulator mode "
            "still honors workload-native cache-conditioned phases when this flag is set."
        ),
    )
    ap.add_argument(
        "--inject-sim-phases",
        action="store_true",
        help="Opt back into the legacy synthetic idle/stall simulator phases and flag-driven perturbations.",
    )
    ap.add_argument(
        "--sim-ops-per-zone",
        type=int,
        default=None,
        help="Optional simulator work scale. Defaults to a TT-calibrated per-workload ops_per_zone when available.",
    )
    ap.add_argument(
        "--sim-classification-mode",
        choices=["strict", "compute_biased"],
        default="strict",
        help="Simulator trace classification policy: strict treats memory traffic as stall, compute_biased counts plain loads/stores as compute-like activity.",
    )
    ap.add_argument(
        "--sim-trace-only",
        action="store_true",
        help="For spike/qemu/gem5, skip synthetic work_done markers and derive SIT only from the classified trace timeline.",
    )
    
    ap.add_argument(
        "--time_us",
        default=None,
        type=float,
        help="SIT window size in us (defaults to 32 for tt_wormhole, else 256)",
    )
    ap.add_argument(
        "--expected-work-rate",
        type=float,
        default=None,
        help="Expected work rate for SIT normalization. If omitted, tt_wormhole falls back to a legacy same-run resident-time normalization; publication plots should override this with an external reference.",
    )
    ap.add_argument(
        "--no-work-sit-mode",
        choices=["global_active", "window_active"],
        default=None,
        help="Fallback SIT mode when work_done is unavailable (defaults to window_active for --sim-trace-only runs, else global_active).",
    )
    ap.add_argument("--skip-post-processing", action="store_true")
    ap.add_argument("--practical", action="store_true")
    ap.add_argument("--debug-sit", action="store_true")
    
    ap.add_argument("--cores", type=int, default=None)
    ap.add_argument("--isa", default="RV64GC")
    ap.add_argument("--spike-bin", default=os.environ.get("SPIKE_BIN", "spike"))
    ap.add_argument("--spike-cc", default=os.environ.get("SPIKE_CC", "riscv64-unknown-elf-gcc"))
    ap.add_argument("--pk", default=str(Path.home() / "opt" / "riscv" / "riscv64-unknown-elf" / "bin" / "pk"))
    ap.add_argument("--inst_us", type=float, default=1.0)
    ap.add_argument("--resident_pc_ge", default="0x80000000")
    ap.add_argument("--gem5-bin", default=os.environ.get("GEM5_BIN", "gem5.opt"))
    ap.add_argument("--gem5-root", default=os.environ.get("GEM5_ROOT", ""))
    ap.add_argument("--gem5-config", default=None, help="Path to gem5 se.py config")
    ap.add_argument("--gem5-extra-args", default="", help="Extra args passed to gem5 after se.py")
    ap.add_argument("--gem5-cc", default=os.environ.get("GEM5_CC", "riscv64-linux-gnu-gcc"))
    ap.add_argument("--gem5-cpu-type", default="TimingSimpleCPU")
    ap.add_argument(
        "--gem5-cpu-types",
        default="",
        help="Optional comma-separated per-CPU gem5 CPU types, e.g. TimingSimpleCPU,MinorCPU",
    )
    ap.add_argument("--gem5-mem-size", default="512MB")
    ap.add_argument("--gem5-adapter-mode", default="exec", choices=["stats", "exec"])
    ap.add_argument("--gem5-stats-period-us", type=float, default=1.0)
    ap.add_argument("--gem5-ipc-active-thresh", type=float, default=0.24)
    ap.add_argument("--gem5-stall-miss-thresh", type=float, default=0.05)
    ap.add_argument("--gem5-l1-resident-thresh", type=float, default=0.8)
    ap.add_argument("--gem5-mem-reqs-per-inst-thresh", type=float, default=0.08)
    ap.add_argument("--gem5-idle-inst-thresh", type=float, default=0.0)
    ap.add_argument("--qemu-bin", default=os.environ.get("QEMU_BIN", "qemu-riscv64"))
    ap.add_argument("--qemu-cc", default=os.environ.get("QEMU_CC", "riscv64-linux-gnu-gcc"))
    ap.add_argument("--qemu-extra-args", default="", help="Extra args passed to qemu before program path")
    ap.add_argument(
        "--allow-nonzero-exit",
        action="store_true",
        help="Allow non-zero workload exit codes for qemu target (default: fail on non-zero)",
    )
    ap.add_argument("--tt-profile-csv", default=None, help="tt_wormhole input: profile_log_device.csv")
    ap.add_argument("--tt-zone-log", default=None, help="tt_wormhole input: zone_src_locations.log")
    ap.add_argument(
        "--tt-output-mode",
        default="tile",
        choices=["lane", "tile"],
        help="tt_wormhole adapter output mode (tile default for SIT, lane for debug)",
    )
    ap.add_argument("--tt-chip-freq-mhz", type=int, default=None, help="tt_wormhole optional CHIP_FREQ override")
    ap.add_argument("--tt-strict-pairing", dest="tt_strict_pairing", action="store_true", help="tt_wormhole: fail on unmatched start/end (default)")
    ap.add_argument("--tt-no-strict-pairing", dest="tt_strict_pairing", action="store_false", help="tt_wormhole: allow unmatched start/end")
    ap.add_argument("--tt-strict-map-hit", dest="tt_strict_map_hit", action="store_true", help="tt_wormhole: fail on zone-map misses (default)")
    ap.add_argument("--tt-no-strict-map-hit", dest="tt_strict_map_hit", action="store_false", help="tt_wormhole: allow zone-map misses")
    ap.add_argument("--tt-ops-per-zone", type=float, default=None, help="tt_wormhole work_done units per explicit throughput zone (defaults to 1024)")
    ap.add_argument(
        "--tt-residency-model",
        default=None,
        choices=["kernel_envelope", "active_span"],
        help="tt_wormhole residency model (defaults to active_span)",
    )

    ap.set_defaults(tt_strict_pairing=None, tt_strict_map_hit=None)
    args = ap.parse_args()
    validate_workload_arg(args.target, args.workload)
    apply_target_defaults(args)
    if args.no_work_sit_mode is None:
        args.no_work_sit_mode = "global_active"
    requested_cores = resolve_requested_cores(args.cores)
    simulator_baseline_case = args.target in {"cpu", "spike", "qemu", "gem5"} and not args.inject_sim_phases
    branch_mispredict_enabled = bool(args.branch_mispredict)
    cache_pressure_enabled = bool(args.cache_pressure)
    gem5_cpu_type_plan = [str(args.gem5_cpu_type)]
    if args.target == "gem5":
        gem5_cpu_type_plan = resolve_gem5_cpu_type_plan(
            default_cpu_type=str(args.gem5_cpu_type),
            cpu_types_spec=str(args.gem5_cpu_types),
            requested_cores=requested_cores,
            cores_explicit=args.cores is not None,
        )
        requested_cores = max(1, len(gem5_cpu_type_plan))
    if requested_cores > 1 and args.target != "gem5":
        raise SystemExit("--cores > 1 is currently supported only for --target gem5.")

    if args.target == "tt_wormhole":
        residency_desc = (
            "first-active..last-active per core (compute-oriented)"
            if args.tt_residency_model == "active_span"
            else "workload-owned kernel envelope"
        )
        print("\n=== TT WORMHOLE MODEL ===")
        print("Timing source: TT profiler ZONE_START/ZONE_END cycles")
        print("Semantics source: zone_src_locations pragma map")
        print(f"Residency: {residency_desc}")
        print("State inside residency: ACTIVE/STALL/IDLE from TT zone classification\n")
    else:
        print("\n=== CORRECT MODEL ===")
        print("Simulator baselines: no injected workload idle/stall phases")
        print("Values: from workload execution and adapter interpretation within residency\n")

        if simulator_baseline_case:
            print("ℹ Baseline simulator mode enabled: no extra synthetic phases are injected")
            if branch_mispredict_enabled:
                print("ℹ --branch-mispredict: preserve workload-native branch-conditioned stall behavior")
            if cache_pressure_enabled:
                print("ℹ --cache-pressure: preserve workload-native cache-conditioned stall behavior")
        else:
            print("ℹ Legacy injected simulator phases enabled")
            if branch_mispredict_enabled:
                print("ℹ --branch-mispredict: synthetic control-flow perturbation")
            if cache_pressure_enabled:
                print("ℹ --cache-pressure: synthetic memory-pressure pattern")
    if args.target == "gem5" and args.gem5_adapter_mode == "stats":
        print(
            "ℹ gem5 stats adapter infers state from IPC/cache counters; "
            "flag ordering can be non-monotonic vs marker-driven semantics."
        )
        print("ℹ Use --gem5-adapter-mode exec for marker-faithful sweep visualizations.")
    print()

    if args.target == "both" or args.workload == "all":
        if args.target == "tt_wormhole" and args.workload == "all":
            raise SystemExit("tt_wormhole target does not support --workload all; provide a single workload label for output pathing.")
        targets = ["spike", "cpu"] if args.target == "both" else [args.target]
        workloads = list(
            ["fm_loopback", "fm_mm", "fm_sparse", "fm_read", "fm_write"]
            if args.practical
            else sorted(WORKLOADS_ALL_STANDARD)
        )
        if args.workload != "all":
            workloads = [args.workload]

        for target in targets:
            for workload in workloads:
                cmd = [sys.executable, str(Path(__file__).resolve()),
                       "--target", target, "--workload", workload, "--workload_size", args.workload_size]
                if target == "spike":
                    cmd += ["--spike-bin", str(args.spike_bin), "--spike-cc", str(args.spike_cc), "--pk", str(args.pk), "--isa", str(args.isa)]
                if args.inject_sim_phases:
                    cmd += ["--inject-sim-phases"]
                if branch_mispredict_enabled:
                    cmd += ["--branch-mispredict"]
                if cache_pressure_enabled:
                    cmd += ["--cache-pressure"]
                print("$", " ".join(cmd))
                sh_allow_fail(cmd)
        return

    repo = find_repo_root()
    adapter_spike = repo / "sit_classifier" / "adapters" / "spike_adapter.py"
    adapter_gem5 = repo / "sit_classifier" / "adapters" / "gem5_adapter.py"
    adapter_qemu = repo / "sit_classifier" / "adapters" / "qemu_adapter.py"
    adapter_tt = repo / "sit_classifier" / "adapters" / "tt_wormhole_adapter.py"

    run_size_dir = args.workload_size
    if args.target == "gem5" and requested_cores > 1:
        run_size_dir = f"{args.workload_size}__c{requested_cores}"
    if args.target == "gem5":
        run_size_dir += build_gem5_mix_suffix(gem5_cpu_type_plan)
    run_dir = repo / "runs" / args.target / args.workload / run_size_dir
    build_dir = run_dir / "build"
    traces_dir = run_dir / "traces"
    inputs_dir = run_dir / "inputs"

    build_dir.mkdir(parents=True, exist_ok=True)
    traces_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    needs_baseline_ingest = True
    adapter_meta_base: dict[str, object] = {
        "adapter_name": "unknown",
        "adapter_mode": "unknown",
        "tool_version": "unknown",
        "repo_commit": resolve_repo_commit(repo),
        "inst_us": float(args.inst_us),
        "window_us": float(args.time_us),
        "thresholds": {},
        "allow_nonzero_exit": False,
        "input_trace_path": None,
        "requested_cores": requested_cores,
        "workload_sharded": False,
        "workload_parallel_mode": "single_process",
        "sim_trace_only": bool(args.sim_trace_only),
        "sim_classification_mode": str(args.sim_classification_mode),
    }

    if args.target == "spike":
        ensure_tool(args.spike_bin)
        ensure_tool(args.spike_cc)

        pk = Path(args.pk)
        if not pk.exists():
            raise SystemExit(f"pk not found: {pk}")

        cpath = write_workload(
            build_dir,
            args.workload,
            args.workload_size,
            branch_mispredict_enabled,
            cache_pressure_enabled,
            baseline_case=simulator_baseline_case,
            sim_ops_per_zone=args.sim_ops_per_zone,
            emit_work_markers=not args.sim_trace_only,
        )
        binpath = build_dir / args.workload

        sh([args.spike_cc, "-O0", "-static", "-march=rv64gc", "-mabi=lp64d",
            str(cpath), "-o", str(binpath)], cwd=build_dir)

        trace_path = traces_dir / "spike.trace"
        spike_cmd = [str(args.spike_bin), "-l"]
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
            "--resident-pc-ge", str(args.resident_pc_ge),
            "--classification-mode", str(args.sim_classification_mode)], cwd=repo, env=adapter_env)

        state_csv = inputs_dir / "state_intervals.csv"
        resid_csv = inputs_dir / "residency_intervals.csv"
        adapter_meta_base.update(
            {
                "adapter_name": "spike_adapter",
                "adapter_mode": "commit_log",
                "tool_version": resolve_tool_version([str(args.spike_bin), "--version"]),
                "thresholds": {"resident_pc_ge": str(args.resident_pc_ge)},
                "input_trace_path": str(trace_path),
            }
        )

    elif args.target == "gem5":
        gem5_bin = resolve_gem5_binary(args.gem5_bin)
        gem5_cfg = resolve_gem5_config(gem5_bin, args.gem5_root, args.gem5_config)
        gem5_hetero_cfg = repo / "configs" / "gem5_se_hetero.py"
        use_stats_adapter = args.gem5_adapter_mode == "stats"
        gem5_cpu_types = list(gem5_cpu_type_plan)
        gem5_primary_cpu_type = gem5_cpu_types[0]
        gem5_heterogeneous = len(set(gem5_cpu_types)) > 1
        if gem5_heterogeneous and not gem5_hetero_cfg.exists():
            raise SystemExit(f"Missing heterogeneous gem5 config: {gem5_hetero_cfg}")
        gem5_exec_cfg = gem5_hetero_cfg if gem5_heterogeneous else gem5_cfg
        gem5_cfg_runner = gem5_exec_cfg
        if use_stats_adapter:
            wrapper_cfg = repo / "configs" / "gem5_se_periodic_stats.py"
            if not wrapper_cfg.exists():
                raise SystemExit(f"Missing gem5 wrapper config: {wrapper_cfg}")
            gem5_cfg_runner = wrapper_cfg
        ensure_tool(args.gem5_cc)

        cpath = write_workload(
            build_dir,
            args.workload,
            args.workload_size,
            branch_mispredict_enabled,
            cache_pressure_enabled,
            baseline_case=simulator_baseline_case,
            sim_ops_per_zone=args.sim_ops_per_zone,
            emit_work_markers=not args.sim_trace_only,
        )
        binpath = build_dir / args.workload

        gem5_compile_cmd = [
            args.gem5_cc,
            "-O0",
            "-static",
            "-march=rv64gc",
            "-mabi=lp64d",
        ]
        if workload_needs_pthread(args.workload):
            gem5_compile_cmd.append("-pthread")
        gem5_compile_cmd += [
            str(cpath),
            "-o",
            str(binpath),
        ]
        sh(gem5_compile_cmd, cwd=build_dir)

        gem5_num_cpus, gem5_cmd_spec, gem5_option_spec, gem5_workload_sharded, gem5_parallel_mode = build_gem5_process_plan(
            workload=args.workload,
            binpath=binpath,
            cores=len(gem5_cpu_types),
        )
        if gem5_workload_sharded:
            print(f"ℹ gem5 sharding enabled: splitting {args.workload} across {gem5_num_cpus} CPUs")
        elif args.workload == "matmul_multicore":
            print("ℹ matmul_multicore using single-shard execution (--cores 1)")
        elif args.workload == "matmul_shared":
            print(f"ℹ gem5 shared workload enabled: one process with {gem5_num_cpus} pthread workers")
        if gem5_heterogeneous:
            print(f"ℹ gem5 heterogeneous CPU mix: {', '.join(gem5_cpu_types)}")

        trace_path = traces_dir / "gem5.trace"
        log_path = traces_dir / "gem5.log"
        m5out_dir = run_dir / "m5out"
        stats_path = m5out_dir / "stats.txt"
        m5out_dir.mkdir(parents=True, exist_ok=True)

        gem5_cmd = [gem5_bin, f"--outdir={m5out_dir}"]
        if not use_stats_adapter:
            gem5_cmd += ["--debug-flags=Exec", f"--debug-file={trace_path}"]
        gem5_cmd += [
            str(gem5_cfg_runner),
            f"--cmd={gem5_cmd_spec}",
            f"--cpu-type={gem5_primary_cpu_type}",
            f"--mem-size={args.gem5_mem_size}",
            f"--num-cpus={gem5_num_cpus}",
            "--caches",
        ]
        if gem5_option_spec:
            gem5_cmd.append(f"--options={gem5_option_spec}")
        if gem5_heterogeneous:
            gem5_cmd.append(f"--phase2-cpu-types={','.join(gem5_cpu_types)}")
            gem5_cmd += ["--phase2-base-se-script", str(gem5_cfg)]
        if use_stats_adapter:
            gem5_cmd += [
                "--phase2-se-script",
                str(gem5_exec_cfg),
                "--phase2-stats-period-us",
                str(args.gem5_stats_period_us),
            ]
        if args.gem5_extra_args.strip():
            gem5_cmd.extend(shlex.split(args.gem5_extra_args.strip()))

        print(f"ℹ Running: {' '.join(gem5_cmd)}\n")
        with open(log_path, "w") as gem5_out:
            p = subprocess.run(gem5_cmd, cwd=run_dir, stdout=gem5_out, stderr=subprocess.STDOUT)
        if p.returncode != 0:
            raise SystemExit(f"gem5 run failed (rc={p.returncode}). See {log_path}")

        if use_stats_adapter:
            if not stats_path.exists() or stats_path.stat().st_size == 0:
                raise SystemExit(f"gem5 stats file missing/empty: {stats_path}")
        else:
            if not trace_path.exists() or trace_path.stat().st_size == 0:
                raise SystemExit(f"gem5 trace empty: {trace_path}")

        adapter_env = dict(os.environ)
        adapter_env["PYTHONPATH"] = f"{repo}:{adapter_env.get('PYTHONPATH', '')}".rstrip(":")
        adapter_cmd = [
            sys.executable,
            str(adapter_gem5),
            "--out-dir",
            str(inputs_dir),
        ]
        if use_stats_adapter:
            adapter_cmd += [
                "--gem5-stats",
                str(stats_path),
                "--ipc-active-thresh",
                str(args.gem5_ipc_active_thresh),
                "--stall-miss-thresh",
                str(args.gem5_stall_miss_thresh),
                "--l1-resident-thresh",
                str(args.gem5_l1_resident_thresh),
                "--mem-reqs-per-inst-thresh",
                str(args.gem5_mem_reqs_per_inst_thresh),
                "--idle-inst-thresh",
                str(args.gem5_idle_inst_thresh),
            ]
        else:
            adapter_cmd += [
                "--gem5-trace",
                str(trace_path),
                "--inst-us",
                str(args.inst_us),
                "--resident-pc-ge",
                str(args.resident_pc_ge),
                "--classification-mode",
                str(args.sim_classification_mode),
            ]
        sh(adapter_cmd, cwd=repo, env=adapter_env)

        state_csv = inputs_dir / "state_intervals.csv"
        resid_csv = inputs_dir / "residency_intervals.csv"
        gem5_input_path = stats_path if use_stats_adapter else trace_path
        gem5_thresholds: dict[str, object]
        if use_stats_adapter:
            gem5_thresholds = {
                "ipc_active_thresh": float(args.gem5_ipc_active_thresh),
                "stall_miss_thresh": float(args.gem5_stall_miss_thresh),
                "l1_resident_thresh": float(args.gem5_l1_resident_thresh),
                "mem_reqs_per_inst_thresh": float(args.gem5_mem_reqs_per_inst_thresh),
                "idle_inst_thresh": float(args.gem5_idle_inst_thresh),
            }
        else:
            gem5_thresholds = {"resident_pc_ge": str(args.resident_pc_ge)}
        adapter_meta_base.update(
            {
                "adapter_name": "gem5_adapter",
                "adapter_mode": "stats" if use_stats_adapter else "exec",
                "tool_version": resolve_tool_version([str(gem5_bin), "--version"]),
                "thresholds": gem5_thresholds,
                "input_trace_path": str(gem5_input_path),
                "requested_cores": gem5_num_cpus,
                "workload_sharded": gem5_workload_sharded,
                "workload_parallel_mode": gem5_parallel_mode,
                "cpu_types": gem5_cpu_types,
                "heterogeneous_cpu_mix": gem5_heterogeneous,
            }
        )

    elif args.target == "qemu":
        qemu_bin = resolve_qemu_binary(args.qemu_bin)
        ensure_tool(args.qemu_cc)

        cpath = write_workload(
            build_dir,
            args.workload,
            args.workload_size,
            branch_mispredict_enabled,
            cache_pressure_enabled,
            baseline_case=simulator_baseline_case,
            sim_ops_per_zone=args.sim_ops_per_zone,
            emit_work_markers=not args.sim_trace_only,
        )
        binpath = build_dir / args.workload

        sh(
            [
                args.qemu_cc,
                "-O0",
                "-static",
                "-march=rv64gc",
                "-mabi=lp64d",
                str(cpath),
                "-o",
                str(binpath),
            ],
            cwd=build_dir,
        )

        trace_path = traces_dir / "qemu.trace"
        log_path = traces_dir / "qemu.log"

        qemu_cmd = [
            qemu_bin,
            "-d",
            "in_asm,exec,nochain",
            "-D",
            str(trace_path),
        ]
        if args.qemu_extra_args.strip():
            qemu_cmd.extend(shlex.split(args.qemu_extra_args.strip()))
        qemu_cmd.append(str(binpath))

        print(f"ℹ Running: {' '.join(qemu_cmd)}\n")
        with open(log_path, "w") as qemu_out:
            p = subprocess.run(qemu_cmd, cwd=run_dir, stdout=qemu_out, stderr=subprocess.STDOUT)
        if p.returncode < 0:
            raise SystemExit(f"qemu run terminated by signal (rc={p.returncode}). See {log_path}")
        if p.returncode != 0 and not args.allow_nonzero_exit:
            raise SystemExit(f"qemu run failed (rc={p.returncode}). See {log_path}")
        if p.returncode != 0 and args.allow_nonzero_exit:
            print(f"ℹ qemu workload exited with rc={p.returncode}; continuing with generated trace")
        if not trace_path.exists() or trace_path.stat().st_size == 0:
            raise SystemExit(f"qemu trace empty: {trace_path}")

        adapter_env = dict(os.environ)
        adapter_env["PYTHONPATH"] = f"{repo}:{adapter_env.get('PYTHONPATH', '')}".rstrip(":")
        sh(
            [
                sys.executable,
                str(adapter_qemu),
                "--qemu-trace",
                str(trace_path),
                "--out-dir",
                str(inputs_dir),
                "--inst-us",
                str(args.inst_us),
                "--resident-pc-ge",
                str(args.resident_pc_ge),
                "--classification-mode",
                str(args.sim_classification_mode),
            ],
            cwd=repo,
            env=adapter_env,
        )

        state_csv = inputs_dir / "state_intervals.csv"
        resid_csv = inputs_dir / "residency_intervals.csv"
        adapter_meta_base.update(
            {
                "adapter_name": "qemu_adapter",
                "adapter_mode": "dynamic_tb_trace",
                "tool_version": resolve_tool_version([str(qemu_bin), "--version"]),
                "thresholds": {"resident_pc_ge": str(args.resident_pc_ge)},
                "allow_nonzero_exit": bool(args.allow_nonzero_exit),
                "input_trace_path": str(trace_path),
            }
        )

    elif args.target == "tt_wormhole":
        if not args.tt_profile_csv:
            raise SystemExit("--tt-profile-csv is required when --target tt_wormhole")
        if not args.tt_zone_log:
            raise SystemExit("--tt-zone-log is required when --target tt_wormhole")
        profile_csv = Path(args.tt_profile_csv).resolve()
        zone_log = Path(args.tt_zone_log).resolve()
        if not profile_csv.exists():
            raise SystemExit(f"tt_wormhole profile csv not found: {profile_csv}")
        if not zone_log.exists():
            raise SystemExit(f"tt_wormhole zone log not found: {zone_log}")
        if not adapter_tt.exists():
            raise SystemExit(f"tt_wormhole adapter not found: {adapter_tt}")

        tt_expected_total_work = None
        if args.tt_ops_per_zone is not None:
            tt_expected_total_work = resolve_tt_total_work_units(
                args.workload_size,
                float(args.tt_ops_per_zone),
            )

        adapter_env = dict(os.environ)
        adapter_env["PYTHONPATH"] = f"{repo}:{adapter_env.get('PYTHONPATH', '')}".rstrip(":")
        adapter_cmd = [
            sys.executable,
            str(adapter_tt),
            "--profile-csv",
            str(profile_csv),
            "--zone-log",
            str(zone_log),
            "--out-dir",
            str(inputs_dir),
            "--output-mode",
            str(args.tt_output_mode),
        ]
        if args.tt_chip_freq_mhz is not None:
            adapter_cmd += ["--chip-freq-mhz", str(args.tt_chip_freq_mhz)]
        if args.tt_strict_pairing:
            adapter_cmd += ["--strict-pairing"]
        if args.tt_strict_map_hit:
            adapter_cmd += ["--strict-map-hit"]
        if args.tt_ops_per_zone is not None:
            adapter_cmd += ["--ops-per-zone", str(args.tt_ops_per_zone)]
        if tt_expected_total_work is not None:
            adapter_cmd += ["--expected-total-work", str(tt_expected_total_work)]
        if args.tt_residency_model:
            adapter_cmd += ["--residency-model", str(args.tt_residency_model)]

        sh(adapter_cmd, cwd=repo, env=adapter_env)

        state_csv = inputs_dir / "state_intervals.csv"
        resid_csv = inputs_dir / "residency_intervals.csv"
        if not state_csv.exists() or state_csv.stat().st_size == 0:
            raise SystemExit(f"tt_wormhole adapter state output missing/empty: {state_csv}")
        if not resid_csv.exists() or resid_csv.stat().st_size == 0:
            raise SystemExit(f"tt_wormhole adapter residency output missing/empty: {resid_csv}")

        adapter_meta_base.update(
            {
                "adapter_name": "tt_wormhole_adapter",
                "adapter_mode": str(args.tt_output_mode),
                "tool_version": resolve_tool_version([sys.executable, "--version"]),
                "thresholds": {
                    "strict_pairing": bool(args.tt_strict_pairing),
                    "strict_map_hit": bool(args.tt_strict_map_hit),
                    "chip_freq_mhz_override": args.tt_chip_freq_mhz,
                    "ops_per_zone": args.tt_ops_per_zone,
                    "expected_total_work": tt_expected_total_work,
                    "residency_model": str(args.tt_residency_model),
                },
                "input_trace_path": str(profile_csv),
            }
        )

    elif args.target == "cpu":
        cpath = write_workload(
            build_dir,
            args.workload,
            args.workload_size,
            branch_mispredict_enabled,
            cache_pressure_enabled,
            baseline_case=simulator_baseline_case,
        )
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
        adapter_meta_base.update(
            {
                "adapter_name": "cpu_synthetic_adapter",
                "adapter_mode": "host_runtime_synthetic",
                "tool_version": resolve_tool_version(["gcc", "--version"]),
                "thresholds": {},
                "input_trace_path": None,
            }
        )
    else:
        raise SystemExit(f"unsupported target: {args.target}")

    if args.target == "tt_wormhole" and args.expected_work_rate is None:
        args.expected_work_rate = resolve_tt_expected_work_rate(
            args.workload_size,
            float(args.tt_ops_per_zone),
            resid_csv,
        )
        if args.expected_work_rate is None:
            args.expected_work_rate = DEFAULT_EXPECTED_WORK_RATE

    normalized_hashes: dict[str, str] = {}
    if state_csv.exists():
        normalized_hashes["state_intervals_sha256"] = sha256_file(state_csv)
    if resid_csv.exists():
        normalized_hashes["residency_intervals_sha256"] = sha256_file(resid_csv)
    adapter_meta_full: dict[str, object] = dict(adapter_meta_base)
    input_trace_path_raw = adapter_meta_full.get("input_trace_path", None)
    input_trace_sha = None
    if isinstance(input_trace_path_raw, str) and input_trace_path_raw:
        pth = Path(input_trace_path_raw)
        if pth.exists():
            input_trace_sha = sha256_file(pth)
    adapter_meta_full["input_trace_sha256"] = input_trace_sha
    adapter_meta_full["normalized_output_sha256"] = {
        **normalized_hashes,
        "combined_sha256": stable_combined_sha256(normalized_hashes) if normalized_hashes else None,
    }
    adapter_meta_full["timestamp_utc"] = (
        datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    adapter_meta_path = run_dir / "adapter_meta.json"
    adapter_meta_path.write_text(json.dumps(adapter_meta_full, indent=2, sort_keys=True), encoding="utf-8")

    if args.skip_post_processing:
        print("✓ Workload execution complete")
        return

    cli_py = repo / "result_handler" / "cli.py"
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
        "--no-work-sit-mode", str(args.no_work_sit_mode)]
    if args.expected_work_rate is not None:
        classify_cmd.extend(["--expected-work-rate", str(args.expected_work_rate)])
    if resid_csv.exists():
        classify_cmd.extend(["--residency", str(resid_csv)])
    sh(classify_cmd, cwd=repo)

    # Embed stable adapter metadata into summary artifacts (without timestamp).
    summary_meta = {
        "adapter_name": adapter_meta_base.get("adapter_name"),
        "adapter_mode": adapter_meta_base.get("adapter_mode"),
        "tool_version": adapter_meta_base.get("tool_version"),
        "repo_commit": adapter_meta_base.get("repo_commit"),
        "inst_us": adapter_meta_base.get("inst_us"),
        "window_us": adapter_meta_base.get("window_us"),
        "thresholds": adapter_meta_base.get("thresholds"),
        "input_trace_sha256": adapter_meta_full.get("input_trace_sha256"),
        "normalized_output_sha256": adapter_meta_full.get("normalized_output_sha256"),
        "allow_nonzero_exit": adapter_meta_base.get("allow_nonzero_exit"),
        "requested_cores": adapter_meta_base.get("requested_cores"),
        "workload_sharded": adapter_meta_base.get("workload_sharded"),
        "workload_parallel_mode": adapter_meta_base.get("workload_parallel_mode"),
        "sim_trace_only": adapter_meta_base.get("sim_trace_only"),
        "sim_classification_mode": adapter_meta_base.get("sim_classification_mode"),
        "cpu_types": adapter_meta_base.get("cpu_types"),
        "heterogeneous_cpu_mix": adapter_meta_base.get("heterogeneous_cpu_mix"),
    }
    tt_work_audit = None
    if args.target == "tt_wormhole" and state_csv.exists():
        adapter_debug_summary = inputs_dir / "adapter_debug_summary.txt"
        tt_work_audit = derive_tt_work_audit(
            args.workload_size,
            float(args.tt_ops_per_zone),
            state_csv,
            adapter_debug_summary=adapter_debug_summary,
        )
        warning = str(tt_work_audit.get("warning") or "").strip()
        if warning:
            print(f"ℹ TT work audit: {warning}")

    for smry in [run_dir / "summary.json", run_dir / "run_summary.json"]:
        if not smry.exists():
            continue
        try:
            obj = json.loads(smry.read_text(encoding="utf-8"))
            obj["adapter_meta"] = summary_meta
            if tt_work_audit is not None:
                obj["tt_work_audit"] = tt_work_audit
            smry.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass

    sh([sys.executable, str(cli_py), "export",
        "--in", str(run_dir),
        "--schema", "v1",
        "--format", "csv"], cwd=repo)

    print("✓ done")

if __name__ == "__main__":
    main()
