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

3. [../DATASETS.md](../DATASETS.md)
   - Dataset governance policy (version bumps, immutability, replay and determinism gates).

4. [../VALIDATION.md](../VALIDATION.md)
   - Contributor-facing validation workflow and done-when checklist.

5. Platform runbook for your target:
   - [platforms/spike/README.md](platforms/spike/README.md)
   - [platforms/qemu/README.md](platforms/qemu/README.md)
   - [platforms/gem5/README.md](platforms/gem5/README.md)

6. Consolidated key references + all-checks entrypoint:
   - [platforms/KEY_REFERENCES_AND_ALL_CHECKS.md](platforms/KEY_REFERENCES_AND_ALL_CHECKS.md)

7. Deliverable LaTeX docs in `deliverables/` and `platforms/*/deliverables/`
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

## Platform Factor Terminology

Use this normalized terminology in docs, plots, and report summaries:

- Workload/orchestration factors
- Runtime/OS factors
- Microarchitectural timing factors
- Measurement overhead

Methodological note: Spike and QEMU do not model microarchitectural timing; gem5 and hardware platforms may.

## Cross-Platform Flag Graph Note

To regenerate the cross-platform flag comparison bundle (QEMU/Spike/gem5):

```bash
cd Phase-2
python3 tools/generate_platform_comparison_graphs.py
```

Outputs are written to `Phase-2/docs/platforms/plots/`:
- `platform_flag_gradient_summary.csv`
- `cross_platform_sit_median_by_flag.svg`
- `cross_platform_residency_stall_by_flag.svg`
- `cross_platform_sit_drop_vs_none.svg`
- `cross_platform_stall_rise_vs_none.svg`

QEMU interpretation note:
- QEMU adapter works at translated-block (TB) granularity.
- If a TB mixes memory + compute/control instructions, it is classified as `TB_ACTIVE`.
- Only TBs that are memory-only become `TB_STALL`.
- This can bias `active_frac` upward and `stall_frac` downward in QEMU relative to instruction-level adapters, which can raise fallback SIT values.

Global-vs-window SIT sample commands (single testcase):

```bash
cd Phase-2
source .venv-phase2/bin/activate

# Run 1: no-work fallback = global_active
riscvbench \
  --target qemu \
  --workload fm_mm \
  --workload_size test \
  --time_us 256 \
  --expected-work-rate 1.0 \
  --allow-nonzero-exit \
  --no-work-sit-mode global_active
cp runs/qemu/fm_mm/test/run_windows.csv runs/qemu/fm_mm/test/run_windows_global_active.csv
cp runs/qemu/fm_mm/test/run_summary.json runs/qemu/fm_mm/test/run_summary_global_active.json

# Run 2: no-work fallback = window_active
riscvbench \
  --target qemu \
  --workload fm_mm \
  --workload_size test \
  --time_us 256 \
  --expected-work-rate 1.0 \
  --allow-nonzero-exit \
  --no-work-sit-mode window_active
cp runs/qemu/fm_mm/test/run_windows.csv runs/qemu/fm_mm/test/run_windows_window_active.csv
cp runs/qemu/fm_mm/test/run_summary.json runs/qemu/fm_mm/test/run_summary_window_active.json

# Compare per-window SIT columns from both runs
python3 - <<'PY'
import csv
from pathlib import Path

base = Path("runs/qemu/fm_mm/test")
g = list(csv.DictReader((base / "run_windows_global_active.csv").open()))
w = list(csv.DictReader((base / "run_windows_window_active.csv").open()))

print("window_id, sit(global_mode), sit(window_mode), sit_no_work_global_active, sit_no_work_window_active, active_frac, stall_frac")
for rg, rw in zip(g[:12], w[:12]):
    print(
        rg["window_id"], ",",
        rg["sit"], ",",
        rw["sit"], ",",
        rw["sit_no_work_global_active"], ",",
        rw["sit_no_work_window_active"], ",",
        rw["active_frac"], ",",
        rw["stall_frac"],
    )
PY
```

Active/stall/idle window-cycle visualization (bash-only, existing `run_windows.csv` files):

