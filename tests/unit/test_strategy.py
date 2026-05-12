import pandas as pd
from unittest.mock import MagicMock
from src.engine.application.strategy import HybridStrategy

def test_hold_on_low_confidence():
    settings = MagicMock()
    settings.CONFIDENCE_THRESHOLD = 0.6
    settings.RSI_BUY_LIMIT = 70
    settings.TREND_FILTER = True

    strategy = HybridStrategy(settings)
    df = pd.DataFrame({
        'RSI': [0.3, 0.3],
        'EMA_DIST_50': [0.1, 0.1],
        'MACD_HIST': [-0.1, 0.1],
        'close': [100, 100]
    })
    signal, _ = strategy.get_signal(df, ai_confidence=0.2)
    assert signal is None, "Must be HOLD when AI confidence below threshold"

def test_buy_signal_when_conditions_met():
    settings = MagicMock()
    settings.CONFIDENCE_THRESHOLD = 0.5
    settings.RSI_BUY_LIMIT = 70
    settings.TREND_FILTER = True

    strategy = HybridStrategy(settings)
    df = pd.DataFrame({
        'RSI': [0.6, 0.6],
        'EMA_DIST_50': [0.1, 0.1],
        'MACD_HIST': [0.1, 0.2],
        'close': [100, 101]
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.7)
    assert signal == "BUY"
    assert meta['reason'] is not None
