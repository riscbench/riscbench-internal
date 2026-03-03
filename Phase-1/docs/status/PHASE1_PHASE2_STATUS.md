# Phase-1 and Phase-2 Deliverable Status (Detailed Tracking Snapshot)

This document expands the original status snapshot with:
- what was asked to implement,
- what is currently implemented in this repository,
- design considerations and assumptions per section,
- run commands (where runnable independently), and
- percentage completion for each section plus overall Phase-1/Phase-2 progress.

> **Scoring rule used for percentages**: Completed = 100%, Partially completed = 50%, Not completed = 0%.

## Overall progress

- **Phase-1 overall**: **100.0%** \(11 completed + 0 partial + 0 not completed = 11.0 / 11\)  
  Progress color: <span style="color:#22c55e;"><strong>🟩 Green</strong></span>
- **Phase-2 overall**: **20.0%** \(0 completed + 4 partial + 6 not completed = 2.0 / 10\)  
  Progress color: <span style="color:#ef4444;"><strong>🟥 Red</strong></span>

---

## Phase-1 deliverables (same order)

### 1) SIT Engine core
- **Asked to implement:** Core engine for fixed-window SIT computation and summary metrics.
- **Implemented in repo:** `sit_engine_phase1.py` implements window slicing, accumulation, SIT calculation, and summary generation.
- **Design considerations & assumptions:** Uses deterministic half-open windowing and clamps SIT to [0,1]; assumes valid normalized intervals.
- **How to run / validate section:** `python cli.py classify --in runs/A --window-us 256` (after ingest).
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 2) Time and windowing
- **Asked to implement:** Canonical time slicing and exact-boundary behavior.
- **Implemented in repo:** Implemented in engine with half-open intervals and boundary epsilon logic.
- **Design considerations & assumptions:** Assumes microsecond float timestamps and no negative-duration intervals.
- **How to run / validate section:** `python cli.py classify --in runs/A --window-us 256`.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 3) Residency model
- **Asked to implement:** Gate state accounting by residency masks.
- **Implemented in repo:** Residency merging + intersection logic implemented in engine.
- **Design considerations & assumptions:** Assumes residency intervals are per-core and mergeable; non-resident windows can be NaN for fractions.
- **How to run / validate section:** `python cli.py classify --in runs/A --window-us 256 --residency datasets/residency/partial.csv`.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 4) Trace ingestion API
- **Asked to implement:** Normalized state/residency contract and validation entrypoint.
- **Implemented in repo:** `ingest/ingest_api.py` defines schema/validators used by adapters.
- **Design considerations & assumptions:** Adapter boundary keeps core engine format-agnostic; assumes adapters output normalized columns.
- **How to run / validate section:** `python cli.py ingest --trace datasets/traces/trace_A_single_residency.csv --out runs/A`.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 5) Baseline adapter
- **Asked to implement:** Reference adapter for baseline CSV/raw traces.
- **Implemented in repo:** `adapters/baseline_adapter.py` present and wired through ingest.
- **Design considerations & assumptions:** Keeps parsing-specific details out of engine; assumes baseline source fields are mappable to contract.
- **How to run / validate section:** `python cli.py ingest --trace datasets/traces/trace_A_single_residency.csv --out runs/A`.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 6) Output schema v1
- **Asked to implement:** Versioned export schema and validation checks.
- **Implemented in repo:** `schema/v1.py` + `cli.py export` produce `windows_v1.csv`, `summary_v1.json`.
- **Design considerations & assumptions:** Stable contract intended for downstream tooling; assumes v1 fields remain backward-compatible.
- **How to run / validate section:** `python cli.py export --in runs/A --schema v1`.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 7) Validation suite
- **Asked to implement:** Invariant and regression/golden checks.
- **Implemented in repo:** `tests/check_invariants.py` and `tests/run_golden_suite.py` exist.
- **Design considerations & assumptions:** Validation split into single-output invariants + dataset-level golden checks; assumes dependencies installed.
- **How to run / validate section:** `python tests/run_golden_suite.py --outdir golden_out`.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 8) Reference datasets
- **Asked to implement:** Pinned manifest and reference traces/masks.
- **Implemented in repo:** `datasets/manifest.json` and datasets folders exist.
- **Design considerations & assumptions:** Reproducibility depends on immutable dataset pointers; assumes manifest paths remain valid.
- **How to run / validate section:** `python tests/run_golden_suite.py --manifest datasets/manifest.json --outdir golden_out`.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 9) CLI pipeline
- **Asked to implement:** User pipeline (`ingest -> classify -> export`).
- **Implemented in repo:** `cli.py` exposes all three stages.
- **Design considerations & assumptions:** Explicit staged pipeline supports troubleshooting and partial reruns.
- **How to run / validate section:** `python cli.py --help` and each subcommand independently.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 10) Documentation
- **Asked to implement:** Phase-1 docs + requested checklist docs.
- **Implemented in repo:** `README.md` and `docs/phase1_technical_document.tex` exist and cover required Phase-1 documentation scope.
- **Design considerations & assumptions:** Repository documentation baseline is considered complete for Phase-1 acceptance.
- **How to run / validate section:** `python cli.py --help` (operational doc cross-check).
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

### 11) CI hooks
- **Asked to implement:** Automated workflow(s) for repeatable validation.
- **Implemented in repo:** `.github/workflows/phase1-ci.yml` is present and documents/install-runs validation hooks.
- **Design considerations & assumptions:** CI can install package/dependencies then run commands such as `riscvbench --target ...` in validation flow.
- **How to run / validate section:** Workflow file inspection plus quick command parity in docs.
- **Completion:** <span style="color:#22c55e;">100% 🟩</span>

