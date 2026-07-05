#!/usr/bin/env python3
"""Pre-market tasks: download symbol data, update cache."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_setup import setup_logging
from app.database.db import Database

logger = setup_logging("pre_market")

def main():
    logger.info("Pre-market tasks starting")
    db = Database()
    db.cleanup_old_records(30)
    try:
        from data.dhan_client import DhanClient
        client = DhanClient()
        client._load_instrument_master()
        logger.info("Instrument master refreshed")
    except Exception as e:
        logger.error("Pre-market data refresh failed: %s", e)
    logger.info("Pre-market tasks complete")

if __name__ == "__main__":
    main()
