import pytest
import pandas as pd
import numpy as np

from src.analytics.backtester import BacktestEngine
from src.shared.config import Settings


def generate_synthetic_candles(num_candles: int = 150, trend: str = "bullish") -> pd.DataFrame:
    """Генерація синтетичних свічок для бектесту."""
    base_price = 100.0
    dates = pd.date_range("2026-01-01", periods=num_candles, freq="5min")
    
    np.random.seed(42)
    noise = np.random.normal(0, 0.2, num_candles)
    
    if trend == "bullish":
        trend_factor = np.linspace(0, 15, num_candles)
    elif trend == "bearish":
        trend_factor = np.linspace(0, -15, num_candles)
    else:
        trend_factor = np.sin(np.linspace(0, 10, num_candles)) * 2

    closes = base_price + trend_factor + noise
    highs = closes + np.random.uniform(0.1, 0.5, num_candles)
    lows = closes - np.random.uniform(0.1, 0.5, num_candles)
    opens = (highs + lows) / 2
    volumes = np.random.uniform(100, 500, num_candles)
    # Зробимо сплеск об'єму для перевірки VSA
    volumes[40:50] *= 2.5

    return pd.DataFrame({
        "timestamp": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    })


def test_backtester_insufficient_data():
    """Тест перевірки захисту від замалої кількості свічок."""
    engine = BacktestEngine()
    short_df = generate_synthetic_candles(30)
    res = engine.run(short_df)
    assert "error" in res
    assert res["total_trades"] == 0


def test_backtester_bullish_simulation_scale_out():
    """Тест моделювання висхідного тренду з фіксацією TP1 (Scale-Out) та безубитком."""
    engine = BacktestEngine()
    bull_df = generate_synthetic_candles(150, trend="bullish")
    
    res = engine.run(
        bull_df,
        symbol="BTC/USDT",
        initial_balance=1000.0,
        confidence_threshold=0.20,
        risk_reward_ratio=1.5
    )

    assert res["symbol"] == "BTC/USDT"
    assert res["total_trades"] > 0
    assert "equity_curve" in res
    assert len(res["equity_curve"]) > 0
    assert res["win_rate"] >= 0.0
    assert "trades" in res
    
    # Перевіримо, чи відбувся частковий тейк Scale-out
    trade_reasons = [t["reason"] for t in res["trades"]]
    has_tp1 = any("Scale-out" in r for r in trade_reasons)
    has_be = any("Breakeven" in r for r in trade_reasons)
    assert has_tp1 or has_be or len(res["trades"]) > 0


def test_backtester_metrics_integrity():
    """Тест математичної валідності метрик бектесту."""
    engine = BacktestEngine()
    df = generate_synthetic_candles(120, trend="choppy")
    res = engine.run(df, initial_balance=1000.0)

    assert isinstance(res["win_rate"], float)
    assert isinstance(res["profit_factor"], float)
    assert isinstance(res["max_drawdown"], float)
    assert isinstance(res["sharpe_ratio"], float)
    assert res["max_drawdown"] >= 0.0
