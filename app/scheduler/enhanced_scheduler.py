import time
import signal
import sys
import threading
from datetime import datetime, time as dt_time, timedelta
from typing import Optional, Callable

from config.settings import CONFIG
from config.logging_setup import setup_logging
from app.database.db import Database

logger = setup_logging("scheduler")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed, falling back to threading scheduler")


INDIAN_MARKET_HOLIDAYS_2025 = {
    "2025-01-26", "2025-02-26", "2025-03-14", "2025-03-31",
    "2025-04-10", "2025-04-14", "2025-04-18", "2025-05-01",
    "2025-08-15", "2025-08-27", "2025-10-02", "2025-10-22",
    "2025-11-04", "2025-12-25",
}


class MarketCalendar:
    @staticmethod
    def is_trading_day(dt: Optional[datetime] = None) -> bool:
        dt = dt or datetime.now()
        if dt.weekday() >= 5:
            return False
        date_str = dt.strftime("%Y-%m-%d")
        if date_str in INDIAN_MARKET_HOLIDAYS_2025:
            return False
        return True

    @staticmethod
    def is_market_open(dt: Optional[datetime] = None) -> bool:
        dt = dt or datetime.now()
        if not MarketCalendar.is_trading_day(dt):
            return False
        open_time = dt_time.fromisoformat(CONFIG.market_open)
        close_time = dt_time.fromisoformat(CONFIG.market_close)
        return open_time <= dt.time() <= close_time

    @staticmethod
    def next_market_open(dt: Optional[datetime] = None) -> Optional[datetime]:
        dt = dt or datetime.now()
        for _ in range(14):
            dt += timedelta(days=1)
            if MarketCalendar.is_trading_day(dt):
                hour, minute = map(int, CONFIG.market_open.split(":"))
                return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return None

    @staticmethod
    def is_pre_market(dt: Optional[datetime] = None) -> bool:
        dt = dt or datetime.now()
        if not MarketCalendar.is_trading_day(dt):
            return False
        open_time = dt_time.fromisoformat(CONFIG.market_open)
        pre_time = dt_time(8, 30)
        return pre_time <= dt.time() < open_time

    @staticmethod
    def is_post_market(dt: Optional[datetime] = None) -> bool:
        dt = dt or datetime.now()
        if not MarketCalendar.is_trading_day(dt):
            return False
        close_time = dt_time.fromisoformat(CONFIG.market_close)
        return dt.time() > close_time


class ScanLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False

    def acquire(self) -> bool:
        if self._lock.acquire(blocking=False):
            self._running = True
            return True
        return False

    def release(self):
        self._running = False
        self._lock.release()

    @property
    def is_running(self) -> bool:
        return self._running


