import numpy as np
import pandas as pd
from typing import List
from config.logging_setup import setup_logging
from models import StockData, PatternType

logger = setup_logging("pattern_detector")


class PatternDetector:
    def detect_all(self, stock: StockData) -> List[PatternType]:
        df = pd.DataFrame(stock.ohlc_daily) if stock.ohlc_daily else pd.DataFrame()
        if df.empty or len(df) < 50: return []
        o, h, l, c = df["open"].values.astype(float), df["high"].values.astype(float), df["low"].values.astype(float), df["close"].values.astype(float)
        v = df["volume"].values.astype(float) if "volume" in df.columns else np.ones_like(c)
        p = []
        if self._nr7(h, l): p.append(PatternType.NR7)
        if self._nr4(h, l): p.append(PatternType.NR4)
        if self._ib(h, l): p.append(PatternType.INSIDE_BAR)
        if self._dib(h, l): p.append(PatternType.DOUBLE_INSIDE_BAR)
        if self._bf(o, h, l, c, v): p.append(PatternType.BULL_FLAG)
        if self._bf2(o, h, l, c, v): p.append(PatternType.BEAR_FLAG)
        if self._at(h, l): p.append(PatternType.ASCENDING_TRIANGLE)
        if self._dt(h, l): p.append(PatternType.DESCENDING_TRIANGLE)
        if self._ch(c): p.append(PatternType.CUP_HANDLE)
        if self._fw(h, l): p.append(PatternType.FALLING_WEDGE)
        if self._rw(h, l): p.append(PatternType.RISING_WEDGE)
        if self._db(h, l, c): p.append(PatternType.DARVAS_BOX)
        if self._vcp(h, l, v): p.append(PatternType.VCP)
        if self._tc(h, l, c): p.append(PatternType.TIGHT_CONSOLIDATION)
        if self._orb(h, l, c): p.append(PatternType.ORB_SETUP)
        if self._hh_hl(h, l): p.append(PatternType.HH_HL)
        if self._lh_ll(h, l): p.append(PatternType.LH_LL)
        if self._be(o, c): p.append(PatternType.BULLISH_ENGULFING)
        if self._be2(o, c): p.append(PatternType.BEARISH_ENGULFING)
        if self._mar(o, h, l, c): p.append(PatternType.MARUBOZU)
        if self._doji_brk(o, h, l, c): p.append(PatternType.DOJI_NEAR_BREAKOUT)
        return p

    def _nr7(self, h, l): return len(h) >= 8 and (h[-8:] - l[-8:])[-1] == min(h[-8:] - l[-8:])
    def _nr4(self, h, l): return len(h) >= 5 and (h[-5:] - l[-5:])[-1] == min(h[-5:] - l[-5:])
    def _ib(self, h, l): return len(h) >= 3 and h[-1] < h[-2] and l[-1] > l[-2]
    def _dib(self, h, l): return len(h) >= 4 and h[-1] < h[-2] and l[-1] > l[-2] and h[-2] < h[-3] and l[-2] > l[-3]
    def _bf(self, o, h, l, c, v):
        if len(c) < 20: return False
        r = c[-10:]; fl = max(h[-5:]) - min(l[-5:]); ar = np.mean(h[-20:-5] - l[-20:-5]) if len(h) >= 20 else fl
        return r[-1] > r[0] and fl < ar * 0.6
    def _bf2(self, o, h, l, c, v):
        if len(c) < 20: return False
        r = c[-10:]; fl = max(h[-5:]) - min(l[-5:]); ar = np.mean(h[-20:-5] - l[-20:-5]) if len(h) >= 20 else fl
        return r[-1] < r[0] and fl < ar * 0.6
    def _at(self, h, l):
        if len(h) < 15: return False
        rh, rl = h[-10:], l[-10:]
        return np.std(rh) < np.std(rl) * 0.3 and all(rl[i] > rl[i-1] for i in range(1, len(rl)))
    def _dt(self, h, l):
        if len(h) < 15: return False
        rh, rl = h[-10:], l[-10:]
        return np.std(rl) < np.std(rh) * 0.3 and all(rh[i] < rh[i-1] for i in range(1, len(rh)))
    def _ch(self, c):
        if len(c) < 40: return False
        seg = c[-40:]; mid = len(seg)//2; d = (max(seg)-min(seg))/max(seg)
        hdl = seg[-5:]; hr = (max(hdl)-min(hdl))/max(seg)
        return 0.15 <= d <= 0.45 and hr < 0.1
    def _fw(self, h, l):
        if len(h) < 15: return False
        x = np.arange(15); ch = np.polyfit(x, h[-15:], 1); cl = np.polyfit(x, l[-15:], 1)
        return ch[0] < 0 and cl[0] < 0 and ch[0] > cl[0]
    def _rw(self, h, l):
        if len(h) < 15: return False
        x = np.arange(15); ch = np.polyfit(x, h[-15:], 1); cl = np.polyfit(x, l[-15:], 1)
        return ch[0] > 0 and cl[0] > 0 and ch[0] < cl[0]
    def _db(self, h, l, c):
        if len(h) < 10: return False
        return (max(h[-10:]) - min(l[-5:])) / min(l[-5:]) < 0.05 and c[-1] > np.mean(c[-10:])
    def _vcp(self, h, l, v):
        if len(h) < 15: return False
        r = h[-15:] - l[-15:]
        return len(r) >= 6 and all(r[i] > r[i+1] for i in range(-5, -1)) and all(v[i] > v[i+1] for i in range(-5, -1)) if len(v) >= 6 else False
    def _tc(self, h, l, c):
        if len(h) < 5: return False
        return (max(h[-5:]) - min(l[-5:])) / c[-1] * 100 < 3.0
    def _orb(self, h, l, c):
        if len(h) < 20: return False
        rr = h[-1] - l[-1]; ar = np.mean(h[-20:-1] - l[-20:-1])
        if ar == 0: return False
        cp = (c[-1] - l[-1]) / rr if rr > 0 else 0.5
        return rr < ar * 0.7 and 0.3 <= cp <= 0.7
    def _hh_hl(self, h, l): return len(h) >= 10 and all(h[-i] > h[-i-1] for i in range(1, 5)) and all(l[-i] > l[-i-1] for i in range(1, 5)) if len(h) >= 5 else False
    def _lh_ll(self, h, l): return len(h) >= 10 and all(h[-i] < h[-i-1] for i in range(1, 5)) and all(l[-i] < l[-i-1] for i in range(1, 5)) if len(h) >= 5 else False
    def _be(self, o, c): return len(o) >= 2 and c[-1] > o[-1] and c[-2] < o[-2] and c[-1] > o[-2] and o[-1] < c[-2]
    def _be2(self, o, c): return len(o) >= 2 and c[-1] < o[-1] and c[-2] > o[-2] and c[-1] < o[-2] and o[-1] > c[-2]
    def _mar(self, o, h, l, c):
        if len(o) < 1: return False
        b = abs(c[-1] - o[-1]); uw = h[-1] - max(c[-1], o[-1]); lw = min(c[-1], o[-1]) - l[-1]
        return b > 0 and uw / b < 0.05 and lw / b < 0.05
    def _doji_brk(self, o, h, l, c):
        if len(h) < 10: return False
        tr = h[-1] - l[-1]
        if tr == 0: return False
        is_doji = abs(c[-1] - o[-1]) / tr < 0.1
        res = max(h[-10:-1])
        return is_doji and abs(c[-1] - res) / res < 0.02 if res > 0 else False
