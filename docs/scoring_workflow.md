# Intraday Breakout Scanner — Full Scoring & Selection Workflow

This document explains the end-to-end pipeline: how 219 NSE F&O stocks are analyzed, scored, and filtered down to a Top 20 shortlist.

---

## 1. Data Collection Phase

**File:** `data/collect_data.py` — `DataCollector.collect_all_stocks()`

The scanner iterates over a hardcoded list of NSE F&O stocks (NSE_FO_STOCKS). For each symbol, it calls `collect_symbol_data()` which gathers:

| Data Element | Source | Details |
|---|---|---|
| **Daily OHLCV** | `client.get_historical_daily()` | 1-year history (~250 trading days) |
| **5-min Intraday OHLCV** | `client.get_historical_intraday(interval=5)` | Last 20 trading days |
| **15-min Intraday OHLCV** | `client.get_historical_intraday(interval=15)` | Last 5 trading days (only if market is open) |
| **Live Price** | Quote cache or `client.get_quote()` | Latest traded price |
| **Today's Bar** | Aggregated from intraday bars matching today's date | OHLCV for current session |
| **Delivery %** | `deliveryQty / volume × 100` | 20-day average |
| **VWAP** | `(H+L+C)/3 × volume / total_volume` | Last 5 days |
| **Derivatives** | Option chain via Dhan API (enriched after scoring for top stocks only) | OI, PCR, IV, change in OI |

**Collection is throttled** with a 150ms delay between API calls to avoid rate limits. Quote cache is refreshed every 20 stocks.

**Output:** `Dict[str, StockData]` — one `StockData` object per symbol.

### StockData Model (`models.py:52`)

Key fields used in scoring:
- `price`, `sector`, `avg_turnover_crore`, `avg_volume_lakhs`, `delivery_pct`
- `ohlc_daily`: `List[dict]` with keys `open, high, low, close, volume`, deliveryQty, turnover
- `vwap`, `open_interest`, `change_oi`, `pcr`, `iv`

---

## 2. Stock-Level Analysis Pipeline

**File:** `scoring/ai_scorer.py` — `AIScorer.analyze_stock()`

Each stock goes through this pipeline:

```
analyze_stock(stock, market_open)
    │
    ├── market_open = True  →  _analyze_live()    (runs on 15-min intraday data)
    └── market_open = False →  _run_pipeline()     (runs on daily OHLC data)
```

### Step 2.1: Liquidity Filter

**File:** `analysis/liquidity.py` — `LiquidityFilter.check()`

A stock is **rejected** if it fails any of these configurable thresholds:

| Threshold | Config Key | Default |
|---|---|---|
| Minimum price | `scanner.min_price` | ₹50 |
| Minimum avg turnover | `scanner.min_avg_turnover_crore` | ₹10 Cr |
| Minimum avg volume | `scanner.min_avg_volume_lakhs` | 3 Lakh |
| Minimum delivery % | `scanner.min_delivery_pct` | 20% |

If liquidity fails → stock is skipped (no score, no trade plan).

### Step 2.2: Module Analysis (8 Modules)

Each module analyzes the `StockData` and stores results in `AnalysisResult`:

| # | Module | File | What it extracts |
|---|---|---|---|
| 1 | **MomentumAnalyzer** | `analysis/momentum.py` | RSI(14), ADX, MACD signal, trend strength |
| 2 | **PatternDetector** | `analysis/patterns.py` | Detects chart patterns (Cup & Handle, Flags, Wedges, NR7/NR4, Inside Bar, etc.) |
| 3 | **VolumeAnalyzer** | `analysis/volume.py` | Relative volume, delivery ratio, institutional accumulation/distribution |
| 4 | **DerivativesAnalyzer** | `analysis/derivatives.py` | OI change, PCR, IV, futures basis |
| 5 | **VolatilityAnalyzer** | `analysis/volatility.py` | ATR(14), ATR%, Bollinger Band width, squeeze detection |
| 6 | **RelativeStrengthAnalyzer** | `analysis/relative_strength.py` | 5-day and 20-day relative strength vs Nifty |
| 7 | **GapProbabilityAnalyzer** | `analysis/gap_probability.py` | Probability of gap-up/gap-down next session |
| 8 | **LiquidityFilter** | `analysis/liquidity.py` | Already checked above; also contributes to score |

