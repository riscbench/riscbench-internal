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

WORKLOADS_CUSTOM = {"fm_loopback", "fm_mm", "fm_read", "fm_write"}
WORKLOADS_STANDARD = {"alu", "branch", "memory", "hello", "memread", "memwrite", "memcpy"}
WORKLOADS_SPIKE = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
WORKLOADS_CPU = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
WORKLOADS_GEM5 = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
WORKLOADS_QEMU = WORKLOADS_STANDARD | WORKLOADS_CUSTOM | {"matmul", "matmul_multicore"}
SIZES = {"test", "tiny", "small", "med", "large"}

SIZE_PRESETS = {
    "test":  {"ITER": 256, "DIM": 16,  "PAGES": 2,  "ACTIVE_BOOST": 1},
    "tiny":  {"ITER": 2000, "DIM": 64,  "PAGES": 4,  "ACTIVE_BOOST": 2},
    "small": {"ITER": 3000, "DIM": 96,  "PAGES": 8,  "ACTIVE_BOOST": 3},
    "med":   {"ITER": 4000, "DIM": 128, "PAGES": 16, "ACTIVE_BOOST": 4},
    "large": {"ITER": 5000, "DIM": 256, "PAGES": 32, "ACTIVE_BOOST": 5},
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
    stall_phase((uint64_t)N * (uint64_t)N / 2);
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

def write_workload(build_dir: Path, workload: str, size: str, 
                   branch_mispredict: bool = False,
                   cache_pressure: bool = False) -> Path:
    """Generate C workload with IDLE and STALL phases"""
    preset = SIZE_PRESETS[size]
    code = SRC[workload]
    
    code = code.replace("ITER", str(preset["ITER"]))
    code = code.replace("DIM", str(preset["DIM"]))
    code = code.replace("ACTIVE_BOOST", str(preset["ACTIVE_BOOST"]))
    #code = code.replace("PAGES", str(preset["PAGES"]))
    code = code.replace("BRANCH_MISPREDICT_ENABLED", "1" if branch_mispredict else "0")
    code = code.replace("CACHE_PRESSURE_ENABLED", "1" if cache_pressure else "0")

    # Some legacy templates model cache pressure via a fixed unmapped address
    # (0x80000000), which segfaults in qemu user-mode and can break gem5 SE.
    # Replace with a safe local buffer while preserving memory-access behavior.
    code = code.replace(
        "volatile uint64_t* ptr = (volatile uint64_t*)(0x80000000);",
        "static volatile uint64_t SAFE_STALL_BUF[4096];\n"
        "    volatile uint64_t* ptr = SAFE_STALL_BUF;",
    )

    code = _inject_unified_workload_phases(
        code,
        preset=preset,
        branch_mispredict=branch_mispredict,
        cache_pressure=cache_pressure,
    )

    # Keep templates robust: some workloads use uint64_t and may miss the include.
    if "uint64_t" in code and "#include <stdint.h>" not in code:
        code = '#include <stdint.h>\n' + code
    
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
    
    ap.add_argument("--target", default="cpu", choices=["spike", "cpu", "gem5", "qemu", "both"])
    ap.add_argument("--workload", default="fm_mm", 
                    choices=sorted((WORKLOADS_CPU | WORKLOADS_SPIKE | WORKLOADS_GEM5 | WORKLOADS_QEMU) | {"all"}))
    ap.add_argument("--workload_size", default="small", choices=sorted(SIZES))
    
    ap.add_argument("--branch-mispredict", action="store_true",
                    help="Enable branch mispredicts (causes STALL)")
    ap.add_argument("--cache-pressure", action="store_true",
                    help="Enable cache misses (causes STALL)")
    
    ap.add_argument("--time_us", default=256.0, type=float)
    ap.add_argument("--expected-work-rate", type=float, default=1.0)
    ap.add_argument(
        "--no-work-sit-mode",
        choices=["global_active", "window_active"],
        default="global_active",
        help="Fallback SIT mode when work_done is unavailable",
    )
    ap.add_argument("--skip-post-processing", action="store_true")
    ap.add_argument("--practical", action="store_true")
    ap.add_argument("--debug-sit", action="store_true")
    
    ap.add_argument("--cores", type=int, default=None)
    ap.add_argument("--isa", default="RV64GC")
    ap.add_argument("--pk", default=str(Path.home() / "opt" / "riscv" / "riscv64-unknown-elf" / "bin" / "pk"))
    ap.add_argument("--inst_us", type=float, default=1.0)
    ap.add_argument("--resident_pc_ge", default="0x80000000")
    ap.add_argument("--gem5-bin", default=os.environ.get("GEM5_BIN", "gem5.opt"))
    ap.add_argument("--gem5-root", default=os.environ.get("GEM5_ROOT", ""))
    ap.add_argument("--gem5-config", default=None, help="Path to gem5 se.py config")
    ap.add_argument("--gem5-extra-args", default="", help="Extra args passed to gem5 after se.py")
    ap.add_argument("--gem5-cc", default=os.environ.get("GEM5_CC", "riscv64-linux-gnu-gcc"))
    ap.add_argument("--gem5-cpu-type", default="TimingSimpleCPU")
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

    args = ap.parse_args()
    
    print("\n=== CORRECT MODEL ===")
    print("IDLE: in workload (nop loops - core not computing)")
    print("STALL: from flags (--branch-mispredict, --cache-pressure)")
    print("Values: from workload execution (markers 101/102)\n")
    
    if args.branch_mispredict:
        print("ℹ --branch-mispredict: unpredictable branches → pipeline stalls")
    if args.cache_pressure:
        print("ℹ --cache-pressure: random access → cache misses → stalls")
    if not args.branch_mispredict and not args.cache_pressure:
        print("ℹ Baseline: no stall flags, ~50% idle in workload")
    print()

    if args.target == "both" or args.workload == "all":
        targets = ["spike", "cpu"] if args.target == "both" else [args.target]
        workloads = list(
            ["fm_loopback", "fm_mm", "fm_read", "fm_write"]
            if args.practical
            else sorted(WORKLOADS_CPU | WORKLOADS_SPIKE | WORKLOADS_GEM5 | WORKLOADS_QEMU)
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
    adapter_gem5 = repo / "adapters" / "gem5_adapter.py"
    adapter_qemu = repo / "adapters" / "qemu_adapter.py"

    run_dir = repo / "runs" / args.target / args.workload / args.workload_size
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
    }

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
        adapter_meta_base.update(
            {
                "adapter_name": "spike_adapter",
                "adapter_mode": "commit_log",
                "tool_version": resolve_tool_version(["spike", "--version"]),
                "thresholds": {"resident_pc_ge": str(args.resident_pc_ge)},
                "input_trace_path": str(trace_path),
            }
        )

    elif args.target == "gem5":
        if args.workload not in WORKLOADS_GEM5:
            raise SystemExit(f"gem5 does not support: {args.workload}")

        gem5_bin = resolve_gem5_binary(args.gem5_bin)
        gem5_cfg = resolve_gem5_config(gem5_bin, args.gem5_root, args.gem5_config)
        use_stats_adapter = args.gem5_adapter_mode == "stats"
        gem5_cfg_runner = gem5_cfg
        if use_stats_adapter:
            wrapper_cfg = repo / "configs" / "gem5_se_periodic_stats.py"
            if not wrapper_cfg.exists():
                raise SystemExit(f"Missing gem5 wrapper config: {wrapper_cfg}")
            gem5_cfg_runner = wrapper_cfg
        ensure_tool(args.gem5_cc)

        if args.workload == "matmul_multicore":
            cpath = write_workload(build_dir, "matmul", args.workload_size, args.branch_mispredict, args.cache_pressure)
            binpath = build_dir / "matmul_multicore"
        else:
            cpath = write_workload(build_dir, args.workload, args.workload_size, args.branch_mispredict, args.cache_pressure)
            binpath = build_dir / args.workload

        sh(
            [
                args.gem5_cc,
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
            f"--cmd={binpath}",
            f"--cpu-type={args.gem5_cpu_type}",
            f"--mem-size={args.gem5_mem_size}",
            "--caches",
        ]
        if use_stats_adapter:
            gem5_cmd += [
                "--phase2-se-script",
                str(gem5_cfg),
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
            }
        )

    elif args.target == "qemu":
        if args.workload not in WORKLOADS_QEMU:
            raise SystemExit(f"qemu does not support: {args.workload}")

        qemu_bin = resolve_qemu_binary(args.qemu_bin)
        ensure_tool(args.qemu_cc)

        if args.workload == "matmul_multicore":
            cpath = write_workload(build_dir, "matmul", args.workload_size, args.branch_mispredict, args.cache_pressure)
            binpath = build_dir / "matmul_multicore"
        else:
            cpath = write_workload(build_dir, args.workload, args.workload_size, args.branch_mispredict, args.cache_pressure)
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
            adapter_meta_base.update(
                {
                    "adapter_name": "cpu_synthetic_adapter",
                    "adapter_mode": "host_runtime_synthetic",
                    "tool_version": resolve_tool_version(["gcc", "--version"]),
                    "thresholds": {},
                    "input_trace_path": None,
                }
            )

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
        "--expected-work-rate", str(args.expected_work_rate),
        "--no-work-sit-mode", str(args.no_work_sit_mode)]
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
    }
    for smry in [run_dir / "summary.json", run_dir / "run_summary.json"]:
        if not smry.exists():
            continue
        try:
            obj = json.loads(smry.read_text(encoding="utf-8"))
            obj["adapter_meta"] = summary_meta
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
