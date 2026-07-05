# Scoring Methodology

## Overview

Every NSE F&O stock (219 symbols) is scored on **8 independent components**. Each component is evaluated against graduated thresholds (not binary pass/fail), normalized, then weighted to produce a final score from **0–100**. No stock is ever rejected — every stock receives a score and appears in the report.

---

## 8 Scoring Components

### 1. Trend (weight: 20, max raw: 25)
Measures position relative to key EMAs and slope.

| Condition | Points |
|---|---|
| Price > EMA20 | 4 |
| Price > EMA50 | 4 |
| Price > EMA200 | 4 |
| EMA20 rising | 4 |
| EMA50 rising | 4 |
| EMA20 > EMA50 | 3 |
| EMA50 > EMA200 | 2 |

Capped at 25 raw (20 weighted).

### 2. Price Action (weight: 15, max raw: 30)
Breakout proximity, consolidation patterns, candle patterns, and relative volume.

| Condition | Points |
|---|---|
| Within 2% of 20-day high | 5 |
| Within 5% of 20-day high | 3 |
| Inside Bar (narrowing range) | 3 |
| Bollinger squeeze (BB width < 15%) | 4 |
| NR7 detected | 3 |
| Bull Flag / Cup & Handle / Asc Triangle / VCP / Doji@BO | 4 each |
| Bear Flag / Darvas Box / Tight Consolidation / ORB Setup / Bull Engulfing / Marubozu / HH-HL | 3 each |
| NR7 / Falling Wedge / Rising Wedge / Inside Bar | 2 each |
| NR4 / LH-LL / Bear Engulfing / Desc Triangle / Double Inside Bar | 1 each |
| Relative volume > 2.0 | +3 |
| Relative volume > 1.5 | +2 |
| Relative volume > 1.2 | +1 |

Base: 3. Capped at 30 raw (15 weighted).

### 3. Volume (weight: 15, max raw: 15)
Relative volume vs 20-day average.

| Relative Volume | Points |
|---|---|
| ≥ 3.0 | 15 |
| ≥ 2.0 | 12 |
| ≥ 1.5 | 9 |
| ≥ 1.2 | 6 |
| ≥ 0.8 | 3 |
| < 0.8 | 2 |

### 4. Momentum (weight: 15, max raw: 17)
RSI zone, ADX strength, MACD crossover.

| Condition | Points |
|---|---|
| RSI 55–65 | +7 |
| RSI 65–70 or 50–55 | +5 |
| RSI 45–50 | +3 |
| RSI 70–75 | +2 |
| RSI <45 or >75 | +1 |
| ADX ≥ 28 | +5 |
| ADX 22–28 | +4 |
| ADX 18–22 | +3 |
| ADX < 18 | +1 |
| MACD bullish cross | +3 |
| MACD bearish cross | +1 |

Base: 2. **RSI** uses Wilder's smoothing (14-period). **ADX** uses Wilder's smoothing with proper +DM/-DM comparison. Capped at 17 raw (15 weighted).

### 5. Volatility (weight: 10, max raw: 10)
ATR% range, Bollinger squeeze, expected move.

| Condition | Points |
|---|---|
| ATR% 1.5–5% | +3 |
| ATR% > 5% | +2 |
| ATR% 0.8–1.5% | +1 |
| Bollinger squeeze | +3 |
| Expected move > 1.5% | +2 |

Base: 2. **ATR** uses Wilder's smoothing (14-period). Capped at 10 raw (10 weighted).

### 6. Relative Strength (weight: 10, max raw: 10)
20-day and 5-day outperformance vs Nifty.

| Condition | Points |
|---|---|
| RS20 > 10% | +4 |
| RS20 > 5% | +3 |
| RS20 > 2% | +2 |
| RS20 > 0% | +1 |
| RS5 > 5% | +3 |
| RS5 > 2% | +2 |
| RS5 > 0% | +1 |

Base: 1. Capped at 10 raw (10 weighted). *(Note: currently Nifty data is a placeholder, so this component uses raw stock return only.)*

### 7. Liquidity (weight: 10, max raw: 10)
Turnover and volume tiers.

| Avg Turnover (₹cr) | Points | Avg Vol (lakhs) | Points |
|---|---|---|---|
| ≥ 50 | +4 | ≥ 20 | +4 |
| ≥ 20 | +3 | ≥ 10 | +3 |
| ≥ 10 | +2 | ≥ 5 | +2 |
| ≥ 5 | +1 | ≥ 2 | +1 |

Price ≥ ₹100: +1. Base: 1. Capped at 10 raw (10 weighted).

### 8. Market Context (weight: 5, max raw: 8)
Regime-aware scoring (currently all stocks treated as neutral).

| Condition (Neutral) | Points |
|---|---|
| Base | 2.0 |

Capped at 8 raw (5 weighted).

---

## Normalization & Weighting

Each component is independently normalized before weighting:

```
normalized = min(raw_score / max_raw, 1.0)
weighted_contribution = normalized * weight
```

Each component's max raw caps the maximum possible raw points per component. The ratio `raw / max_raw` is capped at 1.0, so a component can never exceed its allocated weight. This prevents any single area from dominating.

