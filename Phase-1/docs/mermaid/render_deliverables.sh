#!/usr/bin/env bash
set -euo pipefail

if ! command -v mmdc >/dev/null 2>&1; then
  echo "mmdc not found. Install Mermaid CLI first:"
  echo "  npm i -g @mermaid-js/mermaid-cli"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${ROOT_DIR}/deliverables"

for mmd in "${SRC_DIR}"/*.mmd; do
  png="${mmd%.mmd}.png"
  echo "Rendering ${mmd##*/} -> ${png##*/}"
  mmdc -i "${mmd}" -o "${png}" -b transparent
done

echo "Done. PNGs are in: ${SRC_DIR}"