class EnhancedScheduler:
    def __init__(self, scan_func: Callable):
        self.scan_func = scan_func
        self.running = False
        self._apscheduler = None
        self._thread = None
        self._stop_event = threading.Event()
        self._scan_lock = ScanLock()
        self.db = Database()
        self._shutdown_requested = False

    def start(self):
        self.running = True
        self._shutdown_requested = False
        if APSCHEDULER_AVAILABLE:
            self._start_apscheduler()
        else:
            self._start_threading()
        logger.info("Scheduler started (APScheduler: %s)", APSCHEDULER_AVAILABLE)

    def _start_apscheduler(self):
        self._apscheduler = BackgroundScheduler(daemon=True)
        interval = CONFIG.scan_interval_minutes
        hour, minute = map(int, CONFIG.eod_scan_time.split(":"))
        self._apscheduler.add_job(
            self._safe_scan_wrapper, IntervalTrigger(minutes=interval),
            id="live_scan", name="Live Market Scan",
            misfire_grace_time=60, coalesce=True,
        )
        self._apscheduler.add_job(
            self._eod_scan_wrapper, CronTrigger(hour=hour, minute=minute, day_of_week="mon-fri"),
            id="eod_scan", name="End-of-Day Scan",
            misfire_grace_time=300, coalesce=True,
        )
        self._apscheduler.add_job(
            self._pre_market_wrapper, CronTrigger(hour=8, minute=30, day_of_week="mon-fri"),
            id="pre_market", name="Pre-Market Task",
            misfire_grace_time=300, coalesce=True,
        )
        self._apscheduler.add_job(
            self._cleanup_wrapper, CronTrigger(hour=4, minute=0),
            id="cleanup", name="Database Cleanup",
            misfire_grace_time=3600,
        )
        self._apscheduler.start()

    def _start_threading(self):
        def loop():
            while not self._stop_event.is_set():
                try:
                    now = datetime.now()
                    if MarketCalendar.is_market_open(now):
                        self._safe_scan_wrapper()
                    elif MarketCalendar.is_post_market(now):
                        close_hour, close_min = map(int, CONFIG.market_close.split(":"))
                        eod_hour, eod_min = map(int, CONFIG.eod_scan_time.split(":"))
                        if now.hour == eod_hour and now.minute == eod_min:
                            self._eod_scan_wrapper()
                except Exception as e:
                    logger.error("Scheduler loop error: %s", e)
                self._stop_event.wait(60)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def _safe_scan_wrapper(self):
        if self._shutdown_requested:
            return
        now = datetime.now()
        if not MarketCalendar.is_market_open(now):
            logger.debug("Market closed, skipping live scan")
            return
        if not self._scan_lock.acquire():
            logger.warning("Previous scan still in progress, skipping")
            return
        try:
            logger.info("Starting live scan...")
            start = time.time()
            output = self.scan_func()
            duration = time.time() - start
            if output:
                scan_id = self.db.record_scan(
                    "live", output.total_stocks_analyzed,
                    output.stocks_shortlisted, duration=duration,
                )
                if output.top_stocks:
                    self.db.record_signals(scan_id, output.top_stocks)
                logger.info("Live scan complete: %d stocks, %d shortlisted (%.1fs)",
                            output.total_stocks_analyzed, output.stocks_shortlisted, duration)
        except Exception as e:
            logger.error("Live scan failed: %s", e, exc_info=True)
            self.db.record_scan("live", 0, 0, status="failed", error=str(e))
        finally:
            self._scan_lock.release()

    def _eod_scan_wrapper(self):
        if self._shutdown_requested:
            return
        now = datetime.now()
        if not MarketCalendar.is_trading_day(now):
            logger.info("Not a trading day, skipping EOD scan")
            return
        if not self._scan_lock.acquire():
            logger.warning("Previous scan still in progress, skipping EOD")
            return
        try:
            logger.info("Starting end-of-day scan...")
            start = time.time()
            output = self.scan_func()
            duration = time.time() - start
            if output:
                scan_id = self.db.record_scan(
                    "eod", output.total_stocks_analyzed,
                    output.stocks_shortlisted, duration=duration,
                )
                if output.top_stocks:
                    self.db.record_signals(scan_id, output.top_stocks)
                logger.info("EOD scan complete: %d stocks, %d shortlisted (%.1fs)",
                            output.total_stocks_analyzed, output.stocks_shortlisted, duration)
        except Exception as e:
            logger.error("EOD scan failed: %s", e, exc_info=True)
            self.db.record_scan("eod", 0, 0, status="failed", error=str(e))
        finally:
            self._scan_lock.release()

    def _pre_market_wrapper(self):
        now = datetime.now()
        if not MarketCalendar.is_trading_day(now):
            return
        logger.info("Pre-market tasks starting...")
        self.db.cleanup_old_records()
        logger.info("Pre-market tasks complete")

    def _cleanup_wrapper(self):
        self.db.cleanup_old_records(30)

    def stop(self):
        logger.info("Shutdown requested...")
        self._shutdown_requested = True
        self.running = False
        if self._apscheduler:
            self._apscheduler.shutdown(wait=False)
        if self._thread:
            self._stop_event.set()
            self._thread.join(timeout=10)
        self.db.close()
        logger.info("Scheduler stopped")
