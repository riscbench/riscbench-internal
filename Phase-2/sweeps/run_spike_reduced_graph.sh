#!/usr/bin/env bash
set -euo pipefail

# Single-command wrapper:
# 1) runs the Spike reduced matrix sweep
# 2) generates plots (including common_sit_median_by_workload.*)
# 3) copies the run into sweeps/pinned
#
# Usage:
#   bash Phase-2/sweeps/run_spike_reduced_graph.sh
#   bash Phase-2/sweeps/run_spike_reduced_graph.sh Phase-2/sweeps/pinned/spike_exec_reduced_matrix_custom_v1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

SWEEP_CFG="Phase-2/sweeps/sweep_config_spike_matrix_practical.json"
TITLE_SUFFIX=" (spike, reduced matrix)"

PIN_DIR="${1:-}"
if [[ -z "${PIN_DIR}" ]]; then
  PIN_DIR="Phase-2/sweeps/pinned/spike_exec_reduced_matrix_$(date -u +%Y%m%d_%H%M%S)"
fi

if [[ ! -f "${SWEEP_CFG}" ]]; then
  echo "Missing config: ${SWEEP_CFG}" >&2
  exit 2
fi

echo "[1/3] Running spike reduced sweep..."
python3 Phase-2/sweeps/run_param_sweep.py --config "${SWEEP_CFG}"

RUN_DIR="$(ls -1dt Phase-2/sweeps/results/* | head -n1)"
if [[ -z "${RUN_DIR}" || ! -d "${RUN_DIR}" ]]; then
  echo "Could not resolve results directory" >&2
  exit 2
fi
echo "Resolved run dir: ${RUN_DIR}"

echo "[2/3] Building plots..."
python3 Phase-2/sweeps/visualize_sweep_results.py \
  --results-dir "${RUN_DIR}" \
  --common-title-suffix "${TITLE_SUFFIX}"

if [[ -e "${PIN_DIR}" ]]; then
  echo "Pin destination already exists: ${PIN_DIR}" >&2
  exit 2
fi

echo "[3/3] Pinning run..."
cp -a "${RUN_DIR}" "${PIN_DIR}"

echo
echo "Pinned outputs:"
echo "  ${PIN_DIR}/plots/common_sit_median_by_workload.svg"
echo "  ${PIN_DIR}/plots/common_sit_median_by_workload.csv"
