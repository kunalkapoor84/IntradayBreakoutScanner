from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd
from config.settings import CONFIG
from config.logging_setup import setup_logging
from data.dhan_client import DhanClient
from data.nse_fo_stocks import NSE_FO_STOCKS, SECTOR_MAP
from models import StockData

logger = setup_logging("data_collector")


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

    def _date_range(self, days_back: int) -> tuple:
        end = datetime.now()
        start = end - timedelta(days=days_back)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def collect_symbol_data(self, symbol: str) -> Optional[StockData]:
        daily_from, daily_to = self._date_range(self.lookback_daily)
        intra_from, intra_to = self._date_range(self.lookback_intraday)
        daily_data = []
        intraday_data = []
        try:
            daily_data = self.client.get_historical_daily(symbol, from_date=daily_from, to_date=daily_to)
        except Exception as e:
            logger.warning(f"Failed to get daily data for {symbol}: {e}")
        daily_data = strip_non_trading_days(daily_data)
        try:
            intraday_data = self.client.get_historical_intraday(symbol, from_date=intra_from, to_date=intra_to)
        except Exception as e:
            logger.warning(f"Failed to get intraday data for {symbol}: {e}")
        if not daily_data:
            return None
        sector = SECTOR_MAP.get(symbol, "Unknown")
        price = daily_data[-1].get("close", 0) if daily_data else 0
        delivery_pct = self._get_delivery_pct(daily_data)
        vwap = self._calc_vwap(daily_data)
        return StockData(
            symbol=symbol, sector=sector, price=price,
            avg_turnover_crore=self._calc_avg_turnover(daily_data),
            avg_volume_lakhs=self._calc_avg_volume(daily_data),
            delivery_pct=delivery_pct, ohlc_daily=daily_data, ohlc_5min=intraday_data,
            vwap=vwap,
        )

    def collect_all_stocks(self) -> Dict[str, StockData]:
        results = {}
        for i, symbol in enumerate(NSE_FO_STOCKS):
            stock = self.collect_symbol_data(symbol)
            if stock:
                results[symbol] = stock
                logger.info(f"[{i+1}/{len(NSE_FO_STOCKS)}] {symbol} - OK")
        return results

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


