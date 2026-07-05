import numpy as np
from typing import Dict, Tuple
from config.settings import CONFIG
from config.logging_setup import setup_logging
from models import StockData

logger = setup_logging("liquidity_filter")


class LiquidityFilter:
    def __init__(self):
        self.min_price = CONFIG.scanner.min_price
        self.min_turnover = CONFIG.scanner.min_avg_turnover_crore
        self.min_volume = CONFIG.scanner.min_avg_volume_lakhs

    def check(self, stock: StockData) -> Tuple[bool, Dict[str, bool]]:
        checks = {
            "price_above_min": stock.price >= self.min_price if stock.price > 0 else False,
            "turnover_above_min": stock.avg_turnover_crore >= self.min_turnover,
            "volume_above_min": stock.avg_volume_lakhs >= self.min_volume,
            "delivery_above_min": stock.delivery_pct >= CONFIG.scanner.min_delivery_pct,
            "bid_ask_spread_ok": self._check_spread(stock),
        }
        passed = all(checks.values())
        return passed, checks

    def _check_spread(self, stock: StockData) -> bool:
        try:
            recent = stock.ohlc_daily[-5:]
            spreads = [abs(d.get("close", 0) - d.get("open", 0)) / max(d.get("open", 1), 1) * 100 for d in recent]
            return float(np.mean(spreads)) < 2.0 if spreads else True
        except:
            return True