### Step 2.3: Score Computation

**File:** `scoring/ai_scorer.py:182-203` — `_compute_scores()`

Eight component scores are computed, each normalized to a [0,1] range, then multiplied by a configurable weight:

```
final_score = Σ( min(raw[k] / max_possible[k], 1.0) × weight[k] )
```

#### Component 1: Trend Score (max raw: 25, weight: 20)

| Condition | Points |
|---|---|
| Close > EMA(20) | +4 |
| Close > EMA(50) | +4 |
| Close > EMA(200) | +4 |
| EMA(20) rising (current > previous) | +4 |
| EMA(50) rising | +4 |
| EMA(20) > EMA(50) | +3 |
| EMA(50) > EMA(200) | +2 |

Requires 50+ daily bars. Falls back to 5.0 if insufficient data. Capped at 25.

#### Component 2: Price Action Score (max raw: 30, weight: 15)

- **Base:** 3.0
- **Breakout Proximity:** `+5` if close is within 2% of 20-day high, `+3` if within 5%
- **Inside Bar:** `+3` if last bar's high < previous high AND low > previous low
- **Bollinger Squeeze:** `+4` if Bollinger Band width < 15
- **NR7:** `+3` if last bar is the narrowest range of the last 8 bars
- **Pattern Bonuses:**
  - `+4`: BULL_FLAG, ASCENDING_TRIANGLE, CUP_HANDLE, VCP, DOJI_NEAR_BREAKOUT
  - `+3`: BEAR_FLAG, DARVAS_BOX, TIGHT_CONSOLIDATION, ORB_SETUP, BULLISH_ENGULFING, MARUBOZU
  - `+2`: HH_HL, FALLING_WEDGE, RISING_WEDGE, INSIDE_BAR
  - `+1`: NR4, LH_LL, BEARISH_ENGULFING, DESCENDING_TRIANGLE, DOUBLE_INSIDE_BAR
- **Volume Bonus:** `+3` if rel_vol > 2.0, `+2` if > 1.5, `+1` if > 1.2

Capped at 30.

#### Component 3: Volume Score (max raw: 15, weight: 15)

| Relative Volume | Score |
|---|---|
| ≥ 3.0 | 15 |
| ≥ 2.0 | 12 |
| ≥ 1.5 | 9 |
| ≥ 1.2 | 6 |
| ≥ 0.8 | 3 |
| < 0.8 | 2 |

#### Component 4: Momentum Score (max raw: 17, weight: 15)

- **Base:** 2.0

**RSI Scoring:**

| RSI Range | Points |
|---|---|
| 55–65 | +7 |
| 50–55 or 65–70 | +5 |
| 45–50 | +3 |
| 70–75 | +2 |
| <45 or >75 | +1 |

**ADX Scoring:**

| ADX | Points |
|---|---|
| ≥ 28 | +5 |
| ≥ 22 | +4 |
| ≥ 18 | +3 |
| < 18 | +1 |

**MACD:** `+3` for bullish cross, `+1` for bearish cross. Capped at 17.

#### Component 5: Volatility Score (max raw: 10, weight: 10)

- **Base:** 2.0
- **ATR%:** `+3` if 1.5%–5%, `+2` if > 5%, `+1` if > 0.8%
- **Bollinger Squeeze:** `+3`
- **Expected Move > 1.5%:** `+2`

Capped at 10.

#### Component 6: Relative Strength Score (max raw: 10, weight: 10)

- **Base:** 1.0

