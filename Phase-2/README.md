# Phase 2 – Simulator Integrations

## Purpose
Phase 2 integrates simulators with the RISCBench SIT Engine. This phase exists to **feed data into Phase 1**, not to reinterpret or reimplement SIT.

## Scope
Included
- Simulator adapters
- Parameter sweeps
- Validation against golden traces

Explicitly excluded
- Any new SIT computation logic
- Simulator-specific performance metrics in the core engine
- Schema-breaking changes

## Architectural rule
All Phase-2 components must call the Phase-1 SIT Engine as a black box.

## Supported simulators (order)
1. Spike
2. QEMU
3. gem5

## Required reading
- Phase-0/README.md
- Phase-1/README.md
- Phase-1/GENERALIZATION.md
