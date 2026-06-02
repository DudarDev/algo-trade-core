import pandas as pd
from unittest.mock import MagicMock
from src.engine.application.strategy import HybridStrategy, SignalAction

def test_hold_on_low_confidence():
    # Налаштовуємо мок-конфіг
    settings = MagicMock()
    settings.CONFIDENCE_THRESHOLD = 0.6
    settings.RSI_BUY_LIMIT = 70
    settings.TREND_FILTER = True
    settings.min_adx_trend = 25.0

    strategy = HybridStrategy(settings)
    
    # Ідеально валідний DataFrame для флету/низької впевненості
    df = pd.DataFrame({
        'RSI': [0.3, 0.3],
        'EMA_DIST_50': [0.1, 0.1],
        'MACD_HIST': [-0.1, 0.1],
        'close': [100, 100],
        'ATR_PCT': [0.02, 0.02], # Достатня волатильність
        'ADX': [0.35, 0.35]      # Достатній тренд
    })
    
    # Передаємо низьку впевненість ШІ (0.2 < 0.6)
    signal, meta = strategy.get_signal(df, ai_confidence=0.2)
    
    # Має повернути HOLD (або None) через низьку впевненість
    assert signal in [SignalAction.HOLD, None], "Must be HOLD when AI confidence below threshold"


def test_buy_signal_when_conditions_met():
    # Налаштовуємо мок-конфіг для успішного входу
    settings = MagicMock()
    settings.CONFIDENCE_THRESHOLD = 0.5
    settings.RSI_BUY_LIMIT = 70
    settings.TREND_FILTER = True
    settings.min_adx_trend = 25.0 
    
    strategy = HybridStrategy(settings)
    
    # Ідеально валідний DataFrame для бичого тренду
    df = pd.DataFrame({
        'RSI': [0.6, 0.6],          # RSI < 70 (не перегрітий)
        'EMA_DIST_50': [0.1, 0.1],  # Бичий тренд (> 0.005)
        'MACD_HIST': [0.1, 0.2],
        'close': [100, 101],
        'ATR_PCT': [0.02, 0.02],    # Волатильність > 0.015
        'ADX': [0.35, 0.35]         # Сильний тренд (ADX 35 > 25)
    })
    
    # Передаємо високу впевненість ШІ (0.7 > 0.5)
    signal, meta = strategy.get_signal(df, ai_confidence=0.7)
    
    # Має повернути BUY
    assert signal == SignalAction.BUY, f"Expected BUY, got {signal}. Reason: {meta.reason}"