| 20-day RS | Points | 5-day RS | Points |
|---|---|---|---|
| > 10 | +4 | > 5 | +3 |
| > 5 | +3 | > 2 | +2 |
| > 2 | +2 | > 0 | +1 |
| > 0 | +1 | — | — |

Capped at 10.

#### Component 7: Liquidity Score (max raw: 10, weight: 10)

- **Base:** 1.0

| Turnover (₹ Cr) | Points | Volume (Lakhs) | Points |
|---|---|---|---|
| ≥ 50 | +4 | ≥ 20 | +4 |
| ≥ 20 | +3 | ≥ 10 | +3 |
| ≥ 10 | +2 | ≥ 5 | +2 |
| ≥ 5 | +1 | ≥ 2 | +1 |

- **Price ≥ ₹100:** +1

Capped at 10.

#### Component 8: Market Context Score (max raw: 8, weight: 5)

- **Base:** 2.0
- Regime-specific bonuses (currently hardcoded to `"neutral"` — only base of 2.0 applies unless `_detect_market_regime()` is enhanced):
  - **Trending:** `+3` if ADX ≥ 22, `+2` if RSI ≥ 55
  - **Sideways:** `+3` if Bollinger squeeze, `+2` if NR7/NR4/TIGHT_CONSOLIDATION
  - **Weak:** `+3` if 20-day RS > 0, `+2` if 5-day RS > 2

Capped at 8.

#### Formula Summary

```
total_score = min( Σ(comp_scores), 100 )
```

Theoretical maximum: `20 + 15 + 15 + 15 + 10 + 10 + 10 + 5 = 100`

### Step 2.4: Direction & Confidence

**File:** `scoring/ai_scorer.py:411-440` — `_determine_direction()`

A point-based voting system tallies bullish vs bearish signals from all analysis results:

| Signal | Bull | Bear |
|---|---|---|
| RSI bullish/bearish signal | +2 | +2 |
| MACD bullish/bearish cross | +2 | +2 |
| EMA20 > EMA50 / EMA20 < EMA50 | +1 | +1 |
| Price > VWAP / Price < VWAP | +1 | +1 |
| Large bullish/bearish candle | +1 | +1 |
| Bullish patterns (Bull Flag, Asc Triangle, Cup & Handle, Bullish Engulfing etc.) | +2 | — |
| Bearish patterns (Bear Flag, Desc Triangle, Bearish Engulfing etc.) | — | +2 |
| RSI ≥ 60 / RSI ≤ 40 | +1 | +1 |
| Rel Vol > 1.5 | +1 (to leader) | +1 (to leader if bear leads) |

**Confidence calculation:**
```
confidence = abs(bull - bear) / max(bull + bear, 1) × 100
```

**Final assignment:**
- `bull > bear` → `BULLISH`, confidence = `min(90, raw_conf × 1.4 + 30)`
- `bear > bull` → `BEARISH`, confidence = `min(90, raw_conf × 1.4 + 30)`
- `bull == bear` → `NEUTRAL`, confidence = `max(20, raw_conf)`

### Step 2.5: Trade Plan Generation

**File:** `scoring/ai_scorer.py:442-493` — `_generate_trade_plan()`

Based on direction and ATR:

| Parameter | BULLISH | BEARISH | NEUTRAL |
|---|---|---|---|
| Entry | `close + ATR × 0.3` | `close - ATR × 0.3` | — |
| Stop Loss | `entry - ATR × 1.0` | `entry + ATR × 1.0` | `close - ATR × 1.0` |
| Target 1 | `entry + ATR × 2.0` | `entry - ATR × 2.0` | `close + ATR × 1.5` |
| Target 2 | `entry + ATR × 3.0` | `entry - ATR × 3.0` | `close + ATR × 2.5` |
| R:R | `abs(T1 - entry) / abs(entry - SL)` | same | same |
| Position Size | `max(1, int(500 / risk_per_share))` | same | same |

