#!/usr/bin/env python3
"""Cron wrapper for live scans - checks market hours before executing."""
import sys
import os
from datetime import time as dt_time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import CONFIG
from config.logging_setup import setup_logging
from data.time_utils import now_ist

logger = setup_logging("cron_scan")

MARKET_OPEN = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)

def is_trading_day():
    return now_ist().weekday() < 5

def is_market_open():
    now = now_ist().time()
    return MARKET_OPEN <= now <= MARKET_CLOSE

def main():
    if not is_trading_day():
        logger.info("Weekend, skipping scan")
        return
    if not is_market_open():
        logger.info("Outside market hours, skipping scan")
        return
    from main import ScannerEngine
    engine = ScannerEngine()
    engine.run()
    logger.info("Cron scan complete")

if __name__ == "__main__":
    main()
