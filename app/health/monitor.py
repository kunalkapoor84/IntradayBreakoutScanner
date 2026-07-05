import os
import time
import platform
from datetime import datetime
from typing import Dict, Any

from config.settings import CONFIG
from config.logging_setup import setup_logging
from app.database.db import Database
from app.scheduler.enhanced_scheduler import MarketCalendar

logger = setup_logging("health")


class HealthMonitor:
    def __init__(self):
        self.db = Database()
        self._start_time = time.time()

    def get_status(self) -> Dict[str, Any]:
        try:
            latest = self.db.get_latest_scan()
            stats = self.db.get_scan_stats_today()
        except Exception as e:
            latest = None
            stats = {"total_scans": 0, "total_signals": 0}
        status = {
            "scanner": self._get_scanner_status(),
            "system": self._get_system_info(),
            "database": self._get_db_status(),
            "market": self._get_market_info(),
            "latest_scan": latest,
            "today": stats,
            "uptime_seconds": time.time() - self._start_time,
        }
        return status

    def _get_scanner_status(self) -> Dict[str, Any]:
        return {
            "status": "running",
            "started_at": datetime.fromtimestamp(self._start_time).strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0.0",
        }

    def _get_system_info(self) -> Dict[str, Any]:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            return {
                "platform": platform.platform(),
                "cpu_percent": cpu,
                "memory_percent": mem,
                "disk_percent": disk,
                "python_version": platform.python_version(),
            }
        except ImportError:
            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_percent": "N/A (install psutil)",
                "memory_percent": "N/A (install psutil)",
                "disk_percent": "N/A (install psutil)",
            }

    def _get_db_status(self) -> Dict[str, Any]:
        db_path = CONFIG.db_path
        exists = os.path.exists(db_path)
        size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2) if exists else 0
        return {
            "path": db_path,
            "exists": exists,
            "size_mb": size_mb,
            "status": "ok" if exists else "missing",
        }

    def _get_market_info(self) -> Dict[str, Any]:
        now = datetime.now()
        return {
            "is_trading_day": MarketCalendar.is_trading_day(now),
            "is_market_open": MarketCalendar.is_market_open(now),
            "timezone": CONFIG.timezone,
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        }


monitor = HealthMonitor()
