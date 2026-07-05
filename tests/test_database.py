import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def db():
    from app.database.db import Database
    d = Database()
    d.db_path = Path(tempfile.mktemp(suffix=".db"))
    d._init_schema()
    yield d
    if d.db_path.exists():
        d.db_path.unlink()


def test_init_schema(db):
    tables = db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    names = {t["name"] for t in tables}
    assert "scan_history" in names
    assert "signals" in names
    assert "errors" in names


def test_record_scan(db):
    scan_id = db.record_scan("live", 100, 10)
    assert scan_id > 0
    latest = db.get_latest_scan()
    assert latest is not None
    assert latest["scan_type"] == "live"
    assert latest["total_stocks"] == 100


def test_record_error(db):
    db.record_error("test_source", "ValueError", "test message")
    rows = db.fetchall("SELECT * FROM errors WHERE source='test_source'")
    assert len(rows) == 1
    assert rows[0]["error_type"] == "ValueError"


def test_get_scan_stats_today(db):
    db.record_scan("live", 100, 10)
    db.record_scan("eod", 200, 20)
    stats = db.get_scan_stats_today()
    assert stats["total_scans"] >= 2
