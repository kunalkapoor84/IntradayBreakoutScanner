import numpy as np
import pandas as pd
from typing import Dict, List
from config.logging_setup import setup_logging
from models import StockData

logger = setup_logging("volume_analyzer")


class VolumeAnalyzer:
    def analyze(self, stock: StockData) -> Dict[str, float]:
        df = pd.DataFrame(stock.ohlc_daily) if stock.ohlc_daily else pd.DataFrame()
        if df.empty or len(df) < 20: return {}
        v = df["volume"].values.astype(float)
        c = df["close"].values.astype(float) if "close" in df.columns else np.ones_like(v)
        av = np.mean(v[-20:])
        rv = v[-1] / av if av > 0 else 1.0

        del_pct = 0.0
        try:
            dels = [d.get("deliveryQty", 0) for d in stock.ohlc_daily[-20:]]
            del_pct = (dels[-1] / v[-1] * 100) if v[-1] > 0 else 0
        except:
            pass

        return {
            "relative_volume": float(rv),
            "volume_spike": float(v[-1] > 2 * av),
            "avg_volume_20": float(av),
            "delivery_pct_latest": float(del_pct),
            "volume_dry_up": float(np.mean(v[-3:]) < np.mean(v[-10:-3]) * 0.6) if len(v) >= 10 else 0.0,
            "volume_expansion": float(v[-1] > 1.5 * np.mean(v[-5:-1]) and c[-1] > c[-2]) if len(v) >= 5 else 0.0,
            "institutional_accumulation": float(v[-1] * (2 * c[-1] - (c[-1] + c[-2]) / 2) / np.mean(v[-5:]) > 0.5) if len(v) >= 5 else 0.0,
            "institutional_distribution": float(v[-1] * (2 * c[-1] - (c[-1] + c[-2]) / 2) / np.mean(v[-5:]) < -0.5) if len(v) >= 5 else 0.0,
        }
