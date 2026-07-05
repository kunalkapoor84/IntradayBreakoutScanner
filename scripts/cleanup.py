#!/usr/bin/env python3
"""Database and log cleanup."""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_setup import setup_logging
from app.database.db import Database

logger = setup_logging("cleanup")

RETENTION_DAYS = 30

def clean_logs():
    log_dir = Path("logs")
    if not log_dir.exists():
        return
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for f in log_dir.iterdir():
        if f.is_file() and f.suffix in (".log", ".log.1", ".log.2"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                logger.info("Removed old log: %s", f.name)

def main():
    logger.info("Cleanup starting (retention: %d days)", RETENTION_DAYS)
    try:
        db = Database()
        db.cleanup_old_records(RETENTION_DAYS)
    except Exception as e:
        logger.error("DB cleanup failed: %s", e)
    try:
        clean_logs()
    except Exception as e:
        logger.error("Log cleanup failed: %s", e)
    logger.info("Cleanup complete")

if __name__ == "__main__":
    main()
