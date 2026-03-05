#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

SWEEP_CONFIG="${GEM5_SWEEP_CONFIG:-sweeps/sweep_config_gem5_matrix_practical_exec.json}"
GEM5_WORKLOAD_ORDER="${GEM5_WORKLOAD_ORDER:-fm_loopback,fm_mm,fm_sparse,fm_read,fm_write}"
GEM5_EXCLUDE_WORKLOADS="${GEM5_EXCLUDE_WORKLOADS:-matmul}"
RESULTS_DIR=""
OUTDIR=""
TRACES_DIR=""
declare -a TRACE_FILES=()

usage() {
  cat <<'USAGE'
Usage:
  bash tools/run_gem5_property_suite.sh [OPTIONS]

Modes:
  1) Default (no args): run fresh gem5 reduced-matrix sweep + checks.
  2) Existing sweep results:
       --results-dir <path>
  3) Direct traces (golden + no-work checks + window-time plots):
       --trace <trace.csv> [--trace <trace2.csv> ...]
       --traces-dir <dir_with_trace_csvs>
       [--outdir <output_dir>]

Options:
  --results-dir <path>  Existing sweep results dir to validate.
  --trace <path>        Trace CSV to validate (repeatable).
  --traces-dir <path>   Directory of trace CSVs to validate.
  --outdir <path>       Output dir for trace mode (default: sweeps/results/gem5_tracecheck_<ts>).
  -h, --help            Show help.

Env:
  GEM5_SWEEP_CONFIG     Override sweep config path.
  GEM5_WORKLOAD_ORDER   Override workload order for charts (comma-separated).
  GEM5_EXCLUDE_WORKLOADS
                        Comma-separated workloads excluded from plots/monotonic checks
                        (default: matmul).
USAGE
}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

require_executable() {
  local tool="$1"
  if [[ -x "$tool" ]]; then
    return 0
  fi
  command -v "$tool" >/dev/null 2>&1 || die "missing executable: $tool"
}

resolve_gem5_bin_from_config() {
  python3 - "$SWEEP_CONFIG" <<'PY'
import json
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1]).resolve()
if not cfg_path.exists():
    raise SystemExit(f"missing sweep config: {cfg_path}")

cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
shared = cfg.get("shared", {})
gem5_bin = str(shared.get("gem5_bin", "")).strip() or "gem5.opt"
print(gem5_bin)
PY
}

run_fixture_check() {
  python3 tests/check_adapter_fixtures.py --fixtures gem5
}

run_visualize() {
  local rd="$1"
  python3 sweeps/visualize_sweep_results.py \
    --results-dir "$rd" \
    --workload-order "${GEM5_WORKLOAD_ORDER}" \
    --exclude-workloads "${GEM5_EXCLUDE_WORKLOADS}" \
    --common-title-suffix " (gem5 exec, reduced matrix)"
}

run_monotonic_from_sweep_results() {
  local rd="$1"
  python3 - "$rd" "${GEM5_EXCLUDE_WORKLOADS}" <<'PY'
import csv
import subprocess
import sys
from pathlib import Path

results_dir = Path(sys.argv[1]).resolve()
excluded_workloads = {w.strip() for w in str(sys.argv[2]).split(",") if w.strip()}
sweep_csv = results_dir / "sweep_results.csv"
checker = Path("tests/check_flag_monotonicity.py").resolve()
plots_dir = results_dir / "plots"
plots_dir.mkdir(parents=True, exist_ok=True)
report_csv = plots_dir / "monotonic_report.csv"

if not sweep_csv.exists():
    print(f"SKIP monotonicity: missing {sweep_csv}")
    raise SystemExit(0)

rows = list(csv.DictReader(sweep_csv.open("r", newline="", encoding="utf-8")))
if not rows:
    print("SKIP monotonicity: no rows in sweep_results.csv")
    raise SystemExit(0)

def as_bool(raw: str) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}

def flag_mode(row: dict) -> str:
    bm = as_bool(row.get("branch_mispredict", ""))
    cp = as_bool(row.get("cache_pressure", ""))
    if bm and cp:
        return "both"
    if bm:
        return "branch_mispredict"
    if cp:
        return "cache_pressure"
    return "none"

