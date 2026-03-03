# Contributing to RISCBench

## Mandatory reading before any contribution
All contributors must read and understand
- Phase-0/README.md
- Phase-1/GENERALIZATION.md

PRs that violate these semantics will be closed.

## Phase-2 specific contribution rules
Phase-2 contributions are limited to
- Simulator adapters
- Parameter sweep infrastructure
- Validation artifacts

Required reading for Phase-2 work
- Phase-2/README.md
- Phase-2/ADAPTERS.md
- Phase-2/VALIDATION.md

Explicitly forbidden in Phase-2
- Reimplementation of SIT logic
- Simulator-specific metrics inside the core engine
- Schema-breaking changes without versioning

Contributors must state in their PR description which Phase-2 documents were followed.
