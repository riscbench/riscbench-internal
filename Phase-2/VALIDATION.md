# Phase 2 – Validation and Golden Artifacts

## Validation philosophy
Correctness precedes coverage.

## Golden artifacts
1. Golden micro-kernel traces
2. Golden output schemas
3. Golden invariants

## Example invariants
- SIT must not exceed normalized peak
- Increased residency increases SIT when compute is constant
- Injected stalls reduce median SIT monotonically

## CI usage
All adapters must pass golden invariant checks before merge.
