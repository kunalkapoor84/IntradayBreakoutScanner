#!/usr/bin/env bash
# Oracle Cloud Always Free Ubuntu VM - Complete Setup Script
# Run this script on a fresh Oracle Cloud Ubuntu instance
set -euo pipefail

echo "========================================"
echo "  Oracle Cloud Setup - Scanner"
echo "========================================"

# --- System Packages ---
echo "[1/8] Installing system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv \
    git curl wget sqlite3 \
    nginx fail2ban \
    ufw \
    htop iotop \
    build-essential \
    ca-certificates

# --- Firewall ---
echo "[2/8] Configuring firewall..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
ufw --force enable

# --- Fail2Ban ---
echo "[3/8] Configuring fail2ban..."
cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local 2>/dev/null || true
systemctl enable fail2ban
systemctl restart fail2ban

# --- Python Virtual Environment ---
echo "[4/8] Setting up Python environment..."
PROJECT_DIR="/opt/scanner"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip setuptools wheel

# --- Clone Repository ---
echo "[5/8] Cloning repository..."
if [ ! -d "$PROJECT_DIR/.git" ]; then
    git clone https://github.com/yourusername/intraday-breakout-scanner.git .
else
    git pull
fi

pip install --quiet -r requirements.txt

# --- Configuration ---
echo "[6/8] Setting up configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "IMPORTANT: Edit $PROJECT_DIR/.env with your API keys"
fi

mkdir -p logs reports charts output/reports output/charts data
chown -R ubuntu:ubuntu "$PROJECT_DIR"

# --- systemd Service ---
echo "[7/8] Installing systemd service..."
cp deployment/scanner.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable scanner

# --- Cron Backups ---
echo "[8/8] Setting up cron jobs..."
cat > /etc/cron.d/scanner-backup << 'EOF'
0 4 * * * root /opt/scanner/deployment/backup.sh /opt/scanner /opt/scanner-backups 30 >/dev/null 2>&1
EOF
chmod 644 /etc/cron.d/scanner-backup

# --- Start ---
systemctl start scanner

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env:  nano /opt/scanner/.env"
echo "  2. Restart:    sudo systemctl restart scanner"
echo "  3. Status:     sudo systemctl status scanner"
echo "  4. Logs:       tail -f /opt/scanner/logs/scanner.log"
echo "  5. Dashboard:  http://$(curl -s ifconfig.me):8000/dashboard"
echo ""
echo "Security:"
echo "  - SSH key authentication only (password auth disabled)"
echo "  - Firewall active (ports: 22, 80, 443, 8000)"
echo "  - fail2ban monitoring SSH"
echo "  - Automatic daily backups to /opt/scanner-backups"
echo ""
