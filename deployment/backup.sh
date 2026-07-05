#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${1:-/opt/scanner}"
BACKUP_DIR="${2:-/opt/scanner-backups}"
RETENTION_DAYS="${3:-30}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"

echo "=== Starting backup to $BACKUP_PATH ==="

mkdir -p "$BACKUP_PATH"

if [ -f "$INSTALL_DIR/data/scanner.db" ]; then
    cp "$INSTALL_DIR/data/scanner.db" "$BACKUP_PATH/"
    echo "Database backed up"
fi

if [ -d "$INSTALL_DIR/reports" ] && [ "$(ls -A $INSTALL_DIR/reports 2>/dev/null)" ]; then
    cp -r "$INSTALL_DIR/reports" "$BACKUP_PATH/"
    echo "Reports backed up"
fi

if [ -d "$INSTALL_DIR/charts" ] && [ "$(ls -A $INSTALL_DIR/charts 2>/dev/null)" ]; then
    cp -r "$INSTALL_DIR/charts" "$BACKUP_PATH/"
    echo "Charts backed up"
fi

if [ -d "$INSTALL_DIR/logs" ] && [ "$(ls -A $INSTALL_DIR/logs 2>/dev/null)" ]; then
    cp -r "$INSTALL_DIR/logs" "$BACKUP_PATH/"
    echo "Logs backed up"
fi

cp "$INSTALL_DIR/.env" "$BACKUP_PATH/" 2>/dev/null || true

tar -czf "$BACKUP_PATH.tar.gz" -C "$BACKUP_DIR" "backup_$TIMESTAMP"
rm -rf "$BACKUP_PATH"

find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +"$RETENTION_DAYS" -delete

echo "=== Backup complete: $BACKUP_PATH.tar.gz ==="
echo "Old backups cleaned (retention: $RETENTION_DAYS days)"
