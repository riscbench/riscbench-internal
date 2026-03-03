# Phase 2 – Adapter Contract

## Adapter definition
An adapter normalizes simulator-specific traces into the Phase-1 ingest format.

Adapters must not
- Compute SIT
- Apply residency logic
- Aggregate windows

## Required adapter outputs
- Timestamped events
- Core or thread identifier
- Memory residency signal or inference
- Trace quality metadata

## Residency confidence
Adapters must declare whether residency is
- Explicit (reported by simulator)
- Inferred (heuristic)

## Design principle
API-first. Adapters exist to simplify extension, not encode assumptions.