**Strategy Selection** (priority order):
| Condition | Strategy |
|---|---|
| ORB Setup / NR7 / NR4 / Inside Bar | `ORB` |
| Tight Consolidation / Bollinger Squeeze | `BREAKOUT` |
| Strong ADX | `TREND_FOLLOWING` |
| Bull Flag / Asc Triangle / Cup & Handle | `BREAKOUT` |
| Bear Flag / Desc Triangle | `BREAKDOWN` |
| Gap-up prob > 40% | `GAP_TRADE` |
| Fallback | `ORB` |

---

## 3. Live Market Mode (15-min Intraday)

**File:** `scoring/ai_scorer.py:100-129` — `_analyze_live()`

When the market is OPEN, the pipeline changes:

1. **Daily Momentum Pre-filter** (`_passes_daily_momentum`, line 84-98):
   - Requires 50+ daily bars
   - Trend score ≥ 8
   - RSI between 40 and 75
   - ADX ≥ 15
   - _Fails_ → stock is skipped

2. **15-min Data Check:** Requires 50+ bars of 15-min OHLC

3. **Pipeline on Intraday Data:** The standard `_run_pipeline()` is called with 15-min OHLC substituted as daily data, plus 5-min data emptied.

4. **Intraday Bonuses** (applied to total score):
   - `rel_vol > 1.0` → `VOLUME_EXPANSION_15MIN` pattern, **+5**
   - Fresh EMA(5) > EMA(20) crossover on 15-min → `EMA_CROSSOVER_15MIN`, **+10**
   - EMA alignment (EMA5 > EMA20 > EMA50) → **+5**

5. **Final Filter:** Rejected if direction is NEUTRAL or `total_score < score_threshold` (default: 55)

---

## 4. Shortlisting — Top 20 Selection

**File:** `scoring/ai_scorer.py:495-496` — `shortlist()`

```
shortlist(stocks)
    → sorted(stocks, key=lambda s: (s.total_score, s.confidence, s.risk_reward), reverse=True)
    → [:CONFIG.scanner.top_n]   (default: 20)
```

**Sorting priority (descending):**
1. `total_score` — higher is better
2. `confidence` — higher is better (tiebreaker)
3. `risk_reward` — higher is better (second tiebreaker)

**Global threshold:** Only stocks with `total_score ≥ 55` (`score_threshold`) survive to be considered for Top 20.

No sector or correlation de-duplication is performed — the Top 20 is purely the highest-scoring stocks.

---

## 5. Category Separation

**File:** `scoring/ai_scorer.py:498-512` — `get_categories()`

From the full scored list, stocks are split into categories:

| Category | Selection Criteria | Max Count | Sort Order |
|---|---|---|---|
| **Top Bullish** | `direction == BULLISH` | 10 | total_score descending |
| **Top Bearish** | `direction == BEARISH` | 10 | total_score descending |
| **High Volatility** | `atr > 0` | 10 | ATR% descending |
| **Breakout Watch** | `breakout_proximity ≤ 2` OR `bollinger_squeeze == True` OR `nr_detected == True` | 10 | total_score descending |
| **Mean Reversion** | `(BULLISH AND 45 ≤ rsi ≤ 50)` OR `(BEARISH AND 55 ≤ rsi ≤ 65)` | 10 | total_score descending |

---

## 6. Confidence Bands

**File:** `scoring/ai_scorer.py:514-519` — `get_confidence_band()`

| Score Range | Band |
|---|---|
| ≥ 85 | `*****` |
| ≥ 75 | `****` |
| ≥ 65 | `***` |
| ≥ 55 | `**` |
| < 55 | `Monitor` |

---

## 7. Option Chain Enrichment

**File:** `main.py:125-170` — `_enrich_top_with_option_chain()`

After shortlisting, the **Top 20** stocks get their option chain data fetched from Dhan API:

