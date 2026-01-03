# Phase 2 – Parameter Sweeps

## Purpose
Sweeps explore sensitivity without changing semantics.

## Allowed sweep dimensions
- Window size
- Memory latency
- Cache or SRAM capacity (simulator-exposed)

## Recording rules
Sweep parameters must be recorded as metadata, not core schema fields.

## Prohibited behavior
- Ad-hoc experiment logic
- Hard-coded simulator constants
