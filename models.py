from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from dataclasses_json import dataclass_json
from enum import Enum


class Direction(str, Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    NEUTRAL = "Neutral"


class PatternType(str, Enum):
    NR7 = "NR7"
    NR4 = "NR4"
    INSIDE_BAR = "Inside Bar"
    DOUBLE_INSIDE_BAR = "Double Inside Bar"
    BULL_FLAG = "Bull Flag"
    BEAR_FLAG = "Bear Flag"
    ASCENDING_TRIANGLE = "Ascending Triangle"
    DESCENDING_TRIANGLE = "Descending Triangle"
    CUP_HANDLE = "Cup & Handle"
    FALLING_WEDGE = "Falling Wedge"
    RISING_WEDGE = "Rising Wedge"
    DARVAS_BOX = "Darvas Box"
    VCP = "VCP"
    TIGHT_CONSOLIDATION = "Tight Consolidation"
    ORB_SETUP = "ORB Setup"
    HH_HL = "Higher High Higher Low"
    LH_LL = "Lower High Lower Low"
    BULLISH_ENGULFING = "Bullish Engulfing"
    BEARISH_ENGULFING = "Bearish Engulfing"
    MARUBOZU = "Marubozu"
    DOJI_NEAR_BREAKOUT = "Doji Near Breakout"


class StrategyType(str, Enum):
    ORB = "Opening Range Breakout"
    VWAP_PULLBACK = "VWAP Pullback"
    BREAKOUT = "Breakout"
    BREAKDOWN = "Breakdown"
    TREND_FOLLOWING = "Trend Following"
    GAP_TRADE = "Gap Trade"
    MEAN_REVERSION = "Mean Reversion"


@dataclass_json
@dataclass
class StockData:
    symbol: str
    sector: str = ""
    price: float = 0.0
    avg_turnover_crore: float = 0.0
    avg_volume_lakhs: float = 0.0
    delivery_pct: float = 0.0
    ohlc_daily: List[Dict[str, Any]] = field(default_factory=list)
    ohlc_5min: List[Dict[str, Any]] = field(default_factory=list)
    vwap: float = 0.0
    open_interest: int = 0
    change_oi: int = 0
    futures_data: Dict[str, Any] = field(default_factory=dict)
    option_chain: List[Dict[str, Any]] = field(default_factory=list)
    pcr: float = 0.0
    max_pain: float = 0.0
    iv: float = 0.0
    mwpl: float = 0.0
    corporate_actions: List[str] = field(default_factory=list)
    block_deals: List[Dict[str, Any]] = field(default_factory=list)
    bulk_deals: List[Dict[str, Any]] = field(default_factory=list)
    insider_trades: List[Dict[str, Any]] = field(default_factory=list)
    earnings_date: Optional[str] = None
    dividend_date: Optional[str] = None
    news_headlines: List[str] = field(default_factory=list)


@dataclass_json
@dataclass
class AnalysisResult:
    symbol: str
    passed_liquidity: bool = False
    passed_momentum: bool = False
    momentum_signals: Dict[str, bool] = field(default_factory=dict)
    patterns: List[PatternType] = field(default_factory=list)
    volume_signals: Dict[str, float] = field(default_factory=dict)
    derivatives_signals: Dict[str, Any] = field(default_factory=dict)
    volatility_metrics: Dict[str, float] = field(default_factory=dict)
    relative_strength: Dict[str, float] = field(default_factory=dict)
    gap_probability: Dict[str, float] = field(default_factory=dict)
    rsi: float = 50.0
    adx: float = 0.0
    macd_signal: str = "neutral"
    atr: float = 0.0
    atr_pct: float = 0.0
    direction: Direction = Direction.NEUTRAL
    confidence: float = 0.0
    total_score: float = 0.0


@dataclass_json
@dataclass
class TradePlan:
    symbol: str
    direction: Direction = Direction.NEUTRAL
    confidence_pct: float = 0.0
    entry_price: float = 0.0
    buy_above: float = 0.0
    sell_below: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    atr: float = 0.0
    expected_move_pct: float = 0.0
    risk_reward_ratio: float = 0.0
    recommended_position_size: int = 0
    best_strategy: StrategyType = StrategyType.ORB
    support: float = 0.0
    resistance: float = 0.0
    breakout_level: float = 0.0


@dataclass_json
@dataclass
class ScoredStock:
    symbol: str
    total_score: float
    confidence: float
    direction: Direction
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    atr: float
    volume_ratio: float
    rsi: float
    adx: float
    pcr: float
    oi_change: int
    iv: float
    sector: str = ""
    cmp: float = 0.0
    entry_trigger: float = 0.0
    catalyst: str = ""
    pattern_detected: str = ""
    expected_move_pct: float = 0.0
    risk_reward: float = 0.0
    position_size: int = 0
    strategy: str = ""
    breakout_proximity: float = 0.0
    bollinger_squeeze: bool = False
    nr_detected: bool = False
    chart_path: str = ""


@dataclass_json
@dataclass
class ScannerOutput:
    generated_at: str = ""
    total_stocks_analyzed: int = 0
    stocks_shortlisted: int = 0
    top_stocks: List[ScoredStock] = field(default_factory=list)
    market_summary: Dict[str, Any] = field(default_factory=dict)
    market_regime: str = "neutral"
    all_scored: List[ScoredStock] = field(default_factory=list)
    top_bullish: List[ScoredStock] = field(default_factory=list)
    top_bearish: List[ScoredStock] = field(default_factory=list)
    top_high_volatility: List[ScoredStock] = field(default_factory=list)
    top_breakout_watch: List[ScoredStock] = field(default_factory=list)
    top_mean_reversion: List[ScoredStock] = field(default_factory=list)
