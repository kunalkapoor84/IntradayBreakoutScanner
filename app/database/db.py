import sqlite3
import json
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from config.settings import CONFIG
from config.logging_setup import setup_logging

logger = setup_logging("database")

_schema = Path(__file__).parent / "schema.py"


class Database:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.db_path = Path(CONFIG.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self):
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_schema(self):
        if not _schema.exists():
            logger.warning("Schema file not found at %s", _schema)
            return
        sql = _schema.read_text(encoding="utf-8")
        try:
            conn = self._get_conn()
            conn.executescript(sql)
            conn.commit()
            logger.info("Database schema initialized")
        except Exception as e:
            logger.error("Schema init failed: %s", e)

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._get_conn().execute(sql, params)

    def executemany(self, sql: str, params: List[tuple]) -> sqlite3.Cursor:
        return self._get_conn().executemany(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        row = self._get_conn().execute(sql, params).fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict]:
        return [dict(r) for r in self._get_conn().execute(sql, params).fetchall()]

    def commit(self):
        self._get_conn().commit()

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def record_scan(self, scan_type: str, total: int, shortlisted: int,
                    status: str = "success", duration: float = 0, error: str = "") -> int:
        cursor = self.execute(
            "INSERT INTO scan_history (scan_time, scan_type, total_stocks, shortlisted, status, duration_seconds, error_message) VALUES (datetime('now','+5:30'),?,?,?,?,?,?)",
            (scan_type, total, shortlisted, status, duration, error),
        )
        self.commit()
        return cursor.lastrowid

    def record_signals(self, scan_id: int, top_stocks: List) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for s in top_stocks:
            rows.append((
                scan_id, s.symbol, now, round(s.total_score, 1), round(s.confidence, 1),
                s.direction.value if hasattr(s.direction, "value") else str(s.direction),
                s.entry_price, s.stop_loss, s.target_1, s.target_2, s.cmp,
                round(s.atr, 2), round(s.volume_ratio, 2), round(s.rsi, 1), round(s.adx, 1),
                round(s.pcr, 2), s.oi_change, round(s.iv, 1), s.sector, s.strategy,
                s.pattern_detected, round(s.expected_move_pct, 2), round(s.risk_reward, 2),
                s.position_size, s.catalyst, int(s.bollinger_squeeze), int(s.nr_detected),
                round(s.breakout_proximity, 1), s.chart_path,
            ))
        self.executemany("""
            INSERT INTO signals (scan_id, symbol, scan_time, score, confidence, direction,
            entry_price, stop_loss, target_1, target_2, cmp, atr, volume_ratio, rsi, adx,
            pcr, oi_change, iv, sector, strategy, pattern_detected, expected_move_pct,
            risk_reward, position_size, catalyst, bollinger_squeeze, nr_detected,
            breakout_proximity, chart_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        self.commit()
        return len(rows)

    def record_notification(self, channel: str, ntype: str, message: str,
                            status: str = "sent", error: str = ""):
        self.execute(
            "INSERT INTO notifications (channel, notification_type, message, status, error_message) VALUES (?,?,?,?,?)",
            (channel, ntype, message, status, error),
        )
        self.commit()

    def record_error(self, source: str, error_type: str, message: str, traceback: str = ""):
        self.execute(
            "INSERT INTO errors (source, error_type, message, traceback) VALUES (?,?,?,?)",
            (source, error_type, message, traceback),
        )
        self.commit()

    def get_latest_scan(self) -> Optional[Dict]:
        return self.fetchone("SELECT * FROM scan_history ORDER BY id DESC LIMIT 1")

    def get_recent_signals(self, limit: int = 20) -> List[Dict]:
        return self.fetchall(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
        )

    def get_top_signals_today(self, limit: int = 20) -> List[Dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.fetchall(
            "SELECT * FROM signals WHERE scan_time LIKE ? ORDER BY score DESC LIMIT ?",
            (f"{today}%", limit),
        )

    def get_scan_stats_today(self) -> Dict:
        today = datetime.now().strftime("%Y-%m-%d")
        row = self.fetchone("""
            SELECT COUNT(*) as total_scans, COALESCE(SUM(shortlisted),0) as total_signals
            FROM scan_history WHERE scan_time LIKE ?
        """, (f"{today}%",))
        return row or {"total_scans": 0, "total_signals": 0}

    def cleanup_old_records(self, days: int = 30):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        for table in ["scan_history", "signals", "errors", "notifications"]:
            self.execute(f"DELETE FROM {table} WHERE created_at < ?", (cutoff,))
        self.commit()
        logger.info("Cleaned up records older than %s days", days)