---

## Phase-2 deliverables (same order)

### 1) Phase-2 README
- **Asked to implement:** Dedicated `Phase-2/README.md` with scope and workflow.
- **Implemented in repo:** Not found in repository snapshot.
- **Design considerations & assumptions:** Assumes Phase-2 docs may be planned but not yet added to this repo.
- **How to run / validate section:** Not runnable (doc artifact missing).
- **Completion:** <span style="color:#ef4444;">0% 🟥</span>

### 2) Spike simulator adapter
- **Asked to implement:** Adapter for Spike traces into normalized contract.
- **Implemented in repo:** `adapters/spike_adapter.py` exists and emits normalized intervals.
- **Design considerations & assumptions:** Design follows Phase-1 adapter boundary; assumes Phase-2 packaging/docs still pending.
- **How to run / validate section:** Indirect validation via ingestion pipeline and workload runner.
- **Completion:** <span style="color:#f59e0b;">50% 🟨</span>

### 3) Adapter contract
- **Asked to implement:** Phase-2 adapter contract doc (`Phase-2/ADAPTERS.md`).
- **Implemented in repo:** Not found in repository snapshot.
- **Design considerations & assumptions:** Assumes current source-level behavior exists, but formal Phase-2 contract doc is missing.
- **How to run / validate section:** Not runnable (doc artifact missing).
- **Completion:** <span style="color:#ef4444;">0% 🟥</span>

### 4) Golden micro-kernel traces
- **Asked to implement:** Phase-2 pinned trace set for micro-kernels.
- **Implemented in repo:** No explicit Phase-2 trace package found.
- **Design considerations & assumptions:** Assumes current traces may be reusable but not labeled/governed as Phase-2 set.
- **How to run / validate section:** Not runnable as dedicated Phase-2 artifact.
- **Completion:** <span style="color:#ef4444;">0% 🟥</span>

### 5) Golden output artifacts
- **Asked to implement:** Phase-2 golden outputs/versioning.
- **Implemented in repo:** `golden_out/` has outputs but no explicit Phase-2 versioning package/doc.
- **Design considerations & assumptions:** Assumes outputs are preliminary and need formalized Phase-2 artifact governance.
- **How to run / validate section:** `python tests/run_golden_suite.py --outdir golden_out`.
- **Completion:** <span style="color:#f59e0b;">50% 🟨</span>

### 6) Invariant validation suite
- **Asked to implement:** Phase-2-focused invariant checks and guide.
- **Implemented in repo:** Generic invariant scripts exist under `tests/`, but no Phase-2-specific guide/package.
- **Design considerations & assumptions:** Assumes current checks are foundational and need Phase-2 framing/rules.
- **How to run / validate section:** `python tests/check_invariants.py --help` (currently dependency-gated).
- **Completion:** <span style="color:#f59e0b;">50% 🟨</span>

### 7) Parameter sweep runner
- **Asked to implement:** Runner for controlled parameter sweeps across targets.
- **Implemented in repo:** `run_cross_target_suite.py` exists, but no explicit Phase-2 sweep governance metadata.
- **Design considerations & assumptions:** Assumes runner is functional baseline pending policy/doc completion.
- **How to run / validate section:** `python run_cross_target_suite.py --help`.
- **Completion:** <span style="color:#f59e0b;">50% 🟨</span>

### 8) Dataset governance
- **Asked to implement:** `Phase-2/DATASETS.md` policy and maintenance process.
- **Implemented in repo:** Not found in repository snapshot.
- **Design considerations & assumptions:** Assumes manifest exists but governance policy is not yet codified for Phase-2.
- **How to run / validate section:** Not runnable (policy artifact missing).
- **Completion:** <span style="color:#ef4444;">0% 🟥</span>

### 9) CI integration
- **Asked to implement:** Automated CI gating for Phase-2 replay/validation.
- **Implemented in repo:** No dedicated Phase-2 workflow integration found in repository snapshot.
- **Design considerations & assumptions:** Assumes CI for Phase-2 may be deferred.
- **How to run / validate section:** Not runnable in-repo (Phase-2 workflow files absent).
- **Completion:** <span style="color:#ef4444;">0% 🟥</span>

### 10) Phase-2 validation guide
- **Asked to implement:** `Phase-2/VALIDATION.md` with acceptance process.
- **Implemented in repo:** Not found in repository snapshot.
- **Design considerations & assumptions:** Assumes existing scripts are insufficient without formal validation guide.
- **How to run / validate section:** Not runnable (guide missing).
- **Completion:** <span style="color:#ef4444;">0% 🟥</span>

---

## Quick runnable command set (venv-first, section-wise friendly)

```bash
# 0) Create + activate local virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 1) Inspect CLI sections
python cli.py --help

# 2) Run ingestion section independently
python cli.py ingest --trace datasets/traces/trace_A_single_residency.csv --out runs/A

# 3) Run classify section independently
python cli.py classify --in runs/A --window-us 256 --residency datasets/residency/partial.csv

# 4) Run export section independently
python cli.py export --in runs/A --schema v1

# 5) Run golden regression section
python tests/run_golden_suite.py --outdir golden_out

# 6) Run invariant section (requires numpy)
python tests/check_invariants.py --windows golden_out/A_partial_windows.csv --mode partial --window-us 256

# 7) Run cross-target sweep runner section (help shown without needing pk)
python run_cross_target_suite.py --help
```

## Environment caveat

- `tests/check_invariants.py` imports `numpy`; in this environment `numpy` may be missing, so full invariant execution can be dependency-gated.
