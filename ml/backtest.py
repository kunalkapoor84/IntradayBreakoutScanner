import numpy as np
import pandas as pd
from typing import Dict, List
from config.logging_setup import setup_logging

logger = setup_logging("backtester")


class Backtester:
    def backtest(self, historical_data: Dict[str, List[Dict]], target_pct: float = 2.0) -> dict:
        total, wins = 0, 0
        for sym, bars in historical_data.items():
            if len(bars) < 60: continue
            df = pd.DataFrame(bars)
            for c in ["open","high","low","close","volume"]:
                if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
            for i in range(50, len(df)-1):
                train = df.iloc[:i]; test = df.iloc[i]; nxt = df.iloc[i+1]
                pred = self._predict(train)
                move = (nxt["close"] - test["close"]) / test["close"] * 100
                correct = (pred == "Bullish" and move > 0) or (pred == "Bearish" and move < 0)
                total += 1
                if correct: wins += 1
        wr = wins / total * 100 if total > 0 else 0
        logger.info(f"Backtest: {total} trades, win rate {wr:.1f}%")
        return {"trades": total, "wins": wins, "win_rate": round(wr, 1)}

    def _predict(self, df):
        c = df["close"].values
        if len(c) < 20: return "Neutral"
        e20, e50 = np.mean(c[-20:]), np.mean(c[-50:]) if len(c) >= 50 else np.mean(c[-20:])
        if c[-1] > e20 > e50: return "Bullish"
        if c[-1] < e20 < e50: return "Bearish"
        return "Neutral"
