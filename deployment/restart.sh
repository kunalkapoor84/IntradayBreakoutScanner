#!/usr/bin/env bash
set -euo pipefail

systemctl restart scanner
echo "Scanner restarted"
systemctl status scanner --no-pager
