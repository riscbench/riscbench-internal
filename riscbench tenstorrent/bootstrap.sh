#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
PYTHON_BIN="${PYTHON:-python3}"

echo "Creating virtual environment at ${VENV_DIR}"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

python -m pip install --disable-pip-version-check -r "${SCRIPT_DIR}/dependencies/python-requirements.txt"

cat > "${VENV_DIR}/bin/riscbench" <<EOF
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/python" "${SCRIPT_DIR}/device_handler/orchestrator.py" "\$@"
EOF
chmod +x "${VENV_DIR}/bin/riscbench"

cat > "${VENV_DIR}/bin/riscbench-single" <<EOF
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/python" "${SCRIPT_DIR}/device_handler/backend_runner.py" "\$@"
EOF
chmod +x "${VENV_DIR}/bin/riscbench-single"

cat <<EOF

Bootstrap complete.

Quick start:
  1. Review ${SCRIPT_DIR}/dependencies/SYSTEM_DEPENDENCIES.md
  2. Optionally preinstall simulator system packages once:
       bash ${SCRIPT_DIR}/dependencies/install_simulator_system_deps.sh
  3. Copy ${SCRIPT_DIR}/configs/orchestration.example.json to your own config
  4. Run a dependency check:
       ${SCRIPT_DIR}/run.sh ${SCRIPT_DIR}/configs/orchestration.example.json --check-only
  5. Run a dry-run:
       ${SCRIPT_DIR}/run.sh ${SCRIPT_DIR}/configs/orchestration.example.json --dry-run --skip-missing-tools
  6. Run the full orchestration when your backend paths are ready.
EOF
