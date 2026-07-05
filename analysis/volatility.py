import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from config.logging_setup import setup_logging
from models import StockData

logger = setup_logging("volatility_analyzer")


class VolatilityAnalyzer:
    def analyze(self, stock: StockData) -> Dict[str, float]:
        df = pd.DataFrame(stock.ohlc_daily) if stock.ohlc_daily else pd.DataFrame()
        if df.empty or len(df) < 20: return {}
        c, h, l = df["close"].values.astype(float), df["high"].values.astype(float), df["low"].values.astype(float)
        atr = self._atr(h, l, c, 14)
        atr_pct = atr / c[-1] * 100 if c[-1] > 0 else 0
        _, _, bbw = self._bb(c, 20)
        sqz = bbw < 15.0
        hv = self._hv(c, 20)
        em = atr / c[-1] * 100 if c[-1] > 0 else 0
        return {"atr": float(atr), "atr_pct": float(atr_pct), "bollinger_band_width": float(bbw),
                "bollinger_band_squeeze": float(sqz), "historical_volatility": float(hv),
                "implied_volatility": float(stock.iv), "expected_move_pct": float(em)}

    def _atr(self, h, l, c, p=14):
        if len(c) < p + 1:
            return 0.0
        tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        atr = np.zeros(len(tr))
        atr[p - 1] = np.mean(tr[:p])
        for i in range(p, len(tr)):
            atr[i] = (atr[i - 1] * (p - 1) + tr[i]) / p
        return float(atr[-1])

    def _bb(self, c, p=20):
        if len(c) < p: return 0, 0, 0
        s = np.mean(c[-p:]); std = np.std(c[-p:])
        return s+2*std, s-2*std, 4*std/s*100 if s > 0 else 0

    def _hv(self, c, p=20):
        if len(c) < p+1: return 0.0
        return float(np.std(np.diff(np.log(c))[-p:]) * np.sqrt(252) * 100)
