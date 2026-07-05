import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Direction, PatternType, StrategyType, StockData, AnalysisResult, ScoredStock, ScannerOutput


def test_direction_enum():
    assert Direction.BULLISH.value == "Bullish"
    assert Direction.BEARISH.value == "Bearish"
    assert Direction.NEUTRAL.value == "Neutral"


def test_pattern_type_enum():
    assert PatternType.NR7.value == "NR7"
    assert PatternType.BULL_FLAG.value == "Bull Flag"


def test_stock_data_defaults():
    sd = StockData(symbol="RELIANCE")
    assert sd.symbol == "RELIANCE"
    assert sd.sector == ""
    assert sd.price == 0.0


def test_analysis_result_defaults():
    ar = AnalysisResult(symbol="RELIANCE")
    assert ar.symbol == "RELIANCE"
    assert ar.rsi == 50.0
    assert ar.direction == Direction.NEUTRAL


def test_scored_stock():
    ss = ScoredStock(
        symbol="RELIANCE", total_score=85.0, confidence=90.0,
        direction=Direction.BULLISH, entry_price=2500.0,
        stop_loss=2450.0, target_1=2600.0, target_2=2700.0,
        atr=25.0, volume_ratio=2.5, rsi=65.0, adx=30.0,
        pcr=1.2, oi_change=50000, iv=25.0,
    )
    assert ss.symbol == "RELIANCE"
    assert ss.total_score == 85.0
    assert ss.direction == Direction.BULLISH


def test_scanner_output():
    out = ScannerOutput()
    assert out.total_stocks_analyzed == 0
    assert out.stocks_shortlisted == 0
    assert out.top_stocks == []