```bash
cd Phase-2
source .venv-phase2/bin/activate

# Spike: single workload
python3 sweeps/plot_spike_window_diagnostics.py \
  --windows-csv runs/spike/fm_mm/test/run_windows.csv \
  --out-dir docs/platforms/plots/workload_cycles/spike \
  --prefix spike_fm_mm_test

# Spike: all FM workloads (test)
for w in fm_loopback fm_mm fm_sparse fm_read fm_write; do
  f="runs/spike/$w/test/run_windows.csv"
  [ -f "$f" ] || continue
  python3 sweeps/plot_spike_window_diagnostics.py \
    --windows-csv "$f" \
    --out-dir docs/platforms/plots/workload_cycles/spike \
    --prefix "spike_${w}_test"
done

# gem5: single workload
python3 sweeps/plot_spike_window_diagnostics.py \
  --windows-csv runs/gem5/fm_mm/test/run_windows.csv \
  --out-dir docs/platforms/plots/workload_cycles/gem5 \
  --prefix gem5_fm_mm_test

# gem5: all FM workloads (test)
for w in fm_loopback fm_mm fm_sparse fm_read fm_write; do
  f="runs/gem5/$w/test/run_windows.csv"
  [ -f "$f" ] || continue
  python3 sweeps/plot_spike_window_diagnostics.py \
    --windows-csv "$f" \
    --out-dir docs/platforms/plots/workload_cycles/gem5 \
    --prefix "gem5_${w}_test"
done
```

Python quick checks on generated `__window_breakdown.csv` files:

```bash
cd Phase-2

# 1) One-file weighted split (active/idle/stall inside residency)
# Meaning: reports residency-weighted fractions for a single workload.
python3 - <<'PY'
import csv
from pathlib import Path

p = Path("docs/platforms/plots/workload_cycles/gem5/gem5_fm_mm_test__window_breakdown.csv")
rows = list(csv.DictReader(p.open()))
res = sum(float(r["resident_us"]) for r in rows)
act = sum(float(r["resident_compute_us"]) for r in rows)
idl = sum(float(r["idle_us"]) for r in rows)
stl = sum(float(r["memory_attributed_us"]) for r in rows)
print("file:", p)
print("active_frac=", round(act / res, 6), "idle_frac=", round(idl / res, 6), "stall_frac=", round(stl / res, 6))
PY

# 2) Per-workload summary table (all gem5 FM breakdown CSVs)
# Meaning: shows which workload is most active-heavy vs stall-heavy.
python3 - <<'PY'
import csv
from pathlib import Path

root = Path("docs/platforms/plots/workload_cycles/gem5")
files = sorted(root.glob("gem5_fm_*_test__window_breakdown.csv"))
print("workload,active_frac,idle_frac,stall_frac,resident_us_total")
for p in files:
    rows = list(csv.DictReader(p.open()))
    res = sum(float(r["resident_us"]) for r in rows)
    if res <= 0:
        continue
    act = sum(float(r["resident_compute_us"]) for r in rows) / res
    idl = sum(float(r["idle_us"]) for r in rows) / res
    stl = sum(float(r["memory_attributed_us"]) for r in rows) / res
    wl = p.name.replace("gem5_", "").replace("_test__window_breakdown.csv", "")
    print(f"{wl},{act:.6f},{idl:.6f},{stl:.6f},{res:.1f}")
PY

# 3) Spike vs gem5 for the same workload
# Meaning: direct platform comparison of active/idle/stall mix for one workload.
python3 - <<'PY'
import csv
from pathlib import Path

pairs = {
    "spike": Path("docs/platforms/plots/workload_cycles/spike/spike_fm_mm_test__window_breakdown.csv"),
    "gem5": Path("docs/platforms/plots/workload_cycles/gem5/gem5_fm_mm_test__window_breakdown.csv"),
}
print("platform,active_frac,idle_frac,stall_frac,resident_us_total")
for plat, p in pairs.items():
    if not p.exists():
        print(f"{plat},MISSING,MISSING,MISSING,0")
        continue
    rows = list(csv.DictReader(p.open()))
    res = sum(float(r["resident_us"]) for r in rows)
    if res <= 0:
        print(f"{plat},0,0,0,0")
        continue
    act = sum(float(r["resident_compute_us"]) for r in rows) / res
    idl = sum(float(r["idle_us"]) for r in rows) / res
    stl = sum(float(r["memory_attributed_us"]) for r in rows) / res
    print(f"{plat},{act:.6f},{idl:.6f},{stl:.6f},{res:.1f}")
PY
```

## How To Use These Docs During Implementation

1. Start in `../README.md` to understand full flow and commands.
2. Enforce adapter boundaries with `../ADAPTERS.md` before coding.
3. Use the target runbook in `platforms/<target>/README.md` for exact commands and expected files.
4. Use corresponding platform deliverable `.tex` files to verify design intent and function-level flow.
5. Run validation scripts referenced in the runbook before considering the change complete.
