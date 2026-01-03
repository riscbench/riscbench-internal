# Phase-1. SIT Engine Core  
**RISCBench Hardware-Agnostic Engine**

Phase-1 is the **center of gravity** of RISCBench.  
It generalizes the semantics validated in Phase-0 into a reusable, hardware-agnostic SIT Engine.

Phase-1 does **not** redefine SIT.  
It preserves meaning while enabling reuse across simulators, platforms, and future silicon.

---

## Role of Phase-1

Phase-1 defines the **single source of truth** for

- Windowing
- Residency semantics
- SIT accumulation
- Output schema

All later phases must call into this engine.  
No later phase may reinterpret, duplicate, or bypass Phase-1 logic.

---

## Relationship to Phase-0

- Phase-0 defines semantic correctness on real hardware
- Phase-1 generalizes mechanisms without changing meaning
- Phase-1 must reproduce Phase-0 behavior under equivalent inputs

Phase-0 is the **semantic anchor** for all Phase-1 behavior.

If Phase-1 diverges from Phase-0 semantics under equivalent conditions, **Phase-1 is wrong**.

---

## Required reading order

Before contributing to Phase-1, read in this order

1. Phase-0 README  
   `../Phase-0/README.md`  
   Defines fixed windows, SRAM residency, and SIT semantics

2. Phase-1 Generalization Note  
   `GENERALIZATION.md`  
   Maps Phase-0 semantics into the hardware-agnostic engine

3. This document

---

## What Phase-1 delivers

- SIT Engine core pipeline
- Trace ingestion API and adapter contracts
- Residency-gated, windowed SIT computation
- Versioned, machine-readable output schema
- Validation hooks, golden traces, and invariants

---

## What belongs in Phase-1

- Hardware-agnostic logic only
- Adapter interfaces and ingest contracts
- Schema evolution under explicit version control
- Validation logic and reference behavior
- Golden traces and invariant enforcement

---

## What does **not** belong in Phase-1

- Platform-specific trace parsing logic
- Simulator-specific heuristics inside the engine
- Redefinition of residency semantics
- Windowing tied to hardware capacity or SRAM size
- Any second implementation of SIT logic

---

## Relationship to Phase-2

Phase-2 exists to integrate simulators and run parameter sweeps.  
Phase-2 **must not** reimplement or reinterpret SIT logic.

Phase-2 documentation

- `Phase-2/README.md`
- `Phase-2/ADAPTERS.md`
- `Phase-2/VALIDATION.md`
- `Phase-2/SWEEPS.md`
- `Phase-2/DATASETS.md`
- `Phase-2/CI.md`

Any Phase-2 contribution must demonstrate compatibility with the Phase-1 engine and preserve all invariants defined here.

---

## Internal rule

Phase-1 exists to make SIT reusable **without semantic drift**.

If a change improves convenience but weakens semantic alignment with Phase-0, the change must be rejected.
