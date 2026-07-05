import os
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
from config.settings import CONFIG
from config.logging_setup import setup_logging
from models import ScoredStock, StockData, TradePlan, Direction

logger = setup_logging("visualization")
plt.style.use("ggplot")


class ChartGenerator:
    def __init__(self): self.output_dir = f"{CONFIG.output_dir}\\charts"

    def generate_chart(self, stock: StockData, plan: TradePlan, scored: ScoredStock):
        if not stock.ohlc_daily or len(stock.ohlc_daily) < 30: return ""
        df = pd.DataFrame(stock.ohlc_daily[-60:])
        for c in ["open","high","low","close","volume"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14,9), gridspec_kw={"height_ratios": [3,1]})
        fig.suptitle(f"{stock.symbol} | Score: {scored.total_score:.1f} | {scored.direction.value if hasattr(scored.direction,'value') else scored.direction} | Conf: {scored.confidence:.0f}%", fontsize=14, fontweight="bold", color="#333")
        self._plot_candle(ax1, df, stock, plan); self._plot_vol(ax2, df)
        plt.tight_layout()
        fp = f"{self.output_dir}\\{stock.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(fp, dpi=150, bbox_inches="tight"); plt.close(); return fp

    def _plot_candle(self, ax, df, stock, plan):
        dates = range(len(df)); c = df["close"].values
        colors = ["#26a69a" if r["close"] >= r["open"] else "#ef5350" for _, r in df.iterrows()]
        ax.bar(dates, df["high"]-df["low"], bottom=df["low"], width=0.3, color="#999", alpha=0.4, linewidth=0)
        ax.bar(dates, abs(c-df["open"].values), bottom=np.minimum(df["open"].values,c), width=0.6, color=colors, alpha=0.9)
        if len(c) >= 20: ax.plot(dates, self._ema(c,20), "#e65100", alpha=0.8, lw=1.5, label="20 EMA")
        if len(c) >= 50: ax.plot(dates, self._ema(c,50), "#1565c0", alpha=0.8, lw=1.5, label="50 EMA")
        if stock.vwap > 0: ax.plot(dates, np.full(len(dates), stock.vwap), "#333", alpha=0.5, lw=1, ls="--", label="VWAP")
        trigger = plan.buy_above if plan.direction == Direction.BULLISH else (plan.sell_below if plan.direction == Direction.BEARISH else plan.entry_price)
        if trigger > 0: ax.axhline(y=trigger, xmin=0.8, xmax=1, color="#1565c0", lw=1.5, ls="--", label=f"Entry: {trigger:.2f}")
        if plan.entry_price > 0: ax.axhline(y=plan.entry_price, xmin=0.8, xmax=1, color="#999", lw=1, ls=":", alpha=0.6, label=f"CMP: {plan.entry_price:.2f}")
        if plan.stop_loss > 0: ax.axhline(y=plan.stop_loss, xmin=0.8, xmax=1, color="#d32f2f", lw=1.5, ls=":", label=f"SL: {plan.stop_loss}")
        if plan.target_1 > 0: ax.axhline(y=plan.target_1, xmin=0.8, xmax=1, color="#2e7d32", lw=1.5, ls=":", label=f"T1: {plan.target_1}")
        if plan.target_2 > 0: ax.axhline(y=plan.target_2, xmin=0.8, xmax=1, color="#2e7d32", lw=1.5, ls="--", label=f"T2: {plan.target_2}")
        if plan.breakout_level > 0: ax.axhline(y=plan.breakout_level, xmin=0.8, xmax=1, color="#f57c00", lw=1.5, ls="-", label=f"BO: {plan.breakout_level}")
        ax.set_ylabel("Price"); ax.legend(loc="upper left", fontsize=8, facecolor="white", edgecolor="#ccc"); ax.set_xticks([]); ax.grid(True, alpha=0.3)

    def _plot_vol(self, ax, df):
        dates = range(len(df))
        colors = ["#26a69a" if r["close"] >= r["open"] else "#ef5350" for _, r in df.iterrows()]
        ax.bar(dates, df["volume"].values, color=colors, alpha=0.6)
        ax.set_ylabel("Volume"); ax.set_xlabel("Trading Days"); ax.grid(True, alpha=0.3)
        av = np.mean(df["volume"].values[-20:]) if len(df) >= 20 else np.mean(df["volume"].values)
        ax.axhline(y=av, color="#e65100", lw=1, ls="--", alpha=0.7, label=f"Avg Vol: {av:.0f}")
        ax.legend(loc="upper left", fontsize=8, facecolor="white", edgecolor="#ccc")

    def _ema(self, d, p):
        if len(d) < p: return np.full_like(d, np.nan)
        m = 2/(p+1); e = np.full_like(d, np.nan); e[p-1] = np.mean(d[:p])
        for i in range(p, len(d)): e[i] = (d[i]-e[i-1])*m + e[i-1]
        return e
