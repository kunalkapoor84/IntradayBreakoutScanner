#!/usr/bin/env python3
"""End-of-day comprehensive scan."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.logging_setup import setup_logging
from app.database.db import Database

logger = setup_logging("eod_scan")

def main():
    logger.info("End-of-day scan starting")
    from main import ScannerEngine
    engine = ScannerEngine()
    output = engine.run()
    if output:
        db = Database()
        scan_id = db.record_scan("eod", output.total_stocks_analyzed,
                                  output.stocks_shortlisted)
        if output.top_stocks:
            db.record_signals(scan_id, output.top_stocks)
        from app.notifications.multi_channel import MultiChannelNotifier
        notifier = MultiChannelNotifier()
        notifier.send_scan_report(output)
        html_path = None
        try:
            from reporting.html_report import HTMLReportGenerator
            html_path = HTMLReportGenerator().generate(output)
        except Exception as e:
            logger.error("HTML report failed: %s", e)
        if html_path and notifier.telegram_enabled:
            notifier._send_telegram_file(html_path)
    logger.info("End-of-day scan complete")

if __name__ == "__main__":
    main()
