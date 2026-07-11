import sys, os, time, shutil
from datetime import datetime
from pathlib import Path
from typing import List
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import CONFIG
from config.logging_setup import setup_logging
from data.collect_data import DataCollector, _is_market_open_now
from data.time_utils import now_ist
from scoring.ai_scorer import AIScorer
from reporting.excel_report import ExcelReportGenerator
from reporting.csv_report import CSVReportGenerator
from reporting.json_report import JSONReportGenerator
from reporting.html_report import HTMLReportGenerator
from reporting.visualization import ChartGenerator
from alerts.telegram import TelegramAlert
from alerts.email_alert import EmailAlert
from models import StockData, AnalysisResult, ScoredStock, ScannerOutput, TradePlan, Direction

logger = setup_logging("scanner")


def clear_output_dirs():
    for d in [Path("output/reports"), Path("output/charts")]:
        if d.exists():
            shutil.rmtree(d)
            logger.info("Cleared %s", d)
        d.mkdir(parents=True, exist_ok=True)


class ScannerEngine:
    def __init__(self):
        self.data = DataCollector()
        self.scorer = AIScorer()
        self.xlsx = ExcelReportGenerator()
        self.csv = CSVReportGenerator()
        self.json = JSONReportGenerator()
        self.html = HTMLReportGenerator()
        self.chart = ChartGenerator()
        self.telegram = TelegramAlert()
        self.email = EmailAlert()

    def run(self) -> ScannerOutput:
        clear_output_dirs()
        market_open = _is_market_open_now()
        mode_str = "LIVE 15min" if market_open else "AFTER-HOURS daily"
        logger.info("=" * 60)
        logger.info(f"INTRADAY BREAKOUT SCANNER - Starting ({mode_str})")
        logger.info("=" * 60)
        out = ScannerOutput(generated_at=now_ist().strftime("%Y-%m-%d %H:%M:%S"))
        all_s = self.data.collect_all_stocks()
        out.total_stocks_analyzed = len(all_s)
        scored: List[ScoredStock] = []
        for idx, (sym, stock) in enumerate(all_s.items()):
            try:
                _, result, plan = self.scorer.analyze_stock(stock, market_open=market_open)
                ss = self._build(stock, result, plan, idx)
                scored.append(ss)
                band = self.scorer.get_confidence_band(ss.total_score)
                logger.info(f"[{idx+1}/{len(all_s)}] {sym} | Score: {ss.total_score:.1f} {band} | {result.direction.value} | Conf: {ss.confidence:.0f}% | Pattern: {ss.pattern_detected[:30] or 'N/A'}")
                try:
                    chart_fp = self.chart.generate_chart(stock, plan, ss)
                    if chart_fp: ss.chart_path = chart_fp
                except: pass
            except Exception as e: logger.error(f"Error {sym}: {e}")
        out.all_scored = scored
        out.top_stocks = self.scorer.shortlist(scored)
        cats = self.scorer.get_categories(scored)
        out.top_bullish = cats["top_bullish"]
        out.top_bearish = cats["top_bearish"]
        out.top_high_volatility = cats["top_high_volatility"]
        out.top_breakout_watch = cats["top_breakout_watch"]
        out.top_mean_reversion = cats["top_mean_reversion"]
        out.market_regime = self.scorer.market_regime
        out.stocks_shortlisted = len(out.top_stocks)
        logger.info(f"Shortlisted: {out.stocks_shortlisted}")
        self._enrich_top_with_option_chain(out, scored, all_s)
        try:
            self.xlsx.generate(out)
            self.csv.generate(out)
            self.json.generate(out)
            html_fp = self.html.generate(out)
        except Exception as e:
            logger.error(f"Reports failed: {e}")
            html_fp = None
        self.telegram.send_report(out)
        if html_fp:
            try: self.telegram.send_file(html_fp)
            except Exception as e: logger.error(f"Telegram file send failed: {e}")
        self.email.send_report(out)
        self._print(out)
        return out

    def _build(self, stock: StockData, r: AnalysisResult, plan: TradePlan, idx: int) -> ScoredStock:
        bp, bs, nr = 100.0, False, False
        try:
            h = [float(d.get("high", 0)) for d in stock.ohlc_daily if d.get("high")]
            c = [float(d.get("close", 0)) for d in stock.ohlc_daily if d.get("close")]
            l = [float(d.get("low", 0)) for d in stock.ohlc_daily if d.get("low")]
            if len(c) >= 20 and c[-1] > 0:
                d20_high = max(h[-20:])
                bp = (d20_high - c[-1]) / c[-1] * 100
            if len(c) >= 20:
                s = np.mean(c[-20:])
                std = np.std(c[-20:])
                bs = bool((4 * std / s * 100 < 20) if s > 0 else False)
            if len(h) >= 8:
                nr = bool((np.array(h[-8:]) - np.array(l[-8:]))[-1] == min(np.array(h[-8:]) - np.array(l[-8:])))
        except:
            pass
        return ScoredStock(symbol=stock.symbol, total_score=round(r.total_score,1), confidence=round(r.confidence,1),
                          direction=r.direction, entry_price=plan.entry_price, cmp=stock.price, entry_trigger=plan.entry_price,
                          stop_loss=plan.stop_loss, target_1=plan.target_1, target_2=plan.target_2, atr=r.atr,
                          volume_ratio=r.volume_signals.get("relative_volume",0), rsi=r.rsi, adx=r.adx,
                          pcr=stock.pcr, oi_change=stock.change_oi, iv=stock.iv, sector=stock.sector,
                          catalyst=self._catalyst(stock, r),
                          pattern_detected=", ".join([p.value for p in r.patterns[:3]]),
                          expected_move_pct=plan.expected_move_pct, risk_reward=plan.risk_reward_ratio,
                          position_size=plan.recommended_position_size,
                          strategy=plan.best_strategy.value if hasattr(plan.best_strategy,'value') else str(plan.best_strategy),
                          breakout_proximity=round(bp, 2), bollinger_squeeze=bs, nr_detected=nr)

    def _catalyst(self, stock: StockData, r: AnalysisResult) -> str:
        c = []
        if stock.earnings_date: c.append("Earnings")
        if stock.corporate_actions: c.append("Corp Action")
        if stock.block_deals: c.append("Block Deal")
        if "Bullish" in str(r.direction) and r.volume_signals.get("institutional_accumulation"): c.append("Inst Accumulation")
        if "Bearish" in str(r.direction) and r.volume_signals.get("institutional_distribution"): c.append("Inst Distribution")
        return "; ".join(c) if c else "Technical"

    def _enrich_top_with_option_chain(self, out: ScannerOutput, scored: List[ScoredStock], all_s: dict):
        top_symbols = [s.symbol for s in out.top_stocks]
        if not top_symbols:
            return
        logger.info(f"Fetching option chain for top {len(top_symbols)} symbols...")
        nearest_expiry = ""
        for sym in top_symbols:
            try:
                if not nearest_expiry:
                    sid = int(self.data.client._get_security_id(sym))
                    nearest_expiry = self.data.client._get_nearest_expiry(sid)
                    time.sleep(3)
                chain = self.data.client.get_option_chain(sym, expiry=nearest_expiry)
                time.sleep(3)
                if not chain:
                    continue
                stock = all_s.get(sym)
                if not stock:
                    continue
                ce = [o for o in chain if str(o.get("option_type", "")).upper() == "CE"]
                pe = [o for o in chain if str(o.get("option_type", "")).upper() == "PE"]
                ce_oi = sum(o.get("open_interest", 0) or 0 for o in ce)
                pe_oi = sum(o.get("open_interest", 0) or 0 for o in pe)
                coi = sum(o.get("change_oi", 0) or 0 for o in ce) + sum(o.get("change_oi", 0) or 0 for o in pe)
                ivs = [o.get("iv", 0) or 0 for o in chain if (o.get("iv") or 0) > 0]
                stock.option_chain = chain
                stock.open_interest = ce_oi + pe_oi
                stock.change_oi = coi
                stock.pcr = round(pe_oi / max(ce_oi, 1), 2)
                stock.iv = round(float(np.mean(ivs)), 2) if ivs else 0.0
                idx = next((i for i, s in enumerate(scored) if s.symbol == sym), -1)
                if idx >= 0:
                    old_chart_path = scored[idx].chart_path
                    _, result, plan = self.scorer.analyze_stock(stock, market_open=_is_market_open_now())
                    scored[idx] = self._build(stock, result, plan, idx)
                    scored[idx].chart_path = old_chart_path
                    logger.info(f"  OC enriched: {sym} | OI: {stock.open_interest:,} | PCR: {stock.pcr} | IV: {stock.iv}%")
            except Exception as e:
                logger.debug(f"Option chain failed for {sym}: {e}")
        out.top_stocks = self.scorer.shortlist(scored)
        cats = self.scorer.get_categories(scored)
        out.top_bullish = cats["top_bullish"]
        out.top_bearish = cats["top_bearish"]
        out.top_high_volatility = cats["top_high_volatility"]
        out.top_breakout_watch = cats["top_breakout_watch"]
        out.top_mean_reversion = cats["top_mean_reversion"]

    def _print(self, out: ScannerOutput):
        self._print_category("TOP 20 OVERALL", out.top_stocks, out)
        self._print_category("TOP 10 BULLISH", out.top_bullish, out)
        self._print_category("TOP 10 BEARISH", out.top_bearish, out)
        self._print_category("TOP 10 HIGH VOLATILITY", out.top_high_volatility, out)
        self._print_category("TOP 10 BREAKOUT WATCH", out.top_breakout_watch, out)
        self._print_category("TOP 10 MEAN REVERSION", out.top_mean_reversion, out)

    def _print_category(self, title: str, stocks: List[ScoredStock], out: ScannerOutput):
        if not stocks:
            return
        print("\n" + "=" * 100)
        print(f"  {title}  |  Regime: {out.market_regime.upper()}  |  Analyzed: {out.total_stocks_analyzed}")
        print("=" * 100)
        print(f"  {'#':<4} {'Symbol':<12} {'Score':<6} {'Band':<12} {'Dir':<9} {'Conf':<5} {'Entry':<10} {'SL':<10} {'T1':<10} {'R:R':<6} {'ATR%':<6} {'Pattern':<22}")
        print("-" * 100)
        for i, s in enumerate(stocks, 1):
            d = s.direction.value if hasattr(s.direction, 'value') else str(s.direction)
            band = self.scorer.get_confidence_band(s.total_score)
            atr_pct = f"{s.atr / max(s.cmp, 1) * 100:.1f}%" if s.atr else "N/A"
            pat = s.pattern_detected[:22] if s.pattern_detected else "-"
            extras = ""
            if s.bollinger_squeeze: extras += " BB-SQZ"
            if s.nr_detected: extras += " NR"
            if s.breakout_proximity <= 2: extras += f" BRK-{s.breakout_proximity:.0f}%"
            print(f"  {i:<4} {s.symbol:<12} {s.total_score:<6.1f} {band:<12} {d:<9} {s.confidence:<5.0f} {s.entry_price:<10.2f} {s.stop_loss:<10.2f} {s.target_1:<10.2f} {s.risk_reward:<6.2f} {atr_pct:<6} {pat:<22}{extras}")