groups = {}
for row in rows:
    workload = (row.get("workload") or "").strip()
    workload_size = (row.get("workload_size") or "").strip()
    summary_path = (row.get("summary_path") or "").strip()
    if workload in excluded_workloads:
        continue
    if not workload or not workload_size or not summary_path:
        continue
    groups.setdefault((workload, workload_size), {})[flag_mode(row)] = summary_path

report_rows = []
failures = []
for (workload, workload_size), mp in sorted(groups.items()):
    base = mp.get("none", "")
    if not base:
        report_rows.append({
            "workload": workload,
            "workload_size": workload_size,
            "variants_checked": "",
            "status": "skip",
            "reason": "missing baseline",
        })
        continue

    cmd = [
        "python3",
        str(checker),
        "--baseline", base,
        "--min-sit-drop", "0.02",
        "--min-stall-rise", "0.02",
        "--max-idle-rise", "0.20",
    ]
    variants = []
    for arg_name, fm in [
        ("--branch", "branch_mispredict"),
        ("--cache", "cache_pressure"),
        ("--both", "both"),
    ]:
        p = mp.get(fm, "")
        if p:
            cmd += [arg_name, p]
            variants.append(fm)

    if not variants:
        report_rows.append({
            "workload": workload,
            "workload_size": workload_size,
            "variants_checked": "",
            "status": "skip",
            "reason": "no variants",
        })
        continue

    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if text:
        print(text)

    status = "pass" if proc.returncode == 0 else "fail"
    report_rows.append({
        "workload": workload,
        "workload_size": workload_size,
        "variants_checked": ",".join(variants),
        "status": status,
        "reason": "" if proc.returncode == 0 else f"rc={proc.returncode}",
    })
    if proc.returncode != 0:
        failures.append(f"{workload}/{workload_size}")

fields = ["workload", "workload_size", "variants_checked", "status", "reason"]
with report_csv.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(report_rows)
print(f"Wrote: {report_csv}")

if failures:
    print("FAIL monotonicity:", ", ".join(failures))
    raise SystemExit(2)
print("PASS monotonicity checks")
PY
}

run_no_work_mode_checks() {
  local manifest="$1"
  local base_out="$2"
  local plots_dir="${base_out}/plots"
  mkdir -p "${plots_dir}"

  python3 tests/run_golden_suite.py \
    --manifest "$manifest" \
    --outdir "${base_out}/golden_window_active" \
    --window-us 256.0 \
    --no-work-sit-mode window_active

  python3 tests/run_golden_suite.py \
    --manifest "$manifest" \
    --outdir "${base_out}/golden_global_active" \
    --window-us 256.0 \
    --no-work-sit-mode global_active

  python3 tests/check_no_work_sit_modes.py \
    --window-out "${base_out}/golden_window_active" \
    --global-out "${base_out}/golden_global_active" \
    --require-difference \
    --report-csv "${plots_dir}/no_work_sit_mode_report.csv"

  python3 tools/generate_window_time_plots.py \
    --base-out "${base_out}" \
    --platform-label "gem5"
}

build_manifest_from_traces() {
  local manifest_out="$1"
  shift
  python3 - "$manifest_out" "$@" <<'PY'
import json
import sys
from pathlib import Path

manifest_out = Path(sys.argv[1]).resolve()
trace_args = [Path(p).resolve() for p in sys.argv[2:]]

if not trace_args:
    raise SystemExit("no traces provided")

repo = Path.cwd().resolve()
masks_dir = repo / "datasets" / "residency"

manifest = {
    "dataset_version": f"gem5-tracecheck-{len(trace_args)}traces",
    "window_us_default": 256.0,
    "traces": [str(p) for p in trace_args],
    "residency_masks": {
        "all": str((masks_dir / "all.csv").resolve()),
        "skip_w0": str((masks_dir / "skip_w0.csv").resolve()),
        "partial": str((masks_dir / "partial.csv").resolve()),
        "exact_boundary": str((masks_dir / "exact_boundary.csv").resolve()),
    },
}
manifest_out.parent.mkdir(parents=True, exist_ok=True)
manifest_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(manifest_out)
PY
}

