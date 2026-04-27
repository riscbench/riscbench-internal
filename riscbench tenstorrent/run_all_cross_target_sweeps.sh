#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="${PYTHON:-python3}"
fi

TIME_US="${TIME_US:-256}"
SIMULATORS="${SIMULATORS:-qemu,spike,gem5}"
SIM_CLASSIFICATION_MODE="${SIM_CLASSIFICATION_MODE:-compute_biased}"
GEM5_ADAPTER_MODE="${GEM5_ADAPTER_MODE:-exec}"
ALLOW_NONZERO_EXIT="${ALLOW_NONZERO_EXIT:-1}"
RESUME_AFTER="${RESUME_AFTER:-}"
PRUNE_RUNS_AFTER_CASE="${PRUNE_RUNS_AFTER_CASE:-0}"

required_env=(
  QEMU_BIN
  QEMU_CC
  PK
  GEM5_BIN
  GEM5_ROOT
  GEM5_CC
)

missing=()
for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("${name}")
  fi
done

if (( ${#missing[@]} > 0 )); then
  cat <<MSG
Missing required environment variables:
  ${missing[*]}

Set them first, for example:
  export QEMU_BIN=/usr/bin/qemu-riscv64
  export QEMU_CC=/usr/bin/riscv64-linux-gnu-gcc
  export PK=/home/dev_srinidhi/opt/riscv/riscv64-unknown-elf/bin/pk
  export GEM5_BIN=/home/dev_srinidhi/opt/gem5/build/RISCV/gem5.opt
  export GEM5_ROOT=/home/dev_srinidhi/opt/gem5
  export GEM5_CC=/usr/bin/riscv64-linux-gnu-gcc
MSG
  exit 1
fi

COMMON_ARGS=(
  --target tenstorrent
  --time-us "${TIME_US}"
  --simulators "${SIMULATORS}"
  --sim-trace-only
  --sim-classification-mode "${SIM_CLASSIFICATION_MODE}"
  --qemu-bin "${QEMU_BIN}"
  --qemu-cc "${QEMU_CC}"
  --pk "${PK}"
  --gem5-bin "${GEM5_BIN}"
  --gem5-root "${GEM5_ROOT}"
  --gem5-cc "${GEM5_CC}"
  --gem5-adapter-mode "${GEM5_ADAPTER_MODE}"
)

if [[ "${ALLOW_NONZERO_EXIT}" == "1" ]]; then
  COMMON_ARGS+=(--allow-nonzero-exit)
fi

resume_pending=0
resume_workload=""
resume_size=""
if [[ -n "${RESUME_AFTER}" ]]; then
  resume_pending=1
  resume_workload="${RESUME_AFTER%%:*}"
  resume_size="${RESUME_AFTER#*:}"
  if [[ -z "${resume_workload}" || -z "${resume_size}" || "${resume_workload}" == "${resume_size}" ]]; then
    echo "Invalid RESUME_AFTER='${RESUME_AFTER}'. Expected format: workload:size"
    exit 1
  fi
fi

should_skip_case() {
  local workload="$1"
  local workload_size="$2"
  if [[ "${resume_pending}" != "1" ]]; then
    return 1
  fi
  if [[ "${workload}" == "${resume_workload}" && "${workload_size}" == "${resume_size}" ]]; then
    echo "Resuming after ${workload} / ${workload_size}"
    resume_pending=0
    return 0
  fi
  echo "Skipping completed case ${workload} / ${workload_size}"
  return 0
}

purge_run_artifacts() {
  if [[ "${PRUNE_RUNS_AFTER_CASE}" != "1" ]]; then
    return 0
  fi
  echo "Pruning bulky run artifacts under ${SCRIPT_DIR}/runs/"
  rm -rf \
    "${SCRIPT_DIR}/runs/gem5" \
    "${SCRIPT_DIR}/runs/spike" \
    "${SCRIPT_DIR}/runs/qemu" \
    "${SCRIPT_DIR}/runs/tt_wormhole"
  mkdir -p "${SCRIPT_DIR}/runs"
}

run_cross_target() {
  local workload="$1"
  local workload_size="$2"
  echo
  echo "=== Cross-target: ${workload} / ${workload_size} ==="
  "${PYTHON_BIN}" "${SCRIPT_DIR}/device_handler/orchestrator.py" \
    "${COMMON_ARGS[@]}" \
    --workload "${workload}" \
    --workload-size "${workload_size}"
  purge_run_artifacts
}

run_tt_only() {
  local workload="$1"
  local workload_size="$2"
  echo
  echo "=== TT-only: ${workload} / ${workload_size} ==="
  "${PYTHON_BIN}" "${SCRIPT_DIR}/device_handler/orchestrator.py" \
    --target tenstorrent \
    --time-us "${TIME_US}" \
    --workload "${workload}" \
    --workload-size "${workload_size}"
  purge_run_artifacts
}

tile_workloads=(
  tt_eltwise_sfpu
  tt_eltwise_binary
  tt_custom_sfpi_add
  tt_custom_sfpi_smoothstep
)

tile_sizes=(
  tt_32tile
  tt_64tile
  tt_128tile
)

for workload in "${tile_workloads[@]}"; do
  for size in "${tile_sizes[@]}"; do
    if should_skip_case "${workload}" "${size}"; then
      continue
    fi
    run_cross_target "${workload}" "${size}"
  done
done

matmul_workloads=(
  tt_matmul_single
  tt_matmul_multi
)

matmul_sizes=(
  tt_m320_n320_k320
  tt_m640_n640_k640
  tt_m960_n960_k960
  tt_m1280_n1280_k1280
)

for workload in "${matmul_workloads[@]}"; do
  for size in "${matmul_sizes[@]}"; do
    if should_skip_case "${workload}" "${size}"; then
      continue
    fi
    run_cross_target "${workload}" "${size}"
  done
done

# tt_sfpu_chain does not currently have a simulator mapping in the orchestrator.
run_tt_only tt_sfpu_chain tt_1tile

echo
echo "All cross-target sweeps finished."
