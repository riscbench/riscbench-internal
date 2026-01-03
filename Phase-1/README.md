# Phase-1. SIT Engine Core  
**RISCBench Hardware-Agnostic Engine**

Phase-1 is the center of gravity of RISCBench. It generalizes the semantics validated in Phase-0 into a reusable, hardware-agnostic SIT Engine.

Phase-1 does not redefine SIT. It preserves meaning while enabling reuse.

---

## How Phase-1 relates to Phase-0

- Phase-0 defines semantic correctness on real hardware
- Phase-1 generalizes mechanisms without changing meaning
- Phase-1 must reproduce Phase-0 behavior under equivalent inputs

Phase-0 is the semantic anchor for all Phase-1 behavior.

---

## Required reading

Before contributing to Phase-1, read:

- Phase-0 README  
  `../Phase-0/README.md`  
  Defines fixed windows, SRAM residency, and SIT semantics

- Phase-1 Generalization Note  
  `GENERALIZATION.md`  
  Maps Phase-0 semantics into the hardware-agnostic engine

---

## What Phase-1 delivers

- SIT Engine core pipeline
- Trace ingestion API and adapter contracts
- Residency-gated windowed SIT computation
- Versioned output schema
- Validation hooks and reference behavior

---

## What belongs in Phase-1

- Hardware-agnostic logic
- Adapter interfaces
- Schema evolution under version control
- Validation and golden traces

---

## What does not belong in Phase-1

- Platform-specific trace parsing logic
- Redefinition of residency semantics
- Windowing tied to hardware capacity
- Simulator-specific heuristics inside the engine

---

## Internal rule

If Phase-1 behavior diverges from Phase-0 semantics under equivalent conditions, Phase-1 is wrong.

---

Phase-1 exists to make SIT reusable without semantic drift.
