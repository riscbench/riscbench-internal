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

# Phase-2 Deliverables  
**Simulator Integrations – Engineering Execution Table**

| S/N | Deliverable | Description | What Ships | Done-When |
|---|---|---|---|---|
| 1 | Phase-2 README | Defines Phase-2 scope as adapters and parameter sweeps only, forbidding SIT reimplementation | Phase-2/README.md | Approved and cross-linked from Phase-1 |
| 2 | Spike simulator adapter | Normalizes Spike traces into Phase-1 ingest format | spike_adapter module | Golden kernels reproduce expected SIT behavior |
| 3 | Adapter contract | Formal specification of adapter responsibilities and boundaries | Phase-2/ADAPTERS.md | All adapters conform without semantic leakage |
| 4 | Golden micro-kernel traces | Deterministic kernels anchoring correctness across simulators | Pinned trace files | Traces reproducible and versioned |
| 5 | Golden output artifacts | Expected SIT outputs tied to engine and schema versions | Parquet / JSON artifacts | Outputs match exactly across reruns |
| 6 | Invariant validation suite | Simulator-independent correctness checks | Validation scripts | All invariants pass before merge |
| 7 | Parameter sweep runner | Controlled exploration of window size and simulator knobs | Sweep tooling | Sweep metadata recorded without schema pollution |
| 8 | Dataset governance | Rules for dataset provenance, immutability, and review | Phase-2/DATASETS.md | Dataset changes are gated and versioned |
| 9 | CI integration | Automated replay of golden traces and invariants | CI configuration | Any regression fails deterministically |
| 10 | Phase-2 validation guide | Contributor-facing validation and debugging workflow | Phase-2/VALIDATION.md | New adapters validated without tribal knowledge |
