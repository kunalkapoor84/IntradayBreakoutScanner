import time
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
from config.settings import CONFIG
from config.logging_setup import setup_logging
from data.dhan_client import DhanClient
from data.nse_fo_stocks import NSE_FO_STOCKS, SECTOR_MAP
from data.time_utils import now_ist, IST
from models import StockData

logger = setup_logging("data_collector")


def _is_market_open_now() -> bool:
    now = now_ist()
    if now.weekday() >= 5:
        return False
    open_time = dt_time.fromisoformat(CONFIG.market_open)
    close_time = dt_time.fromisoformat(CONFIG.market_close)
    return open_time <= now.time() <= close_time


def strip_non_trading_days(data: List[Dict]) -> List[Dict]:
    if not data:
        return data
    data = data.copy()
    cut = len(data)
    for i in range(len(data) - 1, -1, -1):
        d = data[i]
        vol = d.get("volume", 0) or 0
        flat = d.get("high") == d.get("low") and d.get("open") == d.get("close")
        if vol == 0 or flat:
            cut = i
        else:
            break
    if cut > 0:
        removed = len(data) - cut
        data = data[:cut]
        if removed > 0:
            logger.info(f"Stripped {removed} non-trading bar(s) from end")
    return data


class DataCollector:
    def __init__(self):
        self.client = DhanClient()
        self.lookback_daily = CONFIG.scanner.lookback_daily_days
        self.lookback_intraday = CONFIG.scanner.lookback_intraday_days
        self._quote_cache: Dict[str, float] = {}
        self._oi_cache: Dict[str, int] = {}
        self._quote_cache_time: float = 0.0

    def _prefetch_quotes(self):
        logger.info("Prefetching live quotes for all symbols...")
        try:
            raw = self.client.get_batch_quote(NSE_FO_STOCKS)
            self._quote_cache = {sym: v["price"] for sym, v in raw.items() if v["price"] > 0}
            self._oi_cache = {sym: v["oi"] for sym, v in raw.items()}
            self._quote_cache_time = time.time()
            logger.info("Quotes fetched for %d symbols", len(self._quote_cache))
        except Exception as e:
            logger.debug("Batch quote fetch failed: %s", e)
            self._quote_cache = {}
            self._oi_cache = {}
            self._quote_cache_time = 0.0

    def _refresh_quotes_if_stale(self, max_age: float = 15.0):
        if self._quote_cache_time and time.time() - self._quote_cache_time < max_age:
            return
        logger.debug("Quote cache stale, refreshing...")
        try:
            raw = self.client.get_batch_quote(NSE_FO_STOCKS)
            self._quote_cache = {sym: v["price"] for sym, v in raw.items() if v["price"] > 0}
            self._oi_cache = {sym: v["oi"] for sym, v in raw.items()}
            self._quote_cache_time = time.time()
        except Exception as e:
            logger.debug("Quote refresh failed: %s", e)

    @staticmethod
    def _ts_to_date_str(ts) -> str:
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                ts = ts / 1000
            return datetime.fromtimestamp(ts, tz=IST).strftime("%Y-%m-%d")
        return str(ts)[:10] if ts else ""

    def _date_range(self, days_back: int) -> tuple:
        end = now_ist()
        start = end - timedelta(days=days_back)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def _throttle(self):
        time.sleep(0.15)

    def collect_symbol_data(self, symbol: str) -> Optional[StockData]:
        daily_from, daily_to = self._date_range(self.lookback_daily)
        intra_from, intra_to = self._date_range(self.lookback_intraday)
        daily_data = []
        intraday_data = []
        try:
            daily_data = self.client.get_historical_daily(symbol, from_date=daily_from, to_date=daily_to)
        except Exception as e:
            logger.warning(f"Failed to get daily data for {symbol}: {e}")
        self._throttle()
        daily_data = strip_non_trading_days(daily_data)
        try:
            intraday_data = self.client.get_historical_intraday(symbol, from_date=intra_from, to_date=intra_to)
        except Exception as e:
            logger.warning(f"Failed to get intraday data for {symbol}: {e}")
        self._throttle()
        if not daily_data:
            return None
        sector = SECTOR_MAP.get(symbol, "Unknown")
        price = daily_data[-1].get("close", 0) if daily_data else 0
        live_price = self._get_live_price(symbol)
        if live_price > 0:
            price = live_price
            self._update_intraday_with_live(intraday_data, live_price)
        today_bar = self._build_today_bar(intraday_data, live_price)
        if today_bar:
            has_today_in_daily = bool(daily_data and self._ts_to_date_str(daily_data[-1].get("timestamp")) == now_ist().strftime("%Y-%m-%d"))
            if live_price <= 0 and not has_today_in_daily:
                price = today_bar["close"]
            daily_data.append(today_bar)
        delivery_pct = self._get_delivery_pct(daily_data)
        vwap = self._calc_vwap(daily_data)
        deriv_data = self._collect_derivatives(symbol)
        self._throttle()
        oi = deriv_data["open_interest"] or self._oi_cache.get(symbol, 0)
        return StockData(
            symbol=symbol, sector=sector, price=price,
            avg_turnover_crore=self._calc_avg_turnover(daily_data),
            avg_volume_lakhs=self._calc_avg_volume(daily_data),
            delivery_pct=delivery_pct, ohlc_daily=daily_data, ohlc_5min=intraday_data,
            vwap=vwap,
            open_interest=oi,
            change_oi=deriv_data["change_oi"],
            option_chain=deriv_data["option_chain"],
            pcr=deriv_data["pcr"],
            iv=deriv_data["iv"],
        )

    def collect_all_stocks(self) -> Dict[str, StockData]:
        self._prefetch_quotes()
        results = {}
        for i, symbol in enumerate(NSE_FO_STOCKS):
            stock = self.collect_symbol_data(symbol)
            if stock:
                results[symbol] = stock
                logger.info(f"[{i+1}/{len(NSE_FO_STOCKS)}] {symbol} - OK")
            if (i + 1) % 20 == 0:
                self._refresh_quotes_if_stale(max_age=15.0)
        return results

    def _get_live_price(self, symbol: str) -> float:
        if symbol in self._quote_cache:
            return self._quote_cache[symbol]
        try:
            quote = self.client.get_quote(symbol)
            if isinstance(quote, dict):
                for key in ("lastPrice", "ltp", "last_price", "close", "CMP"):
                    val = quote.get(key)
                    if val and float(val) > 0:
                        return float(val)
        except Exception as e:
            logger.debug(f"Failed to get live quote for {symbol}: {e}")
        return 0.0

    def _update_intraday_with_live(self, intraday_data: List[Dict], live_price: float):
        if not intraday_data or live_price <= 0:
            return
        last = intraday_data[-1]
        last["close"] = live_price
        if live_price > last.get("high", 0):
            last["high"] = live_price
        if live_price < last.get("low", float("inf")):
            last["low"] = live_price

    def _build_today_bar(self, intraday_data: List[Dict], live_price: float) -> Optional[Dict]:
        if not intraday_data:
            return None
        today_str = now_ist().strftime("%Y-%m-%d")
        today_opens, today_highs, today_lows, today_closes, today_volumes = [], [], [], [], []
        has_today_data = False
        for bar in intraday_data:
            ts = bar.get("timestamp")
            if not ts:
                continue
            if isinstance(ts, (int, float)):
                if ts > 1e12:
                    ts = ts / 1000
                bar_date = datetime.fromtimestamp(ts, tz=IST).strftime("%Y-%m-%d")
            else:
                bar_date = str(ts)[:10]
            if bar_date == today_str:
                has_today_data = True
                if bar.get("open"): today_opens.append(bar["open"])
                if bar.get("high"): today_highs.append(bar["high"])
                if bar.get("low"): today_lows.append(bar["low"])
                if bar.get("close"): today_closes.append(bar["close"])
                if bar.get("volume"): today_volumes.append(bar["volume"])
        if not has_today_data or not today_opens:
            return None
        last_close = float(live_price) if live_price > 0 else float(today_closes[-1]) if today_closes else float(today_opens[-1])
        return {
            "timestamp": today_str,
            "open": float(today_opens[0]),
            "high": float(max(today_highs)) if today_highs else last_close,
            "low": float(min(today_lows)) if today_lows else last_close,
            "close": last_close,
            "volume": int(sum(today_volumes)) if today_volumes else 0,
        }

    def _get_delivery_pct(self, daily_data: List[Dict]) -> float:
        try:
            recent = daily_data[-20:]
            pcts = [d.get("deliveryQty", 0) / max(d.get("volume", 1), 1) * 100 for d in recent]
            return float(np.mean(pcts)) if pcts else 0.0
        except:
            return 0.0

    def _calc_vwap(self, daily_data: List[Dict]) -> float:
        try:
            recent = daily_data[-5:]
            pv = sum(((d.get("high", 0) + d.get("low", 0) + d.get("close", 0)) / 3) * d.get("volume", 0) for d in recent)
            v = sum(d.get("volume", 0) for d in recent)
            return pv / v if v else 0.0
        except:
            return 0.0

    def _calc_avg_turnover(self, daily_data: List[Dict]) -> float:
        try:
            recent = daily_data[-20:]
            to = [((d.get("high", 0) + d.get("low", 0) + d.get("close", 0)) / 3) * d.get("volume", 0) for d in recent]
            return float(np.mean(to) / 1e7) if to else 0.0
        except:
            return 0.0

    def _calc_avg_volume(self, daily_data: List[Dict]) -> float:
        try:
            vols = [d.get("volume", 0) for d in daily_data[-20:]]
            return float(np.mean(vols) / 1e5) if vols else 0.0
        except:
            return 0.0

    def _collect_derivatives(self, symbol: str) -> dict:
        ce_cache = self._oi_cache.get(symbol, 0)
        return {
            "option_chain": [],
            "open_interest": ce_cache,
            "change_oi": 0,
            "pcr": 0.0,
            "iv": 0.0,
        }


