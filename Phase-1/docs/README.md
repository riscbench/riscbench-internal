# Phase-1 Docs Layout

- `phase1_technical_document.tex`: technical write-up source
- `phase1_deliverables_matrix.tex`: 11-deliverable fulfillment matrix with architecture notes and Mermaid flow blocks
- `VALIDATION_PHASE1.tex`: LaTeX technical document for Validation Suite (purpose, invariants, CI hooks, done-when mapping)
- `PHASE0_TRACE_UTILIZATION_VALIDATION.tex`: LaTeX validation document mapping how Phase-0 Tenstorrent trace logic is carried into Phase-1 engine behavior and Phase-2 adapter pathways
- `REFERENCE_DATASETS_PHASE1.tex`: LaTeX technical document for Reference Datasets (manifest contract, governance, lifecycle, done-when mapping)
- `VALIDATION_PHASE1.md`: detailed Validation Suite architecture, invariants, CI gating, and done-when mapping (includes Phase-2 invariant alignment)
- `REFERENCE_DATASETS_PHASE1.md`: detailed Reference Datasets contract, governance, replay integration, and done-when mapping
- `deliverables/`: separate LaTeX documents (no unified file) for each Phase-1 deliverable:
  - `01_SIT_Engine_Core.tex`
  - `02_Time_and_Windowing.tex`
  - `03_Residency_Model.tex`
  - `04_Trace_Ingestion_API.tex`
  - `05_Baseline_Adapter.tex`
  - `06_Output_Schema_v1.tex`
  - `07_Validation_Suite.tex`
  - `08_Reference_Datasets.tex`
  - `09_CLI_Pipeline.tex`
  - `10_Documentation.tex`
  - `11_CI_Hooks.tex`
- `guides/`: conceptual guides and generalization notes
- `status/`: delivery/progress dashboards
- `runbooks/`: command-oriented operator notes
- `mermaid/`: architecture/workflow diagrams
  - `mermaid/deliverables/*.mmd`: archived Mermaid source flowcharts (optional/reference)
  - `mermaid/render_deliverables.sh`: optional Mermaid-to-PNG helper

Current LaTeX status:
- `phase1_technical_document.tex`: native TikZ diagrams (no Mermaid conversion needed)
- `phase1_deliverables_matrix.tex`: native TikZ flowcharts (no Mermaid conversion needed)