1. Get nearest expiry date
2. Fetch full option chain (all strikes, both CE and PE)
3. Calculate aggregate:
   - **Total OI** = `Σ(CE OI) + Σ(PE OI)`
   - **OI Change** = `Σ(CE change OI) + Σ(PE change OI)`
   - **PCR** = `Σ(PE OI) / max(Σ(CE OI), 1)`
   - **IV** = mean of all individual option IVs
4. Re-score the stock with updated derivatives data
5. Re-sort and re-categorize the Top 20

---

## 8. Report Generation

After scoring, shortlisting, and OC enrichment, reports are generated:

| Format | File | Generator Class |
|---|---|---|
| Excel (`.xlsx`) | `output/reports/scanner_report_{date}.xlsx` | `ExcelReportGenerator` |
| CSV (`.csv`) | `output/reports/scanner_report_{date}.csv` | `CSVReportGenerator` |
| JSON (`.json`) | `output/reports/scanner_report_{date}.json` | `JSONReportGenerator` |
| HTML (`.html`) | `output/reports/scanner_report_{date}.html` | `HTMLReportGenerator` |

---

## 9. Complete End-to-End Flow

```
 ┌──────────────────────────────────────────────────────────────┐
 │                    DataCollection Phase                       │
 │                                                               │
 │  For each of 219 NSE F&O symbols:                            │
 │    ├── Fetch 1yr daily OHLC                                   │
 │    ├── Fetch 20 days of 5-min intraday                        │
 │    ├── Fetch 5 days of 15-min intraday (if market open)       │
 │    └── Get live price & basic derivatives stats               │
 │                                                               │
 │  Output: Dict[symbol → StockData]                             │
 └──────────────────────┬───────────────────────────────────────┘
                        │
                        ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                  Scoring Pipeline (per stock)                 │
 │                                                               │
 │  Step 1: Liquidity Check                                      │
 │    Fail → skip stock                                          │
 │    Pass → continue                                            │
 │                                                               │
 │  Step 2: 8-Module Analysis                                    │
 │    ┌──────────────┐                                           │
 │    │  Momentum     │→ RSI, ADX, MACD                          │
 │    │  Patterns     │→ 23 chart patterns                       │
 │    │  Volume       │→ rel vol, delivery, accumulation         │
 │    │  Derivatives  │→ OI, PCR, IV                             │
 │    │  Volatility   │→ ATR, Bollinger bands, squeeze           │
 │    │  Rel Strength │→ 5d & 20d RS vs Nifty                    │
 │    │  Gap Prob     │→ gap prediction                          │
 │    │  Liquidity    │→ turnover, volume tiers                  │
 │    └──────────────┘                                           │
 │                                                               │
 │  Step 3: Compute 8 Component Scores                           │
 │    ┌──────────────────────┬──────┬───────────┐                │
 │    │ Component            │ Max  │ Weight    │                │
 │    ├──────────────────────┼──────┼───────────┤                │
 │    │ Trend                │ 25   │ 20.0      │                │
 │    │ Price Action         │ 30   │ 15.0      │                │
 │    │ Volume               │ 15   │ 15.0      │                │
 │    │ Momentum             │ 17   │ 15.0      │                │
 │    │ Volatility           │ 10   │ 10.0      │                │
 │    │ Relative Strength    │ 10   │ 10.0      │                │
 │    │ Liquidity            │ 10   │ 10.0      │                │
 │    │ Market Context       │ 8    │ 5.0       │                │
 │    └──────────────────────┴──────┴───────────┘                │
 │                                                               │
 │  Step 4: total_score = Σ(normalized_raw × weight)             │
 │         Clamped to [0, 100]                                    │
 │                                                               │
 │  Step 5: Determine Direction & Confidence                     │
 │    Vote-based: bull vs bear signals                           │
 │    conf = |bull-bear| / (bull+bear) × 100, then scaled        │
 │                                                               │
 │  Step 6: Generate Trade Plan                                  │
 │    Entry, SL, Targets, Position Size, Strategy                │
 │                                                               │
 │  Output: AnalysisResult + TradePlan per stock                 │
 └──────────────────────┬───────────────────────────────────────┘
                        │
                        ▼
 ┌──────────────────────────────────────────────────────────────┐
 │              Shortlisting & Categorization                    │
 │                                                               │
 │  Step 1: shortlist(scored_stocks)                             │
 │    Sort by (total_score DESC, confidence DESC, R:R DESC)      │
 │    Take top 20                                                │
 │                                                               │
 │  Step 2: Option Chain Enrichment for Top 20                   │
 │    Fetch real OI, PCR, IV from API                            │
 │    Re-score with enriched data                                │
 │    Re-sort and re-categorize Top 20                           │
 │                                                               │
 │  Step 3: Category Separation                                  │
 │    Top 20 | Top Bullish(10) | Top Bearish(10)                 │
 │    High Volatility(10) | Breakout Watch(10)                   │
 │    Mean Reversion(10)                                         │
 │                                                               │
 │  Step 4: Confidence Band Assignment                           │
 │    ≥ 85 → *****  |  ≥ 75 → ****  |  ≥ 65 → ***               │
 │    ≥ 55 → **     |  < 55 → Monitor                            │
 └──────────────────────┬───────────────────────────────────────┘
                        │
                        ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                   Report Generation                           │
 │                                                               │
 │  ├── Excel (.xlsx)                                            │
 │  ├── CSV (.csv)                                               │
 │  ├── JSON (.json)                                             │
 │  ├── HTML (.html)                                             │
 │  └── Console Printout (terminal)                              │
 │                                                               │
 │  Alerts: Telegram (report + HTML file) + Email                │
 └──────────────────────────────────────────────────────────────┘
```

