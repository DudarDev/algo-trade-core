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
