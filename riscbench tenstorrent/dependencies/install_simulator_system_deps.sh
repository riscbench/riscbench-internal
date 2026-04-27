#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer currently supports Linux only."
  exit 2
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "This installer currently supports apt-based systems only."
  exit 2
fi

echo "Refreshing sudo credentials for simulator system dependency install..."
sudo -v

# Keep the sudo ticket warm while this script runs so apt does not keep prompting.
while true; do
  sudo -n true
  sleep 60
  kill -0 "$$" || exit
done 2>/dev/null &
SUDO_KEEPALIVE_PID=$!
trap 'kill "${SUDO_KEEPALIVE_PID}" >/dev/null 2>&1 || true' EXIT

PACKAGES=(
  qemu-user
  gcc-riscv64-linux-gnu
  gcc-riscv64-unknown-elf
  git
  build-essential
  device-tree-compiler
  libboost-regex-dev
  libboost-system-dev
  libboost-filesystem-dev
  libexpat1-dev
  zlib1g
  zlib1g-dev
  scons
  m4
  libprotobuf-dev
  protobuf-compiler
  libprotoc-dev
  libgoogle-perftools-dev
  python3-dev
  pkg-config
  libboost-all-dev
)

echo "Installing shared simulator prerequisites with one sudo session..."
sudo apt-get update
sudo apt-get install -y "${PACKAGES[@]}"

cat <<'EOF'

System dependency bootstrap complete.

What this installed:
- QEMU user-mode runtime and RISC-V cross compiler
- Spike and pk build prerequisites
- gem5 build prerequisites

What this did not do:
- build spike/pk
- clone or build gem5
- install any Tenstorrent SDK/toolchain

Next step:
- run the orchestrator normally; it can now build local simulator toolchains with fewer sudo prompts
- or run with --auto-install-simulator-tools to let the wrapper fetch/build missing simulator backends
EOF
