#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${1:-/opt/scanner}"
BRANCH="${2:-main}"

echo "=== Deploying Scanner ==="

if [ ! -d "$INSTALL_DIR" ]; then
    echo "Error: $INSTALL_DIR does not exist. Run setup.sh first."
    exit 1
fi

cd "$INSTALL_DIR"

git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

source venv/bin/activate
pip install --quiet --upgrade pip setuptools wheel
pip install --quiet -r requirements.txt

mkdir -p logs reports charts output/reports output/charts data

systemctl restart scanner
systemctl status scanner --no-pager

echo "=== Deploy complete ==="