---

## Key Configuration Parameters

**File:** `config/settings.py`

| Parameter | Default | Description |
|---|---|---|
| `scanner.score_threshold` | 55.0 | Minimum total score to appear in Top 20 |
| `scanner.top_n` | 20 | Number of stocks in the shortlist |
| `scanner.min_price` | 50.0 | Minimum stock price to pass liquidity |
| `scanner.min_avg_turnover_crore` | 10.0 | Minimum avg daily turnover (₹ Cr) |
| `scanner.min_avg_volume_lakhs` | 3.0 | Minimum avg daily volume (Lakh) |
| `scanner.min_delivery_pct` | 20.0 | Minimum delivery percentage |
| `scanner.max_risk_per_trade` | 500.0 | Max ₹ risk per trade for position sizing |
| `weights.trend` | 20.0 | Trend score weight |
| `weights.price_action` | 15.0 | Price action score weight |
| `weights.volume` | 15.0 | Volume score weight |
| `weights.momentum` | 15.0 | Momentum score weight |
| `weights.volatility` | 10.0 | Volatility score weight |
| `weights.relative_strength` | 10.0 | Relative strength score weight |
| `weights.liquidity` | 10.0 | Liquidity score weight |
| `weights.market_context` | 5.0 | Market context score weight |

---

## Summary

1. **219 stocks** enter → ~207 pass liquidity check
2. Each stock gets **8 component scores** (trend, price action, volume, momentum, volatility, relative strength, liquidity, market context)
3. Component scores are normalized to [0,1], weighted, and summed → **total_score [0–100]**
4. Direction is determined via **bull vs bear vote tally**
5. Stocks are **sorted by total_score → confidence → risk_reward**
6. **Top 20** survive shortlisting
7. Option chain data is fetched for the Top 20 → **re-scored** for final ranking
8. Stocks are split into **6 category views** (Overall, Bullish, Bearish, High Vol, Breakout Watch, Mean Reversion)
9. Reports are generated in **4 formats** (Excel, CSV, JSON, HTML) and dispatched via **Telegram + Email**
