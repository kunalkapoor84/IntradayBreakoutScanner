#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${1:-/opt/scanner}"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  [PASS] $desc"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $desc"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Scanner Health Check ==="
echo "Time: $(date)"
echo ""

echo "--- Process Status ---"
check "Scanner systemd service" "systemctl is-active --quiet scanner"
check "Scanner process running" "pgrep -f 'python.*main.py' || pgrep -f 'uvicorn.*dashboard'" -- allows either

echo ""
echo "--- Database ---"
check "Database file exists" "[ -f '$INSTALL_DIR/data/scanner.db' ]"
if [ -f "$INSTALL_DIR/data/scanner.db" ]; then
    DB_SIZE=$(du -h "$INSTALL_DIR/data/scanner.db" | cut -f1)
    echo "  Database size: $DB_SIZE"
fi

echo ""
echo "--- Filesystem ---"
check "Log directory exists" "[ -d '$INSTALL_DIR/logs' ]"
check "Reports directory exists" "[ -d '$INSTALL_DIR/reports' ]"
check "Charts directory exists" "[ -d '$INSTALL_DIR/charts' ]"
check "Config file exists" "[ -f '$INSTALL_DIR/.env' ]"

echo ""
echo "--- System Resources ---"
echo "  CPU: $(top -bn1 | grep 'Cpu(s)' | awk '{print $2}')%"
echo "  Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "  Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"

echo ""
echo "--- API Check ---"
if command -v curl &>/dev/null; then
    check "Health endpoint" "curl -sf http://localhost:8000/health > /dev/null"
    check "Status endpoint" "curl -sf http://localhost:8000/status > /dev/null"
fi

echo ""
echo "--- Last Scan ---"
if [ -f "$INSTALL_DIR/data/scanner.db" ]; then
    sqlite3 "$INSTALL_DIR/data/scanner.db" "SELECT scan_time, scan_type, total_stocks, shortlisted, status FROM scan_history ORDER BY id DESC LIMIT 1;" 2>/dev/null || echo "  No scan records found"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
