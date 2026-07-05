import numpy as np
from typing import Dict, List, Optional
from config.logging_setup import setup_logging
from models import StockData

logger = setup_logging("relative_strength")


class RelativeStrengthAnalyzer:
    def __init__(self, nifty_data: Optional[List[Dict]] = None, sector_data: Optional[Dict[str, List[Dict]]] = None):
        self.nifty_data = nifty_data or []
        self.sector_data = sector_data or {}

    def analyze(self, stock: StockData) -> Dict[str, float]:
        r = {"rs_5day": 0.0, "rs_20day": 0.0, "momentum_rank": 0.0, "sector_leader_score": 0.0, "nifty_relative_strength": 0.0}
        if not stock.ohlc_daily or len(stock.ohlc_daily) < 20: return r
        sc = np.array([float(d.get("close", 0)) for d in stock.ohlc_daily if d.get("close")])
        if len(sc) < 20: return r
        sp5 = (sc[-1] - sc[-6]) / sc[-6] * 100 if len(sc) >= 6 else 0
        sp20 = (sc[-1] - sc[-21]) / sc[-21] * 100 if len(sc) >= 21 else 0
        nc = np.array([float(d.get("close", 0)) for d in self.nifty_data if d.get("close")]) if self.nifty_data else np.array([])
        np5 = (nc[-1] - nc[-6]) / nc[-6] * 100 if len(nc) >= 6 else 0
        np20 = (nc[-1] - nc[-21]) / nc[-21] * 100 if len(nc) >= 21 else 0
        r["rs_5day"] = float(sp5 - np5)
        r["rs_20day"] = float(sp20 - np20)
        r["nifty_relative_strength"] = float(sp20 - np20)
        rs_ratio = (1 + sp20/100) / (1 + np20/100) if (1 + np20/100) > 0 else 1.0
        r["momentum_rank"] = float(rs_ratio * 100)
        return r
