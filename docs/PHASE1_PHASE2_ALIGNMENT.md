# RISCBench Phase 1 and Phase 2 Alignment Guide

This document captures the intended technical alignment for RISCBench Phase 1 and Phase 2 development. It is meant to serve as a stable reference for contributors, interns, and collaborators so work remains coherent with the roadmap and research intent.

---

## Project context

The RISCBench repository contains multiple phases that intentionally build on one another.

Phase 0 provides a research starting point. It includes a performance-profiling prototype implemented for a very specific platform, the Tenstorrent ASIC. This code is not the target architecture, but a concrete example used to validate early thinking around SIT and residency.

Phase 1 is the core of the project. Its goal is to generalize the Phase 0 work into a clean, hardware-agnostic SIT Engine with a stable API and schema. Every later phase depends on this engine rather than reimplementing logic elsewhere.

Phase 2 expands breadth by integrating simulators, but only by calling into the Phase 1 SIT Engine. Phase 2 must not fragment or bypass the core engine.

Phase 1 is the center of gravity for Phases 2, 3, and 4.

---

## Phase 1 goals and responsibilities

Phase 1 focuses on depth rather than breadth.

Key objectives include
- Understanding the Phase 0 Tenstorrent profiling implementation
- Generalizing the profiling logic into a hardware-agnostic SIT Engine
- Defining clear trace ingestion APIs and adapter contracts
- Implementing residency classification and SIT window detection
- Producing a stable, machine-readable output schema
- Establishing reference datasets and validation tests

The Phase 1 engine must be small, predictable, and testable. It is the single source of truth that all simulators, kernels, and platforms call into.

---

## Residency and SIT definition

By residency window, we explicitly mean SRAM residency.

Residency windows correspond to points in time when data is resident in on-chip memory for the target hardware or simulator model.

SIT is accumulated only during SRAM residency windows. Periods where data is not resident must not contribute to SIT, even if instructions continue executing.

This definition is foundational and must remain consistent across platforms.

---

## Phase 2 scope and boundaries

Phase 2 expands breadth, not theory.

Its role is to integrate simulators and parameter sweeps by adapting their outputs into the Phase 1 SIT Engine.

Phase 2 must not
- Reimplement SIT logic
- Introduce alternative definitions of residency
- Diverge from the Phase 1 schema without versioning

Phase 2 exists to stress-test, validate, and expose the Phase 1 engine under controlled variation.

---

## Phase 2 clarifications and decisions

### Phase 1 baseline acceptability

The current Phase 1 approach is acceptable as the Phase 2 baseline.

Defaults may include
- Fixed windowing
- Residency classification
- Summary statistics such as median and p95

These defaults represent a lab-baseline profile, not a claim of global optimality.

Requirements
- Window size must be configurable as a first-class parameter
- Each adapter must emit trace quality metadata to allow confidence comparison across simulators

---

### Simulator order for Phase 2

Recommended sequence
- Spike first
- QEMU second
- gem5 third

Rationale
- Spike offers the lowest friction for RV64GC instruction trace ingestion and matches roadmap examples
- QEMU provides a widely used middle ground with faster iteration
- gem5 offers richer timing and memory hierarchy modeling but carries higher integration and validation complexity

---

### Golden references and validation

Validation should use a golden set, not a single truth trace.

Three golden artifacts are required
- Golden kernel traces consisting of deterministic micro-kernels with expected SIT signatures
- Golden schema outputs consisting of pinned parquet or json outputs tied to a specific SIT Engine version
- Golden invariants that must hold regardless of simulator

Example invariants
- SIT must not exceed the normalized peak for a given run configuration
- Increasing residency time increases SIT when compute is held constant
- Injected stalls increase stall residency and monotonically reduce sit_median

---

### Active, stall, and idle inference

A critical requirement is determining when data is resident in SRAM and using that information as the basis for all measurements.

Adapter design principles
- API-first by design for extensibility and ease of integration
- Prefer explicit simulator-reported states when available
- Timing-based inference is acceptable initially when explicit states are unavailable

Inference requirements
- Inferred states must be clearly labeled
- Confidence or quality metadata must be included

---

### Synthetic kernels versus real workloads

Phase 2 should start with synthetic micro-kernels.

Reasons
- Deterministic expected SIT behavior
- Cleaner validation and debugging
- Reduced simulator noise

Guidance
- Kernels from the Phase 0 Tenstorrent work may be reused or adapted
- One to two real workload traces may be added later as sanity anchors
- Real workloads should only be introduced after adapters and golden tests are stable

---

### Schema discipline

Phase 2 outputs must follow the Phase 1 schema for baseline compatibility.

Design expectations
- API-first thinking so the Phase 1 engine can speak cleanly to diverse simulators
- Schema must remain lean and disciplined

Limited extensions are acceptable
- Extensions must live under a versioned extensions namespace
- No breaking changes to core fields during Phase 2

Possible extension categories
- Adapter metadata such as simulator version or inferred state confidence
- Sweep metadata such as cache size overrides or core count

---

### Phase 2 emphasis and priorities

Priority order
- Validation and golden traces
- Memory hierarchy effects with explicit attention to SRAM residency
- Window size sensitivity explored through parameter sweeps
- Clear documentation of adapter contracts and assumptions

Lower priority and only after stability
- Multi-core scaling experiments
- Visualization and presentation polish

---

## Concrete Phase 2 deliverables

Phase 2 should consist of adapters and parameter sweeps that call into the same SIT Engine core.

Expected deliverables
- Adapter interfaces such as a spike adapter that normalizes events into the Phase 1 ingest format
- Sweep runner capable of executing the same kernels across window sizes and selected simulator knobs
- Golden dataset folder with pinned traces, pinned outputs, and invariant tests
- CI hooks that run golden tests on every pull request to prevent silent regressions

---

## Minimum datasets to proceed

To unblock Phase 2 while Phase 1 is still being refined
- Five to eight micro-kernel traces on Spike including single-core and small multi-core variants
- One memory pressure trace that intentionally forces residency breaks
- One synchronization-heavy trace that stresses barriers and contention
- Optional one real workload trace added later only after golden micro-kernels pass consistently

---

## Closing principle

Phase 1 correctness and stability take precedence over Phase 2 breadth.

Phase 2 exists to validate, stress, and strengthen the Phase 1 SIT Engine, not to dilute it.

This document should be treated as the reference for alignment until explicitly revised.
