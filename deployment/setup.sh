#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${1:-https://github.com/yourusername/intraday-breakout-scanner.git}"
INSTALL_DIR="${2:-/opt/scanner}"

echo "=== Intraday Breakout Scanner - Automated Setup ==="
echo "Target directory: $INSTALL_DIR"

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (use sudo)"
    exit 1
fi

apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl wget sqlite3 nginx fail2ban certbot python3-certbot-nginx

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [ ! -d "$INSTALL_DIR/.git" ]; then
    git clone "$REPO_URL" .
else
    git pull
fi

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

cp .env.example .env
echo "=== IMPORTANT: Edit .env with your API keys ==="
echo "nano $INSTALL_DIR/.env"

mkdir -p logs reports charts output/reports output/charts data

chown -R ubuntu:ubuntu "$INSTALL_DIR" 2>/dev/null || chown -R 1000:1000 "$INSTALL_DIR" 2>/dev/null || true

cp deployment/scanner.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable scanner
systemctl start scanner

echo "=== Setup Complete ==="
echo "Edit configuration: nano $INSTALL_DIR/.env"
echo "Start scanner: sudo systemctl start scanner"
echo "Check status: sudo systemctl status scanner"
echo "View logs: tail -f $INSTALL_DIR/logs/scanner.log"
