from typing import Dict, Tuple
from config.logging_setup import setup_logging

logger = setup_logging("ml_model")


class RuleBasedPredictor:
    def predict(self, analysis_result) -> Tuple[str, float]:
        bull, bear = 0, 0
        ms = analysis_result.momentum_signals
        vs = analysis_result.volume_signals
        ds = analysis_result.derivatives_signals
        rs = analysis_result.relative_strength
        if ms.get("rsi_bullish"): bull += 8
        if ms.get("rsi_bearish"): bear += 8
        if ms.get("adx_strong"):
            bull += 5 if ms.get("ema20_above_ema50") else 0
            bear += 5 if ms.get("ema20_below_ema50") else 0
        if ds.get("long_buildup"): bull += 10
        if ds.get("short_buildup"): bear += 10
        if ds.get("short_covering"): bull += 7
        if ds.get("long_unwinding"): bear += 7
        if vs.get("relative_volume", 0) > 2:
            bull += 5 if ms.get("price_above_vwap") else 0
            bear += 5 if ms.get("price_below_vwap") else 0
        if rs.get("rs_5day", 0) > 2: bull += 5
        if rs.get("rs_5day", 0) < -2: bear += 5
        total = max(bull + bear, 1)
        if bull > bear: return "Bullish", min(95, bull / total * 100)
        elif bear > bull: return "Bearish", min(95, bear / total * 100)
        return "Neutral", 50.0
