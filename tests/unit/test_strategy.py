import pytest
import pandas as pd
from unittest.mock import MagicMock
from src.engine.application.strategy import HybridStrategy, SignalAction, MarketRegime
from src.engine.application.adaptive_risk_controller import AdaptiveRiskController

@pytest.fixture
def base_settings():
    settings = MagicMock()
    settings.CONFIDENCE_THRESHOLD = 0.55
    settings.RSI_BUY_LIMIT = 70
    settings.TREND_FILTER = True
    settings.min_adx_trend = 25.0
    settings.min_atr_pct = 0.001
    return settings

def test_hold_on_low_confidence(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.5, 0.5],
        'EMA_DIST_50': [0.01, 0.01],
        'MACD_HIST': [0.1, 0.1],
        'close': [100.0, 100.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.35, 0.35]
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.30)
    assert signal in [SignalAction.HOLD, None]
    assert "Insufficient confidence" in meta.reason

def test_buy_signal_when_conditions_met(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.55, 0.55],
        'EMA_DIST_50': [0.01, 0.01],  # BULL
        'MACD_HIST': [0.1, 0.2],
        'close': [100.0, 101.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.35, 0.35]
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.70)
    assert signal == SignalAction.BUY
    assert meta.regime == MarketRegime.BULL

def test_choppy_market_adx_filter(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.50, 0.50],
        'EMA_DIST_50': [0.001, 0.001],
        'MACD_HIST': [0.1, 0.1],
        'close': [100.0, 100.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.15, 0.15]  # ADX = 15 < 25
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.80)
    assert signal == SignalAction.HOLD
    assert meta.regime == MarketRegime.CHOP
    assert "CHOPPY" in meta.reason

def test_overbought_rsi_filter(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.75, 0.75],  # RSI = 75 >= 70
        'EMA_DIST_50': [0.02, 0.02],
        'MACD_HIST': [0.1, 0.1],
        'close': [100.0, 100.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.35, 0.35]
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.85)
    assert signal == SignalAction.HOLD
    assert "RSI Overbought" in meta.reason

def test_bear_market_falling_macd_filter(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.45, 0.45],
        'EMA_DIST_50': [-0.02, -0.02],  # BEAR
        'MACD_HIST': [-0.05, -0.10],   # Negative MACD
        'close': [100.0, 98.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.30, 0.30]
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.85)
    assert signal == SignalAction.HOLD
    assert "Bearish MACD in Bear Market" in meta.reason

def test_already_in_position_filter(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.5, 0.5],
        'EMA_DIST_50': [0.02, 0.02],
        'MACD_HIST': [0.1, 0.1],
        'close': [100.0, 101.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.30, 0.30]
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.75, in_position=True)
    assert signal is None
    assert "Already in position" in meta.reason

def test_adaptive_risk_tightening_strategy(base_settings):
    risk_controller = AdaptiveRiskController(
        base_confidence=0.55,
        base_min_adx=25.0
    )
    # Simulate 2 losses
    risk_controller.record_trade_result(-10.0, 0, 990.0)
    risk_controller.record_trade_result(-10.0, 0, 980.0)

    # Dynamic confidence threshold rose from 0.55 to 0.61!
    strategy = HybridStrategy(base_settings, risk_controller=risk_controller)
    df = pd.DataFrame({
        'RSI': [0.5, 0.5],
        'EMA_DIST_50': [0.01, 0.01],
        'MACD_HIST': [0.1, 0.1],
        'close': [100.0, 101.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.30, 0.30]
    })
    
    # 0.58 would have been BUY under base 0.55, but with adaptive risk it is rejected (0.58 < 0.61)
    signal, meta = strategy.get_signal(df, ai_confidence=0.58)
    assert signal == SignalAction.HOLD
    assert "Insufficient confidence" in meta.reason

def test_higher_timeframe_downtrend_blocks_entry(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.55, 0.55],
        'EMA_DIST_50': [0.01, 0.01],
        'MACD_HIST': [0.1, 0.2],
        'close': [100.0, 101.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.35, 0.35]
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.80, htf_trend="BEARISH")
    assert signal == SignalAction.HOLD
    assert "Higher TF (1h) Downtrend" in meta.reason

def test_btc_market_pulse_bearish_blocks_entry(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.55, 0.55],
        'EMA_DIST_50': [0.01, 0.01],
        'MACD_HIST': [0.1, 0.2],
        'close': [100.0, 101.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.35, 0.35]
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.80, btc_pulse="BEARISH_DUMP")
    assert signal == SignalAction.HOLD
    assert "BTC Market Pulse Bearish" in meta.reason

def test_vsa_low_volume_blocks_entry(base_settings):
    strategy = HybridStrategy(base_settings)
    df = pd.DataFrame({
        'RSI': [0.55, 0.55],
        'EMA_DIST_50': [0.01, 0.01],
        'MACD_HIST': [0.1, 0.2],
        'close': [100.0, 101.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.35, 0.35],
        'VOL_SPIKE': [0.50, 0.50]  # Low volume breakout < 0.85
    })
    signal, meta = strategy.get_signal(df, ai_confidence=0.80)
    assert signal == SignalAction.HOLD
    assert "Low Volume Breakout" in meta.reason

def test_ensemble_factor_consensus_and_divergence(base_settings):
    strategy = HybridStrategy(base_settings)
    # When technical factors are aligned with high confidence:
    df_bull = pd.DataFrame({
        'RSI': [0.52, 0.52],
        'EMA_DIST_50': [0.015, 0.015],
        'MACD_HIST': [0.15, 0.20],
        'close': [100.0, 102.0],
        'ATR_PCT': [0.02, 0.02],
        'ADX': [0.35, 0.35],
        'VOL_SPIKE': [1.30, 1.30],
        'BUY_PRESSURE': [0.65, 0.65]
    })
    sig, meta = strategy.get_signal(df_bull, ai_confidence=0.75)
    assert sig == SignalAction.BUY
    assert meta.quant_score >= 0.70
    assert meta.ensemble_conf >= 0.70
    assert "Ens=" in meta.reason
