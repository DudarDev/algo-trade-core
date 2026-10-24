import pytest
from src.engine.application.adaptive_risk_controller import (
    AdaptiveRiskController,
    AdaptiveRiskState,
    AdaptiveThresholds
)

def test_adaptive_risk_default_state():
    controller = AdaptiveRiskController(
        base_confidence=0.55,
        base_min_adx=25.0,
        base_risk_pct=0.02
    )
    state = controller.get_state()
    assert state.consecutive_losses == 0
    assert state.consecutive_wins == 0
    assert state.current_confidence_threshold == 0.55
    assert state.current_min_adx == 25.0
    assert state.current_risk_multiplier == 1.0
    assert state.status_message == "NORMAL"

def test_adaptive_risk_loss_streak_tightening():
    controller = AdaptiveRiskController(
        base_confidence=0.55,
        base_min_adx=25.0,
        base_risk_pct=0.02
    )

    # 1st loss:
    state1 = controller.record_trade_result(net_pnl=-10.0, target_label=0, balance_after_trade=990.0)
    assert state1.consecutive_losses == 1
    assert state1.current_confidence_threshold == 0.58  # 0.55 + 0.03
    assert state1.current_min_adx == 27.0              # 25.0 + 2.0
    assert controller.get_effective_risk_pct() < 0.02   # risk reduced

    # 2nd loss:
    state2 = controller.record_trade_result(net_pnl=-12.0, target_label=0, balance_after_trade=978.0)
    assert state2.consecutive_losses == 2
    assert state2.current_confidence_threshold == 0.61  # 0.55 + 0.06
    assert state2.current_min_adx == 29.0              # 25.0 + 4.0
    assert state2.status_message == "DEFENSIVE"

    # 3rd loss (max penalty bounds):
    state3 = controller.record_trade_result(net_pnl=-15.0, target_label=0, balance_after_trade=963.0)
    assert state3.consecutive_losses == 3
    assert state3.current_confidence_threshold == 0.63  # 0.55 + 0.08 capped
    assert state3.current_min_adx == 31.0
    assert state3.status_message == "HIGH_DEFENSE"

def test_adaptive_risk_recovery_on_wins():
    controller = AdaptiveRiskController(
        base_confidence=0.55,
        base_min_adx=25.0,
        base_risk_pct=0.02
    )

    # Create 2 losses
    controller.record_trade_result(net_pnl=-10.0, target_label=0, balance_after_trade=990.0)
    controller.record_trade_result(net_pnl=-10.0, target_label=0, balance_after_trade=980.0)
    assert controller.consecutive_losses == 2

    # Now 1 win breaks the loss streak immediately
    state_win1 = controller.record_trade_result(net_pnl=25.0, target_label=1, balance_after_trade=1005.0)
    assert state_win1.consecutive_losses == 0
    assert state_win1.consecutive_wins == 1
    # Thresholds normalize
    assert state_win1.current_confidence_threshold == 0.55
    assert state_win1.current_min_adx == 25.0

def test_adaptive_risk_initialize_from_history():
    controller = AdaptiveRiskController(
        base_confidence=0.55,
        base_min_adx=25.0,
        base_risk_pct=0.02
    )

    class DummyTrade:
        def __init__(self, pnl, target):
            self.pnl = pnl
            self.target_label = target

    # 3 recent losses
    trades = [
        DummyTrade(-5.0, 0),
        DummyTrade(-8.0, 0),
        DummyTrade(-10.0, 0)
    ]
    controller.initialize_from_history(trades, current_balance=950.0)
    state = controller.get_state()
    assert state.consecutive_losses == 3
    assert state.current_confidence_threshold == 0.63
    assert state.current_min_adx == 31.0

def test_circuit_breaker_daily_loss_limit():
    controller = AdaptiveRiskController(
        base_confidence=0.55,
        base_min_adx=25.0,
        base_risk_pct=0.02
    )
    controller.initialize_from_history([], current_balance=1000.0)
    assert controller.is_circuit_breaker_triggered() is False

    # 1st loss: -12 USDT (total -12 USDT, limit is -30 USDT)
    controller.record_trade_result(net_pnl=-12.0, target_label=0, balance_after_trade=988.0)
    assert controller.is_circuit_breaker_triggered() is False

    # 2nd loss: -10 USDT (total -22 USDT, limit is -30 USDT)
    controller.record_trade_result(net_pnl=-10.0, target_label=0, balance_after_trade=978.0)
    assert controller.is_circuit_breaker_triggered() is False

    # 3rd loss: -10 USDT (total -32 USDT <= -30 USDT) -> Circuit Breaker triggers!
    state = controller.record_trade_result(net_pnl=-10.0, target_label=0, balance_after_trade=968.0)
    assert controller.is_circuit_breaker_triggered() is True
    assert state.circuit_breaker_active is True
    assert state.daily_loss_usdt == -32.0

    # Reset circuit breaker
    controller.reset_circuit_breaker()
    assert controller.is_circuit_breaker_triggered() is False
    assert controller.get_state().circuit_breaker_active is False
