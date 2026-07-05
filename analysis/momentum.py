import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from config.logging_setup import setup_logging
from models import StockData

logger = setup_logging("momentum_analyzer")


class MomentumAnalyzer:
    def analyze(self, stock: StockData) -> Dict:
        df = self._to_df(stock.ohlc_daily)
        if df.empty or len(df) < 50:
            return {}
        c, h, l, v = df["close"].values.astype(float), df["high"].values.astype(float), df["low"].values.astype(float), df["volume"].values.astype(float) if "volume" in df.columns else np.ones(len(df))
        o = df["open"].values.astype(float)

        rsi = self._rsi(c, 14)
        adx = self._adx(h, l, c, 14)
        macd_l, _, macd_h = self._macd(c)
        e20 = self._ema(c, 20)
        e50 = self._ema(c, 50)
        vwap = self._vwap(h, l, c, v)
        lc = c[-1]

        return {
            "rsi_bullish": 55 <= rsi <= 75,
            "rsi_bearish": 25 <= rsi <= 45,
            "adx_strong": adx > 25,
            "macd_bullish_cross": len(macd_h) >= 2 and macd_h[-1] > 0 and macd_h[-2] <= 0,
            "macd_bearish_cross": len(macd_h) >= 2 and macd_h[-1] < 0 and macd_h[-2] >= 0,
            "price_above_vwap": lc > vwap,
            "price_below_vwap": lc < vwap,
            "ema20_above_ema50": len(e20) > 0 and len(e50) > 0 and e20[-1] > e50[-1],
            "ema20_below_ema50": len(e20) > 0 and len(e50) > 0 and e20[-1] < e50[-1],
            "strong_closing_momentum": len(c) >= 5 and all(c[-i] > c[-i-1] for i in range(1, 4)),
            "large_bullish_candle": self._big_candle(o, c, "bullish"),
            "large_bearish_candle": self._big_candle(o, c, "bearish"),
            "adx": adx,
        }

    def _to_df(self, data): return pd.DataFrame(data) if data else pd.DataFrame()

    def _rsi(self, c, p=14):
        if len(c) < p + 1:
            return 50.0
        d = np.diff(c)
        g = np.where(d > 0, d, 0)
        ls = np.where(d < 0, -d, 0)
        ag = np.mean(g[:p])
        al = np.mean(ls[:p])
        for i in range(p, len(g)):
            ag = (ag * (p - 1) + g[i]) / p
            al = (al * (p - 1) + ls[i]) / p
        return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)

    def _adx(self, h, l, c, p=14):
        if len(c) < 2 * p + 1:
            return 0.0
        tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
        up = h[1:] - h[:-1]
        down = l[:-1] - l[1:]
        pos_dm = np.where((up > down) & (up > 0), up, 0)
        neg_dm = np.where((down >= up) & (down > 0), down, 0)
        tr_s = np.zeros(len(tr))
        pos_s = np.zeros(len(pos_dm))
        neg_s = np.zeros(len(neg_dm))
        tr_s[p - 1] = np.mean(tr[:p])
        pos_s[p - 1] = np.mean(pos_dm[:p])
        neg_s[p - 1] = np.mean(neg_dm[:p])
        for i in range(p, len(tr)):
            tr_s[i] = (tr_s[i - 1] * (p - 1) + tr[i]) / p
            pos_s[i] = (pos_s[i - 1] * (p - 1) + pos_dm[i]) / p
            neg_s[i] = (neg_s[i - 1] * (p - 1) + neg_dm[i]) / p
        with np.errstate(invalid="ignore", divide="ignore"):
            pdi = np.where(tr_s > 0, 100 * pos_s / tr_s, 0)
            ndi = np.where(tr_s > 0, 100 * neg_s / tr_s, 0)
            dx = np.where((pdi + ndi) > 0, 100 * np.abs(pdi - ndi) / (pdi + ndi), 0)
        adx = np.zeros(len(dx))
        adx[2 * p - 2] = np.mean(dx[p - 1:2 * p - 1])
        for i in range(2 * p - 1, len(dx)):
            adx[i] = (adx[i - 1] * (p - 1) + dx[i]) / p
        return float(adx[-1])

    def _macd(self, c):
        e12 = self._ema(c, 12)
        e26 = self._ema(c, 26)
        if len(e12) == 0 or len(e26) == 0:
            return np.array([]), np.array([]), np.array([])
        m = e12 - e26
        s = self._ema(m, 9)
        h = m - s if len(s) > 0 else np.zeros_like(m)
        return m, s, h

    def _ema(self, d, p):
        if len(d) < p: return np.array([])
        m = 2 / (p + 1); e = np.full_like(d, np.nan); e[p-1] = np.mean(d[:p])
        for i in range(p, len(d)): e[i] = (d[i] - e[i-1]) * m + e[i-1]
        return e

    def _vwap(self, h, l, c, v):
        tp = (h + l + c) / 3
        return np.sum(tp * v) / np.sum(v) if np.sum(v) > 0 else 0

    def _big_candle(self, o, c, direction):
        if len(o) < 2: return False
        body = abs(c[-1] - o[-1]); avg = np.mean(abs(c[-21:-1] - o[-21:-1])) if len(o) > 21 else body
        if avg == 0: return False
        is_bull = c[-1] > o[-1]
        return (direction == "bullish" and is_bull and body > 2 * avg) or (direction == "bearish" and not is_bull and body > 2 * avg)
