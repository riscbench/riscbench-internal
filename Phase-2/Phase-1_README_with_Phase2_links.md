# Phase 1 – SIT Engine Core

## Role of Phase 1
Phase 1 defines the hardware-agnostic SIT Engine. It is the single source of truth for
- windowing
- residency semantics
- SIT accumulation
- output schema

All later phases must call into this engine.

## Required reading order
1. Phase-0/README.md
2. Phase-1/GENERALIZATION.md
3. This document

## Relationship to Phase 2
Phase 2 exists to integrate simulators and run parameter sweeps.
Phase 2 must not reimplement or reinterpret SIT logic.

Phase-2 documentation:
- Phase-2/README.md
- Phase-2/ADAPTERS.md
- Phase-2/VALIDATION.md
- Phase-2/SWEEPS.md
- Phase-2/DATASETS.md
- Phase-2/CI.md

Any Phase-2 contribution must demonstrate compatibility with the Phase-1 engine
and preserve all invariants defined here.
