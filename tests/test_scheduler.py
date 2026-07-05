import pytest
from datetime import datetime, time as dt_time
from app.scheduler.enhanced_scheduler import MarketCalendar


def test_is_trading_day_weekend():
    sat = datetime(2025, 1, 4)
    sun = datetime(2025, 1, 5)
    assert MarketCalendar.is_trading_day(sat) is False
    assert MarketCalendar.is_trading_day(sun) is False


def test_is_trading_day_weekday():
    mon = datetime(2025, 1, 6)
    assert MarketCalendar.is_trading_day(mon) is True


def test_is_market_open():
    from unittest.mock import patch
    with patch("app.scheduler.enhanced_scheduler.MarketCalendar.is_trading_day", return_value=True):
        with patch("app.scheduler.enhanced_scheduler.CONFIG.market_open", "09:15"):
            with patch("app.scheduler.enhanced_scheduler.CONFIG.market_close", "15:30"):
                dt = datetime(2025, 1, 6, 12, 0)
                assert MarketCalendar.is_market_open(dt) is True
                dt_pre = datetime(2025, 1, 6, 8, 0)
                assert MarketCalendar.is_market_open(dt_pre) is False
                dt_post = datetime(2025, 1, 6, 16, 0)
                assert MarketCalendar.is_market_open(dt_post) is False


def test_is_pre_market():
    from unittest.mock import patch
    with patch("app.scheduler.enhanced_scheduler.MarketCalendar.is_trading_day", return_value=True):
        with patch("app.scheduler.enhanced_scheduler.CONFIG.market_open", "09:15"):
            dt = datetime(2025, 1, 6, 8, 30)
            assert MarketCalendar.is_pre_market(dt) is True
            dt = datetime(2025, 1, 6, 10, 0)
            assert MarketCalendar.is_pre_market(dt) is False


def test_is_post_market():
    from unittest.mock import patch
    with patch("app.scheduler.enhanced_scheduler.MarketCalendar.is_trading_day", return_value=True):
        with patch("app.scheduler.enhanced_scheduler.CONFIG.market_close", "15:30"):
            dt = datetime(2025, 1, 6, 16, 0)
            assert MarketCalendar.is_post_market(dt) is True
            dt = datetime(2025, 1, 6, 12, 0)
            assert MarketCalendar.is_post_market(dt) is False
