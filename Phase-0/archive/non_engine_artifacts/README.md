# Archived non-engine artifacts

This folder contains root-level files/directories moved out of the active Phase-1 engine pipeline path.

## Categories
- `legacy_binaries/`: compiled or standalone binaries/ELFs not required by Phase-1 ingest/classify/export.
- `legacy_sources/`: root-level source snapshots/backup files not required by the Phase-1 pipeline.
- `legacy_build/`: legacy build trees (e.g., local `riscv-isa-sim` build output).
- `legacy_adapters/`: root-level adapter copy not used by `Phase-1/cli.py` and `Phase-1/riscvbench.py`.

## Engine path kept intact
- `Phase-1/` code and datasets
- top-level `runs/` and `results/` directories
- repository documentation