| Component | Max Raw | Weight |
|---|---|---|
| Trend | 25 | 20 |
| Price Action | 30 | 15 |
| Volume | 15 | 15 |
| Momentum | 17 | 15 |
| Volatility | 10 | 10 |
| Relative Strength | 10 | 10 |
| Liquidity | 10 | 10 |
| Market Context | 8 | 5 |
| **Total** | **125** | **100** |

Final score = sum of all weighted contributions, clamped to **[0, 100]**.

---

## Confidence Bands

The final score is mapped to a confidence band (displayed as ASCII stars for Windows compatibility):

| Score Range | Band | Label |
|---|---|---|
| ≥ 85 | `*****` | Very Strong |
| 75–84 | `****` | Strong |
| 65–74 | `***` | Moderate |
| 55–64 | `**` | Watch |
| < 55 | `Monitor` | Monitor |

---

## Direction & Confidence %

Direction (Bullish/Bearish/Neutral) is determined separately from scoring:

| Signal | Bullish Votes | Bearish Votes |
|---|---|---|
| RSI 55–75 | +2 | — |
| RSI 25–45 | — | +2 |
| MACD bullish cross | +2 | — |
| MACD bearish cross | — | +2 |
| EMA20 > EMA50 | +1 | — |
| EMA20 < EMA50 | — | +1 |
| Price > VWAP | +1 | — |
| Price < VWAP | — | +1 |
| Large bullish candle | +1 | — |
| Large bearish candle | — | +1 |
| Bull Flag / Asc Triangle / Cup / Bull Eng | +2 | — |
| Bear Flag / Desc Triangle / Bear Eng | — | +2 |
| RSI ≥ 60 | +1 | — |
| RSI ≤ 40 | — | +1 |
| Rel Vol > 1.5 (leans stronger side) | +1 | +1 |

```
total = max(bull + bear, 1)
raw_confidence = abs(bull - bear) / total * 100
confidence = min(90, raw_confidence * 1.4 + 30)
```

Confidence is a vote-based measure of directional agreement, not a predictor of magnitude. It indicates how many independent indicators align in the same direction.

---

## Top 20 Selection

The top 20 overall stocks are selected by sorting all scored stocks by:

```
primary: total_score (descending)
secondary: confidence (descending)
tertiary: risk_reward_ratio (descending)
```

## Category Lists

Beyond the top 20, six category lists are generated:

| Category | Selection | Size |
|---|---|---|
| Top 20 Overall | Highest total_score | 20 |
| Top Bullish | Highest-scoring bullish stocks | 10 |
| Top Bearish | Highest-scoring bearish stocks | 10 |
| Top High Volatility | Highest ATR% (stocks with atr > 0) | 10 |
| Top Breakout Watch | Within 2% of 20d high, or squeeze/NR | 10 |
| Top Mean Reversion | Bullish with RSI 45–50, or Bearish with RSI 55–65 | 10 |

---

## Trade Plan Generation

Each scored stock gets an actionable trade plan using CMP and ATR:

| Level | Bullish | Bearish |
|---|---|---|
| **Entry Trigger** | Buy Above = CMP + 0.3×ATR | Sell Below = CMP − 0.3×ATR |
| **Stop Loss** | CMP − 1.5×ATR | CMP + 1.5×ATR |
| **Target 1** | CMP + 2.0×ATR | CMP − 2.0×ATR |
| **Target 2** | CMP + 3.0×ATR | CMP − 3.0×ATR |
| **Risk:Reward** | (T1 − Entry) / (Entry − SL) | (Entry − T1) / (SL − Entry) |
| **Position Size** | floor(₹500 / risk) | floor(₹500 / risk) |
| **Breakout Level** | CMP + 0.5×ATR | CMP − 0.5×ATR |

Strategy assignment is based on the dominant pattern or signal detected:
- ORB Setup / NR7/NR4 / Inside Bar → **Opening Range Breakout**
- Tight Consolidation / Bollinger Squeeze / Bull Flag / Asc Triangle / Cup & Handle → **Breakout**
- ADX strong → **Trend Following**
- Bear Flag / Desc Triangle → **Breakdown**
- Gap probability > 40% → **Gap Trade**

---

## Excel Report

Two sheets are generated:

**Full List** — All scored stocks (typically ~207) sorted by score descending, with columns: Rank, Symbol, CMP, Entry (trigger level), Score, Band, Conf%, Direction, SL, T1, T2, ATR, ATR%, Vol Ratio, RSI, ADX, PCR, OI Chg, IV, Sector, Strategy, Pattern, Extras (BB-SQZ/NR/BRK), R:R, Pos Size, Exp Move%, Catalyst, Selected (Yes/No with yellow highlight for top 20).

**Top Picks** — Top 20 only, same columns minus Selected.

Direction column is color-coded: green for Bullish, red for Bearish.

---

## Data Sources

All data comes from **Dhan API v2**:
- Historical daily OHLCV (1 year lookback, POST `/v2/charts/historical`)
- Intraday 5-min OHLCV (20 day lookback, POST `/v2/charts/intraday`)
- Instrument master CSV (symbol → numeric security ID mapping)
- Derivative data (OI, PCR, IV) is collected where available but currently limited

Non-trading days (zero volume / flat OHLC) are stripped from the end of daily data to ensure the latest bar reflects a real trading session.
