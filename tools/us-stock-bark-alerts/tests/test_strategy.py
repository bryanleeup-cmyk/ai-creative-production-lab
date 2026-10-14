import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest
from strategy import check_signal, DEFENSIVE, TICKERS

def series(prices):
    return pd.Series(prices, index=pd.bdate_range("2024-01-01", periods=len(prices)))

def test_tesla_buy():
    signal = check_signal("TSLA", series([100]*30 + [112]))
    assert signal and signal.direction == "BUY"
    assert "ORLY" in signal.body

def test_tesla_sell():
    signal = check_signal("TSLA", series([100]*30 + [88]))
    assert signal and signal.direction == "SELL"

def test_growth_buy():
    signal = check_signal("AAPL", series([100]*225 + [103]))
    assert signal and signal.direction == "BUY"
    for ticker in DEFENSIVE:
        assert ticker in signal.body

def test_growth_sell():
    signal = check_signal("NVDA", series([100]*225 + [97]))
    assert signal and signal.direction == "SELL"

def test_no_repeat():
    assert check_signal("SPY", series([100]*225 + [103, 104])) is None

def test_within_band():
    assert check_signal("QQQ", series([100]*225 + [100.5])) is None

def test_insufficient_history():
    with pytest.raises(ValueError):
        check_signal("AAPL", series([100]*225))
    with pytest.raises(ValueError):
        check_signal("TSLA", series([100]*30))

def test_ticker_scope():
    assert TICKERS == ("TSLA","AAPL","SPY","QQQ","NVDA")

def test_dedup_key():
    assert check_signal("AAPL", series([100]*225+[103])).key.endswith(":AAPL:BUY")
