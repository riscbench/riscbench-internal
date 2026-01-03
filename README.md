# riscbench-internal
Internal (private)-closed development of RISCBench before approved upstream to public RISCBench repo.

> 📌 **Pinned Reference**
>
> RISCBench Phase 1 is the center of gravity for the project.
> All simulator integrations, kernels, and extensions must align with the SIT Engine defined here:
>
> 👉 **[PHASE1_PHASE2_ALIGNMENT.md](docs/PHASE1_PHASE2_ALIGNMENT.md)**  
> _(Required reading for contributors)_


<br>

# Phase-0. Tenstorrent Wormhole Testbed  
**RISCBench Ground-Truth Reference**

This directory contains the **Phase-0 Tenstorrent Wormhole testbed**, which grounds the RISCBench **Sustained Instantaneous Throughput (SIT)** metric in real hardware behavior before any abstraction or generalization.

Phase-0 exists to define **correct semantics**, not to provide a reusable benchmarking engine.

---

## Audience guide

- If you are an **internal developer or RISCBench maintainer**, read  
  → **Section A. Internal developers**

- If you are an **external contributor or new collaborator**, read  
  → **Section B. External contributors**

---

## Cross-links into Phase-1

Phase-0 is the semantic anchor and Phase-1 is the reusable engine that must preserve these semantics.

- Phase-1 README  
  `../Phase-1/README.md`

- Phase-1 Generalization Note  
  `../Phase-1/GENERALIZATION.md`

If Phase-1 behavior disagrees with Phase-0 semantics under equivalent conditions, Phase-1 is wrong.

---

## Section A. Internal developers  
**Read this section if you are extending or maintaining RISCBench**

### Role of Phase-0 in RISCBench

Phase-0 is the **ground-truth anchor** for RISCBench. It ties the SIT definition directly to real Tenstorrent Wormhole-class hardware behavior.

Phase-1 generalizes mechanisms, not meaning.  
Nothing in Phase-1 may reinterpret the semantics established here.

### Fixed windows are an analysis lens

- Fixed windows discretize **time**
- Window size is configurable and experimenter-controlled
- Windows do not correspond to SRAM blocks, tiles, or buffers
- Windows are applied after trace ingestion

Window size must never be tied to SRAM capacity.

### SRAM residency is hardware-driven

SRAM residency intervals are derived from Tenstorrent trace semantics such as:
- DRAM → SRAM transfer completion
- SRAM → DRAM eviction events
- Buffer or tile lifetime markers
- Kernel phases requiring SRAM-resident operands

Residency intervals:
- May begin or end inside a window
- May span multiple windows
- May be fragmented

### SIT accumulation invariant

SIT is accumulated **only** over the intersection of:
- Execution activity
- SRAM residency
- Fixed time windows

Rules:
- No residency overlap → SIT = 0
- Partial overlap → partial SIT
- Full overlap → full-window SIT

This invariant must hold regardless of:
- Window size
- Trace resolution
- Platform generalization

### Development constraints

Internal developers must not:
- Redefine residency semantics
- Accumulate SIT outside residency
- Tie window size to SRAM capacity
- Introduce generalized abstractions here

Instead:
- Treat Phase-0 as a correctness oracle
- Use it to validate Phase-1 behavior
- Push all abstraction work into Phase-1

### Internal rule

If Phase-1 behavior disagrees with Phase-0 semantics under equivalent conditions, Phase-1 is wrong.

---

## Section B. External contributors  
**Read this section if you are new to RISCBench or contributing for the first time**

### What Phase-0 is

- A platform-specific research prototype
- Anchored to Tenstorrent Wormhole-class architectures
- Used to validate fixed windows, dynamic residency, and residency-gated SIT
- A correctness reference for later phases

### What Phase-0 is not

- Not hardware-agnostic
- Not a reusable benchmarking framework
- Not the canonical RISCBench implementation
- Not the place to add new simulators or platforms

All generalization work belongs in Phase-1.

### Core measurement principle

Execution is analyzed over fixed-duration time windows imposed by the analysis, not by the hardware.

Within each window, SIT is accumulated only during periods where data resides in on-chip SRAM. If no SRAM residency overlaps a window, SIT for that window is defined as zero, regardless of observed instruction execution.

This ensures SIT reflects orchestration efficiency when data locality enables work, rather than raw throughput.

### Fixed windows vs SRAM residency

- Window size is chosen by the experimenter and controls temporal resolution
- SRAM capacity is fixed by hardware
- Data residency is dynamic and workload-driven

Window boundaries and residency boundaries are independent.

### How to contribute safely

External contributors are encouraged to:
- Study Phase-0 to understand intended SIT semantics
- Use this implementation as a reference when working in Phase-1
- Avoid introducing abstractions or new hardware assumptions here

If your contribution involves portability, reuse, or simulator support, it belongs in Phase-1, not Phase-0.

---

## Phase relationship summary

- Phase-0 defines semantic correctness
- Phase-1 defines the reusable SIT Engine
- Phase-2 exercises the engine across simulators

Phase-0 must remain stable as the reference point for all future phases.