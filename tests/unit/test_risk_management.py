from src.engine.application.risk_management import RiskManager, RiskConfig

def test_evaluate_trade_basic():
    config = RiskConfig(
        atr_multiplier=2.0,
        min_risk_reward=1.5,
        max_risk_pct=2.0
    )
    risk_mgr = RiskManager(config)
    trade = risk_mgr.evaluate_trade(entry_price=100.0, atr=1.0, capital=1000.0)
    assert trade is not None
    assert trade.stop_loss == 98.0
    assert abs(trade.take_profit - 103.2) < 0.001
    assert trade.risk_reward_ratio == 1.6


def test_evaluate_trade_mean_reversion():
    config = RiskConfig(
        atr_multiplier=2.0,
        min_risk_reward=1.5,
        max_risk_pct=2.0
    )
    risk_mgr = RiskManager(config)
    trade = risk_mgr.evaluate_trade(entry_price=100.0, atr=1.0, capital=1000.0, is_mean_reversion=True)
    assert trade is not None
    # For mean reversion, stop loss is tighter (min(atr*1.0, entry*0.012) -> 1.0)
    assert trade.stop_loss == 99.0
    # Take profit is fast target (1.2x ATR or 1.0% + fee)
    assert trade.take_profit >= 101.2
    # Position size is capped safely for counter-trend protection
    assert trade.position_size_usdt <= 45.0


def test_evaluate_trade_dynamic_take_profit_target():
    """Тест 3: Динамічний Take Profit точно встановлює рівень виходу за target_tp_pct"""
    config = RiskConfig(
        atr_multiplier=2.0,
        min_risk_reward=1.5,
        max_risk_pct=2.0
    )
    risk_mgr = RiskManager(config)
    # Entry 100.0, target_tp_pct = 0.025 (+2.5% до EMA 20)
    trade = risk_mgr.evaluate_trade(
        entry_price=100.0,
        atr=1.0,
        capital=1000.0,
        is_mean_reversion=True,
        target_tp_pct=0.025
    )
    assert trade is not None
    assert trade.take_profit == 102.5
    assert trade.stop_loss == 99.0
    assert trade.risk_reward_ratio == 2.5