def main():
    import argparse
    p = argparse.ArgumentParser(description="Intraday Breakout Scanner")
    p.add_argument("--mode", choices=["scan","schedule","live"], default="scan")
    p.add_argument("--symbol", type=str, default="")
    a = p.parse_args()
    if a.mode == "schedule":
        from scheduler.scanner_scheduler import ScannerScheduler
        s = ScannerScheduler(); s.start()
        try:
            while True: time.sleep(60)
        except KeyboardInterrupt: s.stop()
    elif a.mode == "live":
        eng = ScannerEngine()
        while True: eng.run(); time.sleep(300)
    else:
        eng = ScannerEngine()
        if a.symbol:
            market_open = _is_market_open_now()
            stock = eng.data.collect_symbol_data(a.symbol.upper(), market_open=market_open)
            if stock:
                _, r, plan = eng.scorer.analyze_stock(stock, market_open=market_open)
                print(f"\nSymbol: {stock.symbol}\nPrice: {stock.price}\nScore: {r.total_score:.1f}\nDirection: {r.direction.value if hasattr(r.direction,'value') else r.direction}\nConfidence: {r.confidence:.1f}%\nEntry: {plan.entry_price}\nSL: {plan.stop_loss}\nT1: {plan.target_1}\nT2: {plan.target_2}\nStrategy: {plan.best_strategy.value if hasattr(plan.best_strategy,'value') else plan.best_strategy}\nPatterns: {', '.join([p.value for p in r.patterns])}")
        else:
            eng.run()


if __name__ == "__main__":
    main()
