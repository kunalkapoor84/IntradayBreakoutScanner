import numpy as np
from typing import Dict
from config.logging_setup import setup_logging
from models import StockData

logger = setup_logging("gap_probability")


class GapProbabilityAnalyzer:
    def predict(self, stock: StockData) -> Dict[str, float]:
        r = {"gap_up_probability": 0.0, "gap_down_probability": 0.0, "flat_open_probability": 0.0, "expected_gap_pct": 0.0}
        if not stock.ohlc_daily or len(stock.ohlc_daily) < 20: return r
        c = np.array([float(d.get("close", 0)) for d in stock.ohlc_daily if d.get("close")])
        o = np.array([float(d.get("open", 0)) for d in stock.ohlc_daily if d.get("open")])
        if len(c) < 20 or len(o) < 20: return r
        gaps = (o[1:] - c[:-1]) / c[:-1] * 100
        if len(gaps) > 0:
            r["gap_up_probability"] = float(np.sum(gaps > 0.5) / len(gaps) * 100)
            r["gap_down_probability"] = float(np.sum(gaps < -0.5) / len(gaps) * 100)
            r["flat_open_probability"] = float(np.sum((gaps >= -0.5) & (gaps <= 0.5)) / len(gaps) * 100)
        r["expected_gap_pct"] = float(np.mean(gaps[-10:])) if len(gaps) >= 10 else 0.0
        if stock.futures_data and stock.price > 0:
            fp = stock.futures_data.get("lastPrice", 0)
            prem = (fp - stock.price) / stock.price * 100
            if prem > 0.3: r["gap_up_probability"] = min(100, r["gap_up_probability"] * 1.2)
            elif prem < -0.3: r["gap_down_probability"] = min(100, r["gap_down_probability"] * 1.2)
        return r
