import time, threading
from datetime import datetime, time as dt_time
from typing import Optional
import schedule
from config.logging_setup import setup_logging
from data.time_utils import now_ist

logger = setup_logging("scheduler")


class ScannerScheduler:
    def __init__(self):
        self._engine = None; self.running = False; self._thread = None

    def _get_engine(self):
        if self._engine is None:
            from main import ScannerEngine
            self._engine = ScannerEngine()
        return self._engine

    def start(self):
        self.running = True
        for d in ["monday","tuesday","wednesday","thursday","friday"]:
            getattr(schedule.every(), d).at("15:30").do(self.run_scanner)
        schedule.every(5).minutes.do(self.live_scan)
        self._thread = threading.Thread(target=self._run, daemon=True); self._thread.start()
        logger.info("Scheduler started")

    def stop(self): self.running = False

    def _run(self):
        while self.running: schedule.run_pending(); time.sleep(1)

    def run_scanner(self):
        if now_ist().weekday() >= 5: return
        try:
            o = self._get_engine().run(); logger.info(f"Scan done: {o.stocks_shortlisted} shortlisted")
        except Exception as e: logger.error(f"Scan failed: {e}")

    def live_scan(self):
        now = now_ist()
        if now.weekday() >= 5: return
        if dt_time(9,15) <= now.time() <= dt_time(15,30):
            try: self._get_engine().run()
            except Exception as e: logger.error(f"Live scan: {e}")
