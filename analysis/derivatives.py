import numpy as np
from typing import Dict, List, Any
from config.logging_setup import setup_logging
from models import StockData, Direction

logger = setup_logging("derivatives_analyzer")


class DerivativesAnalyzer:
    def analyze(self, stock: StockData) -> Dict[str, Any]:
        r = {"oi_buildup": False, "long_buildup": False, "short_buildup": False,
             "long_unwinding": False, "short_covering": False, "highest_oi_strikes": [],
             "change_in_pcr": 0.0, "iv_percentile": 0.0, "call_writing": False,
             "put_writing": False, "direction_prediction": Direction.NEUTRAL.value,
             "volatility_outlook": "neutral"}
        if not stock.option_chain: return r
        oi, coi, pr = stock.open_interest, stock.change_oi, stock.price
        r["oi_buildup"] = abs(coi) > 0.1 * abs(oi) if oi > 0 else False
        ce = [o for o in stock.option_chain if str(o.get("option_type", "")).upper() == "CE"]
        pe = [o for o in stock.option_chain if str(o.get("option_type", "")).upper() == "PE"]
        cec = sum(o.get("change_oi", 0) or 0 for o in ce)
        pec = sum(o.get("change_oi", 0) or 0 for o in pe)
        if coi > 0 and oi > 0:
            if abs(cec) > abs(pec) * 0.5: r["long_buildup"] = True; r["direction_prediction"] = Direction.BULLISH.value
            elif abs(pec) > abs(cec) * 0.5: r["short_buildup"] = True; r["direction_prediction"] = Direction.BEARISH.value
        if coi < 0 and oi > 0:
            if cec < pec: r["long_unwinding"] = True; r["direction_prediction"] = Direction.BEARISH.value
            elif pec < cec: r["short_covering"] = True; r["direction_prediction"] = Direction.BULLISH.value
        r["change_in_pcr"] = stock.pcr
        r["iv_percentile"] = stock.iv
        r["call_writing"] = cec > 1000
        r["put_writing"] = pec > 1000
        iv = stock.iv
        r["volatility_outlook"] = "high_volatility" if iv > 40 else ("moderate_volatility" if iv > 25 else "low_volatility")
        return r
