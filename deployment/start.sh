#!/usr/bin/env bash
set -euo pipefail

if systemctl is-active --quiet scanner; then
    echo "Scanner is already running"
else
    systemctl start scanner
    echo "Scanner started"
fi
