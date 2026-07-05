import numpy as np
from typing import Dict, List, Optional, Tuple
from config.settings import CONFIG
from config.logging_setup import setup_logging
from models import StockData, AnalysisResult, ScoredStock, Direction, PatternType, TradePlan, StrategyType
from analysis.liquidity import LiquidityFilter
from analysis.momentum import MomentumAnalyzer
from analysis.patterns import PatternDetector
from analysis.volume import VolumeAnalyzer
from analysis.derivatives import DerivativesAnalyzer
from analysis.volatility import VolatilityAnalyzer
from analysis.relative_strength import RelativeStrengthAnalyzer
from analysis.gap_probability import GapProbabilityAnalyzer

logger = setup_logging("ai_scorer")


class AIScorer:
    def __init__(self):
        self.liquidity = LiquidityFilter()
        self.momentum = MomentumAnalyzer()
        self.patterns = PatternDetector()
        self.volume = VolumeAnalyzer()
        self.derivatives = DerivativesAnalyzer()
        self.volatility = VolatilityAnalyzer()
        self.relative_strength = RelativeStrengthAnalyzer()
        self.gap = GapProbabilityAnalyzer()
        self.weights = CONFIG.weights
        self.market_regime = self._detect_market_regime()

    def analyze_stock(self, stock: StockData) -> Tuple[bool, AnalysisResult, TradePlan]:
        result = AnalysisResult(symbol=stock.symbol)

        ms = self.momentum.analyze(stock)
        result.momentum_signals = ms
        result.rsi = self._compute_rsi(stock)
        result.adx = ms.get("adx", 0)
        result.macd_signal = "bullish" if ms.get("macd_bullish_cross") else ("bearish" if ms.get("macd_bearish_cross") else "neutral")

        result.patterns = self.patterns.detect_all(stock)
        result.volume_signals = self.volume.analyze(stock)
        result.derivatives_signals = self.derivatives.analyze(stock)
        result.volatility_metrics = self.volatility.analyze(stock)
        result.relative_strength = self.relative_strength.analyze(stock)
        result.gap_probability = self.gap.predict(stock)
        result.atr = result.volatility_metrics.get("atr", 0)
        result.atr_pct = result.volatility_metrics.get("atr_pct", 0)

        scores = self._compute_scores(result, stock)
        result.total_score = sum(scores.values())
        result.total_score = min(100, max(0, result.total_score))
        result.direction, result.confidence = self._determine_direction(result)
        trade_plan = self._generate_trade_plan(stock, result)
        return True, result, trade_plan

    def _compute_rsi(self, stock: StockData) -> float:
        try:
            c = np.array([float(d.get("close", 0)) for d in stock.ohlc_daily if d.get("close")])
            if len(c) < 15:
                return 50.0
            d = np.diff(c)
            g = np.where(d > 0, d, 0)
            ls = np.where(d < 0, -d, 0)
            ag = np.mean(g[:14])
            al = np.mean(ls[:14])
            for i in range(14, len(g)):
                ag = (ag * 13 + g[i]) / 14
                al = (al * 13 + ls[i]) / 14
            return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
        except:
            return 50.0

    def _compute_ema(self, values, period):
        if len(values) < period:
            return np.array([])
        m = 2 / (period + 1)
        e = np.full_like(values, np.nan)
        e[period - 1] = np.mean(values[:period])
        for i in range(period, len(values)):
            e[i] = (values[i] - e[i - 1]) * m + e[i - 1]
        return e

    def _ema_rising(self, ema):
        if len(ema) < 2:
            return False
        return ema[-1] > ema[-2]

    def _compute_scores(self, r: AnalysisResult, stock: StockData) -> Dict[str, float]:
        w = self.weights
        raw = {
            "trend": self._score_trend(stock),
            "price_action": self._score_pa(r, stock),
            "volume": self._score_vol(r),
            "momentum": self._score_momentum(r),
            "volatility": self._score_volty(r, stock),
            "relative_strength": self._score_rs(r),
            "liquidity": self._score_liquidity(stock),
            "market_context": self._score_market_context(r),
        }
        maxes = {
            "trend": 25.0, "price_action": 30.0, "volume": 15.0,
            "momentum": 17.0, "volatility": 10.0, "relative_strength": 10.0,
            "liquidity": 10.0, "market_context": 8.0,
        }
        wmap = {"trend": w.trend, "price_action": w.price_action, "volume": w.volume,
                "momentum": w.momentum, "volatility": w.volatility,
                "relative_strength": w.relative_strength, "liquidity": w.liquidity,
                "market_context": w.market_context}
        return {k: min(v / maxes[k], 1.0) * wmap[k] for k, v in raw.items()}

    def _score_trend(self, stock: StockData) -> float:
        c = np.array([float(d.get("close", 0)) for d in stock.ohlc_daily if d.get("close")])
        if len(c) < 50:
            return 5.0
        s = 0.0
        e20 = self._compute_ema(c, 20)
        e50 = self._compute_ema(c, 50)
        e200 = self._compute_ema(c, 200)
        lc = c[-1]
        if len(e20) > 0 and lc > e20[-1]:
            s += 4
        if len(e50) > 0 and lc > e50[-1]:
            s += 4
        if len(e200) > 0 and lc > e200[-1]:
            s += 4
        if len(e20) > 0 and self._ema_rising(e20):
            s += 4
        if len(e50) > 0 and self._ema_rising(e50):
            s += 4
        if len(e20) > 0 and len(e50) > 0 and e20[-1] > e50[-1]:
            s += 3
        if len(e50) > 0 and len(e200) > 0 and e50[-1] > e200[-1]:
            s += 2
        return min(25, s)

    def _score_pa(self, r: AnalysisResult, stock: StockData) -> float:
        s = 3.0
        c = np.array([float(d.get("close", 0)) for d in stock.ohlc_daily if d.get("close")])
        h = np.array([float(d.get("high", 0)) for d in stock.ohlc_daily if d.get("high")])
        l = np.array([float(d.get("low", 0)) for d in stock.ohlc_daily if d.get("low")])

        if len(c) >= 20 and c[-1] > 0:
            d20_high = max(h[-20:])
            bp = (d20_high - c[-1]) / c[-1] * 100
            if bp <= 2:
                s += 5
            elif bp <= 5:
                s += 3
        if len(h) >= 3 and h[-1] < h[-2] and l[-1] > l[-2]:
            s += 3
        if len(h) >= 20:
            bbw = self._bollinger_width(c)
            if bbw < 15:
                s += 4
        if len(h) >= 8:
            nr = (h[-8:] - l[-8:])[-1] == min(h[-8:] - l[-8:])
            if nr:
                s += 3
        for p in r.patterns:
            s += {PatternType.BULL_FLAG: 4, PatternType.BEAR_FLAG: 3, PatternType.CUP_HANDLE: 4,
                  PatternType.ASCENDING_TRIANGLE: 4, PatternType.VCP: 4, PatternType.DARVAS_BOX: 3,
                  PatternType.TIGHT_CONSOLIDATION: 3, PatternType.ORB_SETUP: 3,
                  PatternType.BULLISH_ENGULFING: 3, PatternType.MARUBOZU: 3,
                  PatternType.DOJI_NEAR_BREAKOUT: 4, PatternType.HH_HL: 3,
                  PatternType.NR7: 2, PatternType.FALLING_WEDGE: 2, PatternType.RISING_WEDGE: 2,
                  PatternType.INSIDE_BAR: 2, PatternType.NR4: 1,
                  PatternType.LH_LL: 1, PatternType.BEARISH_ENGULFING: 1,
                  PatternType.DESCENDING_TRIANGLE: 1, PatternType.DOUBLE_INSIDE_BAR: 1}.get(p, 1)
        vs = r.volume_signals
        if vs.get("relative_volume", 0) > 2:
            s += 3
        elif vs.get("relative_volume", 0) > 1.5:
            s += 2
        elif vs.get("relative_volume", 0) > 1.2:
            s += 1
        return min(30, s)

    def _score_vol(self, r: AnalysisResult) -> float:
        rv = r.volume_signals.get("relative_volume", 0)
        if rv >= 3:
            return 15
        elif rv >= 2:
            return 12
        elif rv >= 1.5:
            return 9
        elif rv >= 1.2:
            return 6
        elif rv >= 0.8:
            return 3
        return 2

    def _score_momentum(self, r: AnalysisResult) -> float:
        s = 2.0
        rsi = r.rsi
        if 55 <= rsi <= 65:
            s += 7
        elif 65 < rsi <= 70:
            s += 5
        elif 50 <= rsi < 55:
            s += 5
        elif 45 <= rsi < 50:
            s += 3
        elif 70 < rsi <= 75:
            s += 2
        elif rsi < 45 or rsi > 75:
            s += 1
        adx = r.adx
        if adx >= 28:
            s += 5
        elif adx >= 22:
            s += 4
        elif adx >= 18:
            s += 3
        else:
            s += 1
        if r.momentum_signals.get("macd_bullish_cross"):
            s += 3
        elif r.momentum_signals.get("macd_bearish_cross"):
            s += 1
        return min(17, s)

    def _score_volty(self, r: AnalysisResult, stock: StockData) -> float:
        s = 2.0
        v = r.volatility_metrics
        atr_pct = v.get("atr_pct", 0)
        if 1.5 <= atr_pct <= 5:
            s += 3
        elif atr_pct > 5:
            s += 2
        elif atr_pct > 0.8:
            s += 1
        if v.get("bollinger_band_squeeze"):
            s += 3
        if v.get("expected_move_pct", 0) > 1.5:
            s += 2
        return min(10, s)

    def _score_rs(self, r: AnalysisResult) -> float:
        rs = r.relative_strength
        rs5 = rs.get("rs_5day", 0)
        rs20 = rs.get("rs_20day", 0)
        s = 1.0
        if rs20 > 10:
            s += 4
        elif rs20 > 5:
            s += 3
        elif rs20 > 2:
            s += 2
        elif rs20 > 0:
            s += 1
        if rs5 > 5:
            s += 3
        elif rs5 > 2:
            s += 2
        elif rs5 > 0:
            s += 1
        return min(10, s)

    def _score_liquidity(self, stock: StockData) -> float:
        s = 1.0
        to = stock.avg_turnover_crore
        if to >= 50:
            s += 4
        elif to >= 20:
            s += 3
        elif to >= 10:
            s += 2
        elif to >= 5:
            s += 1
        vol = stock.avg_volume_lakhs
        if vol >= 20:
            s += 4
        elif vol >= 10:
            s += 3
        elif vol >= 5:
            s += 2
        elif vol >= 2:
            s += 1
        if stock.price >= 100:
            s += 1
        return min(10, s)

    def _score_market_context(self, r: AnalysisResult) -> float:
        s = 2.0
        regime = self.market_regime
        rsi = r.rsi
        adx = r.adx
        if regime == "trending":
            if adx >= 22:
                s += 3
            if rsi >= 55:
                s += 2
        elif regime == "sideways":
            bb_sqz = r.volatility_metrics.get("bollinger_band_squeeze", False)
            if bb_sqz:
                s += 3
            if any(p in [PatternType.NR7, PatternType.NR4, PatternType.TIGHT_CONSOLIDATION] for p in r.patterns):
                s += 2
        elif regime == "weak":
            rs = r.relative_strength
            if rs.get("rs_20day", 0) > 0:
                s += 3
            if rs.get("rs_5day", 0) > 2:
                s += 2
        return min(8, s)

    def _bollinger_width(self, c):
        if len(c) < 20:
            return 100
        s = np.mean(c[-20:])
        std = np.std(c[-20:])
        return 4 * std / s * 100 if s > 0 else 100

    def _detect_market_regime(self) -> str:
        return "neutral"

    def _determine_direction(self, r: AnalysisResult) -> Tuple[Direction, float]:
        bull, bear = 0, 0
        ms = r.momentum_signals
        if ms.get("rsi_bullish"): bull += 2
        if ms.get("rsi_bearish"): bear += 2
        if ms.get("macd_bullish_cross"): bull += 2
        if ms.get("macd_bearish_cross"): bear += 2
        if ms.get("ema20_above_ema50"): bull += 1
        if ms.get("ema20_below_ema50"): bear += 1
        if ms.get("price_above_vwap"): bull += 1
        if ms.get("price_below_vwap"): bear += 1
        if ms.get("large_bullish_candle"): bull += 1
        if ms.get("large_bearish_candle"): bear += 1
        for p in r.patterns:
            if p in [PatternType.BULL_FLAG, PatternType.ASCENDING_TRIANGLE, PatternType.CUP_HANDLE, PatternType.BULLISH_ENGULFING]:
                bull += 2
            elif p in [PatternType.BEAR_FLAG, PatternType.DESCENDING_TRIANGLE, PatternType.BEARISH_ENGULFING]:
                bear += 2
        if r.rsi >= 60: bull += 1
        elif r.rsi <= 40: bear += 1
        if r.volume_signals.get("relative_volume", 0) > 1.5:
            if bull >= bear: bull += 1
            else: bear += 1
        total = max(bull + bear, 1)
        conf = abs(bull - bear) / total * 100
        if bull > bear:
            return Direction.BULLISH, min(90, conf * 1.4 + 30)
        elif bear > bull:
            return Direction.BEARISH, min(90, conf * 1.4 + 30)
        return Direction.NEUTRAL, max(20, conf)

    def _generate_trade_plan(self, stock: StockData, r: AnalysisResult) -> TradePlan:
        plan = TradePlan(symbol=stock.symbol, direction=r.direction, confidence_pct=r.confidence, atr=r.atr)
        c, a = stock.price, r.atr
        plan.entry_price = c
        if r.direction == Direction.BULLISH:
            entry = round(c + a * 0.3, 2)
            plan.entry_price = entry
            plan.buy_above = entry
            plan.stop_loss = round(entry - a * 0.75, 2)
            plan.target_1 = round(entry + a * 0.75, 2)
            plan.target_2 = round(entry + a * 1.5, 2)
            plan.support = round(entry - a * 0.5, 2)
            plan.resistance = round(entry + a, 2)
            plan.breakout_level = round(entry + a * 0.25, 2)
        elif r.direction == Direction.BEARISH:
            entry = round(c - a * 0.3, 2)
            plan.entry_price = entry
            plan.sell_below = entry
            plan.stop_loss = round(entry + a * 0.75, 2)
            plan.target_1 = round(entry - a * 0.75, 2)
            plan.target_2 = round(entry - a * 1.5, 2)
            plan.support = round(entry - a, 2)
            plan.resistance = round(entry + a * 0.5, 2)
            plan.breakout_level = round(entry - a * 0.25, 2)
        else:
            plan.buy_above, plan.sell_below = 0, 0
            plan.stop_loss = round(c - a * 0.5, 2)
            plan.target_1 = round(c + a * 0.5, 2)
            plan.target_2 = round(c + a, 2)
            plan.support = round(c - a * 0.5, 2)
            plan.resistance = round(c + a * 0.5, 2)
            plan.breakout_level = 0
        plan.expected_move_pct = r.volatility_metrics.get("expected_move_pct", r.atr_pct)
        risk = abs(plan.entry_price - plan.stop_loss)
        plan.risk_reward_ratio = round(abs(plan.target_1 - plan.entry_price) / risk, 2) if risk > 0 else 0
        plan.recommended_position_size = max(1, int(CONFIG.scanner.max_risk_per_trade / risk)) if risk > 0 else 1
        pats = [p.value for p in r.patterns]
        if any(p in pats for p in ["ORB Setup", "NR7", "NR4", "Inside Bar"]):
            plan.best_strategy = StrategyType.ORB
        elif "Tight Consolidation" in pats or r.volatility_metrics.get("bollinger_band_squeeze"):
            plan.best_strategy = StrategyType.BREAKOUT
        elif r.momentum_signals.get("adx_strong"):
            plan.best_strategy = StrategyType.TREND_FOLLOWING
        elif any(p in pats for p in ["Bull Flag", "Ascending Triangle", "Cup & Handle"]):
            plan.best_strategy = StrategyType.BREAKOUT
        elif any(p in pats for p in ["Bear Flag", "Descending Triangle"]):
            plan.best_strategy = StrategyType.BREAKDOWN
        elif r.gap_probability.get("gap_up_probability", 0) > 40:
            plan.best_strategy = StrategyType.GAP_TRADE
        else:
            plan.best_strategy = StrategyType.ORB
        return plan

    def shortlist(self, stocks: List[ScoredStock]) -> List[ScoredStock]:
        return sorted(stocks, key=lambda s: (s.total_score, s.confidence, s.risk_reward), reverse=True)[:CONFIG.scanner.top_n]

    def get_categories(self, stocks: List[ScoredStock]) -> Dict[str, List[ScoredStock]]:
        sorted_all = sorted(stocks, key=lambda s: s.total_score, reverse=True)
        bullish = sorted([s for s in stocks if s.direction == Direction.BULLISH], key=lambda s: s.total_score, reverse=True)[:10]
        bearish = sorted([s for s in stocks if s.direction == Direction.BEARISH], key=lambda s: s.total_score, reverse=True)[:10]
        high_vol = sorted([s for s in stocks if s.atr > 0], key=lambda s: s.atr / max(s.cmp, 1) * 100, reverse=True)[:10]
        breakout = sorted([s for s in stocks if s.breakout_proximity <= 2 or s.bollinger_squeeze or s.nr_detected], key=lambda s: s.total_score, reverse=True)[:10]
        mr = sorted([s for s in stocks if (s.direction == Direction.BULLISH and 45 <= s.rsi <= 50) or (s.direction == Direction.BEARISH and 55 <= s.rsi <= 65)], key=lambda s: s.total_score, reverse=True)[:10]
        return {
            "top_20": sorted_all[:20],
            "top_bullish": bullish,
            "top_bearish": bearish,
            "top_high_volatility": high_vol,
            "top_breakout_watch": breakout,
            "top_mean_reversion": mr,
        }

    def get_confidence_band(self, score: float) -> str:
        if score >= 85: return "*****"
        if score >= 75: return "****"
        if score >= 65: return "***"
        if score >= 55: return "**"
        return "Monitor"