pin_copy() {
  local src="$1"
  local i=1
  local dst
  while :; do
    dst="sweeps/pinned/gem5_exec_reduced_matrix_$(date +%Y%m%d)_v${i}"
    [[ ! -e "$dst" ]] && break
    i=$((i + 1))
  done
  cp -a "$src" "$dst"
  echo "PINNED=${dst}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --results-dir)
      RESULTS_DIR="${2:-}"
      shift 2
      ;;
    --trace)
      TRACE_FILES+=("${2:-}")
      shift 2
      ;;
    --traces-dir)
      TRACES_DIR="${2:-}"
      shift 2
      ;;
    --outdir)
      OUTDIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ -f "${SWEEP_CONFIG}" ]] || die "missing sweep config: ${SWEEP_CONFIG}"

require_cmd python3
require_cmd riscv64-linux-gnu-gcc
GEM5_BIN="$(resolve_gem5_bin_from_config)"
require_executable "${GEM5_BIN}"

run_fixture_check

if [[ -n "${RESULTS_DIR}" ]]; then
  rc=0
  [[ -d "${RESULTS_DIR}" ]] || die "--results-dir not found: ${RESULTS_DIR}"
  RESULTS_DIR="$(cd "${RESULTS_DIR}" && pwd)"
  if [[ -f "${RESULTS_DIR}/sweep_results.csv" ]]; then
    run_visualize "${RESULTS_DIR}"
    if ! run_monotonic_from_sweep_results "${RESULTS_DIR}"; then
      rc=1
    fi
  fi
  [[ -f "${RESULTS_DIR}/sweep_manifest.json" ]] || die "missing sweep_manifest.json in ${RESULTS_DIR}"
  if ! run_no_work_mode_checks "${RESULTS_DIR}/sweep_manifest.json" "${RESULTS_DIR}"; then
    rc=1
  fi
  [[ "${rc}" -eq 0 ]] || exit 2
  echo "DONE: ${RESULTS_DIR}"
  exit 0
fi

if [[ ${#TRACE_FILES[@]} -gt 0 || -n "${TRACES_DIR}" ]]; then
  declare -a all_traces=()
  for p in "${TRACE_FILES[@]}"; do
    [[ -e "$p" ]] || die "trace path not found: $p"
    if [[ -d "$p" ]]; then
      while IFS= read -r f; do all_traces+=("$f"); done < <(find "$p" -maxdepth 1 -type f -name '*.csv' | sort)
    else
      all_traces+=("$p")
    fi
  done
  if [[ -n "${TRACES_DIR}" ]]; then
    [[ -d "${TRACES_DIR}" ]] || die "--traces-dir not found: ${TRACES_DIR}"
    while IFS= read -r f; do all_traces+=("$f"); done < <(find "${TRACES_DIR}" -maxdepth 1 -type f -name '*.csv' | sort)
  fi
  [[ ${#all_traces[@]} -gt 0 ]] || die "no trace csv files found"

  if [[ -z "${OUTDIR}" ]]; then
    OUTDIR="sweeps/results/gem5_tracecheck_$(date +%Y%m%d_%H%M%S)"
  fi
  mkdir -p "${OUTDIR}"
  MANIFEST_PATH="${OUTDIR}/manifest_from_traces.json"
  build_manifest_from_traces "${MANIFEST_PATH}" "${all_traces[@]}" >/dev/null
  run_no_work_mode_checks "${MANIFEST_PATH}" "${OUTDIR}"
  echo "DONE: ${OUTDIR}"
  exit 0
fi

python3 sweeps/run_param_sweep.py --config "${SWEEP_CONFIG}"
RESULTS_DIR="$(ls -td sweeps/results/20* | head -1)"
run_visualize "${RESULTS_DIR}"
rc=0
if ! run_monotonic_from_sweep_results "${RESULTS_DIR}"; then
  rc=1
fi
if ! run_no_work_mode_checks "${RESULTS_DIR}/sweep_manifest.json" "${RESULTS_DIR}"; then
  rc=1
fi
if [[ "${rc}" -eq 0 ]]; then
  pin_copy "${RESULTS_DIR}"
fi
[[ "${rc}" -eq 0 ]] || exit 2
echo "DONE: ${RESULTS_DIR}"
