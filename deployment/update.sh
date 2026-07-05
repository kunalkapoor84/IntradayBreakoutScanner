#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${1:-/opt/scanner}"

echo "=== Updating Scanner ==="

cd "$INSTALL_DIR"

git pull

source venv/bin/activate
pip install --quiet -r requirements.txt

systemctl restart scanner

echo "=== Update complete ==="
