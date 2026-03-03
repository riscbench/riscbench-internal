# Phase-1 Generalization Note  
## Mapping Phase-0 Semantics into the Hardware-Agnostic SIT Engine

This note defines how the **Phase-0 Tenstorrent Wormhole semantics** are generalized into the **Phase-1 RISCBench SIT Engine** without changing meaning.

Phase-1 generalizes mechanisms, not definitions. The SIT Engine must preserve the semantics established in Phase-0 while enabling reuse across simulators, FPGA platforms, and future silicon.

---

## Purpose of Phase-1

Phase-1 exists to extract the invariant core of SIT computation from a platform-specific implementation and express it as:

- A hardware-agnostic engine
- A stable ingestion API
- A versioned, machine-readable output schema

Phase-1 must never reinterpret what SIT means.

---

## Semantic invariants carried forward from Phase-0

### Fixed time windows remain an analysis construct

- Windows discretize time, not memory
- Window size is configurable and experimenter-controlled
- Windows are imposed after trace ingestion
- Windows do not correspond to SRAM size, cache size, tiles, or buffers

---

### Residency gates SIT accumulation

- SIT is accumulated only during residency intervals
- Residency defines when work is eligible to count
- No residency overlap implies SIT equals zero

---

### Residency and window boundaries are independent

- Residency may start or end inside any window
- Residency may span multiple windows
- Residency may be fragmented

Partial-window accumulation must be preserved exactly.

---

### Activity classification is conditioned on residency

- Active, stall, and idle states are evaluated only within residency
- Execution outside residency is excluded

---

## What changes in Phase-1

### Residency becomes an explicit interface

Adapters must supply residency intervals explicitly or provide inferred residency with confidence metadata.  
The SIT Engine never infers residency internally.

---

### Trace ingestion API

Platform-specific traces are normalized by adapters into a common event schema.  
The SIT Engine consumes only normalized events.

---

### Platform diversity

Phase-1 must support explicit, abstracted, and inferred memory hierarchies.  
If residency cannot be determined confidently, uncertainty must be declared.

---

## What Phase-1 must not do

- Redefine residency semantics
- Tie window size to memory capacity
- Accumulate SIT outside residency
- Introduce platform-specific logic into the engine core

---

## Phase-1 correctness criterion

Phase-1 is correct if it reproduces Phase-0 behavior under equivalent conditions.  
If Phase-1 disagrees with Phase-0, Phase-1 is wrong.

---

Phase-0 remains the semantic anchor.  
Phase-1 is the reusable engine that faithfully carries it forward.
