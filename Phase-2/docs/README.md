# Phase-2 Docs

This folder is the documentation index for Phase-2 deliverables.
It is written so a first-time reader can understand what each document is for, what code it maps to, and when to read it.

## Recommended Reading Order (Using Existing Docs)

1. [../README.md](../README.md)
   - Defines Phase-2 scope, architecture, data flow, and command entrypoints.
   - Read this first to understand the full pipeline.

2. [../ADAPTERS.md](../ADAPTERS.md)
   - Defines adapter responsibilities and strict boundaries.
   - Use this before modifying parser logic, state classification, or residency inference.

3. Platform runbook for your target:
   - [platforms/spike/README.md](platforms/spike/README.md)
   - [platforms/qemu/README.md](platforms/qemu/README.md)
   - [platforms/gem5/README.md](platforms/gem5/README.md)

4. Deliverable LaTeX docs in `deliverables/` and `platforms/*/deliverables/`
   - Use these for deep design review and deliverable evidence.

## Core Reference Docs in This Folder

- [Adapter_contract.tex](Adapter_contract.tex)
  - Detailed adapter contract explanation and flow.
- [Spike_simulator_adapter.md](Spike_simulator_adapter.md)
  - Spike adapter behavior and state/residency interpretation notes.
- [Spike_simulator_adapter.tex](Spike_simulator_adapter.tex)
  - Formal LaTeX variant of Spike adapter design.
- [phase2_deliverables_matrix.tex](phase2_deliverables_matrix.tex)
  - Full 10-deliverable matrix and done-when mapping.
- [phase2_open_deliverables_plan.tex](phase2_open_deliverables_plan.tex)
  - Closure plan for items that are partial or pending.

## Deliverable Docs (`deliverables/`) — What Each One Covers

- [deliverables/01_Phase2_README.tex](deliverables/01_Phase2_README.tex)
  - Scope and control-plane documentation role.
  - Maps reader workflow to concrete code entrypoints.

- [deliverables/02_Spike_Simulator_Adapter.tex](deliverables/02_Spike_Simulator_Adapter.tex)
  - Spike adapter normalization path and output contract.
  - Focus on parser responsibilities vs engine responsibilities.

- [deliverables/03_Adapter_Contract.tex](deliverables/03_Adapter_Contract.tex)
  - Formal contract boundary and no-semantic-leakage rules.
  - Explicitly separates allowed adapter logic from forbidden engine logic.

- [deliverables/04_Golden_Microkernel_Traces.tex](deliverables/04_Golden_Microkernel_Traces.tex)
  - Golden trace generation and versioning expectations.
  - Reproducibility and pinning requirements.

- [deliverables/05_Golden_Output_Artifacts.tex](deliverables/05_Golden_Output_Artifacts.tex)
  - Expected windows/summary artifacts and deterministic replay behavior.

- [deliverables/07_Parameter_Sweep_Runner.tex](deliverables/07_Parameter_Sweep_Runner.tex)
  - Sweep execution architecture and metadata separation from SIT schema.

- [deliverables/08_Dataset_Governance.tex](deliverables/08_Dataset_Governance.tex)
  - Provenance/versioning requirements and governance workflow.

- [deliverables/09_CI_Integration.tex](deliverables/09_CI_Integration.tex)
  - CI replay/invariant gates and deterministic failure expectations.

## Platform-Specific Deliverable Folders

- [platforms/spike/README.md](platforms/spike/README.md)
  - Spike-specific purpose, commands, artifact expectations, and deliverable mapping.

- [platforms/qemu/README.md](platforms/qemu/README.md)
  - QEMU-specific purpose, dynamic event-time interpretation, exit policy notes, and deliverable mapping.

- [platforms/gem5/README.md](platforms/gem5/README.md)
  - gem5-specific purpose, stats/exec integration path, and deliverable mapping.

## How To Use These Docs During Implementation

1. Start in `../README.md` to understand full flow and commands.
2. Enforce adapter boundaries with `../ADAPTERS.md` before coding.
3. Use the target runbook in `platforms/<target>/README.md` for exact commands and expected files.
4. Use corresponding platform deliverable `.tex` files to verify design intent and function-level flow.
5. Run validation scripts referenced in the runbook before considering the change complete.
