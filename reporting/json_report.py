import json
from datetime import datetime
from config.settings import CONFIG
from config.logging_setup import setup_logging
from models import ScannerOutput
from scoring.ai_scorer import AIScorer

logger = setup_logging("json_report")


_scorer = AIScorer()

class JSONReportGenerator:
    def generate(self, output: ScannerOutput, filepath: str = ""):
        if not filepath:
            filepath = f"{CONFIG.output_dir}\\reports\\scanner_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data = {"generated_at": output.generated_at, "total_analyzed": output.total_stocks_analyzed,
                "shortlisted": output.stocks_shortlisted, "top_stocks": [
            {"rank": r, "symbol": s.symbol, "score": round(s.total_score,1), "confidence": round(s.confidence,1),
             "direction": s.direction.value if hasattr(s.direction,'value') else s.direction,
             "entry": s.entry_price, "cmp": s.cmp, "sl": s.stop_loss, "t1": s.target_1, "t2": s.target_2,
             "atr": round(s.atr,2), "volume_ratio": round(s.volume_ratio,2), "rsi": round(s.rsi,1),
             "adx": round(s.adx,1), "pcr": round(s.pcr,2), "oi_change": s.oi_change, "iv": round(s.iv,1),
             "sector": s.sector, "strategy": s.strategy, "pattern": s.pattern_detected,
             "expected_move_pct": round(s.expected_move_pct,2), "rr": round(s.risk_reward,2),
             "position_size": s.position_size, "catalyst": s.catalyst, "chart": s.chart_path,
             "bollinger_squeeze": s.bollinger_squeeze, "nr_detected": s.nr_detected,
             "breakout_proximity": round(s.breakout_proximity, 1), "band": _scorer.get_confidence_band(s.total_score)}
            for r, s in enumerate(output.top_stocks, 1)]}
        with open(filepath, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, default=str)
        logger.info(f"JSON saved: {filepath}")
        return filepath
