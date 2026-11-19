# tests/unit/test_delta_neutral.py
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch

from src.shared.config import Settings
from src.engine.domain.models import (
    DeltaNeutralPosition,
    DeltaNeutralMode,
    DeltaNeutralStatus,
    TradeSide
)
from src.engine.application.delta_neutral_trader import DeltaNeutralTrader


class MockSettings:
    SPOT_MAKER_FEE_PCT = 0.0002   # 0.02%
    PERP_MAKER_FEE_PCT = 0.0002   # 0.02%
    SPOT_TAKER_FEE_PCT = 0.0010   # 0.10%
    PERP_TAKER_FEE_PCT = 0.0005   # 0.05%
    MAX_FEE_BREAKEVEN_DAYS = 2.5
    MIN_FUNDING_APY_HURDLE = 10.0
    MAX_ENTRY_BASIS_PCT = 0.80
    MIN_ENTRY_BASIS_PCT = -0.05
    FORCE_FUNDING_ACCRUE = True



@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_active_delta_neutral_positions.return_value = []
    repo.load_balance.return_value = 1000.0
    return repo


@pytest.fixture
def mock_notifier():
    notifier = MagicMock()
    return notifier


@pytest.fixture
def trader(mock_repo, mock_notifier):
    settings = MockSettings()
    return DeltaNeutralTrader(
        settings=settings,
        repo=mock_repo,
        notifier=mock_notifier,
        is_paper=True
    )


def test_calculate_breakeven_days_maker(trader):
    # 8h rate = 0.0002 (0.02% per 8h = 0.06% per day)
    # Maker roundtrip fee = (0.0002 + 0.0002) * 2 * 100 = 0.08%
    # Breakeven days = 0.08 / 0.06 = 1.33 days
    be_days, fee_pct = trader.calculate_breakeven_days(0.0002, is_maker=True)
    assert be_days == 1.33
    assert fee_pct == 0.08


def test_calculate_breakeven_days_taker(trader):
    # Taker roundtrip fee = (0.0010 + 0.0005) * 2 * 100 = 0.30%
    # Rate = 0.0001 (0.01% per 8h = 0.03% per day = ~10.9% APY)
    # Breakeven days = 0.30 / 0.03 = 10.0 days (trap identified by user!)
    be_days, fee_pct = trader.calculate_breakeven_days(0.0001, is_maker=False)
    assert be_days == 10.0
    assert fee_pct == 0.30


def test_fee_breakeven_guard_rejects_slow_amortization(trader):
    # Rate 0.00005 (0.005% per 8h = 0.015% per day = 5.4% APY)
    # With Maker fee 0.08%, breakeven = 0.08 / 0.015 = 5.33 days (> 2.5 max allowed)
    is_ok, reason, details = trader.evaluate_opportunity(
        symbol="BTC/USDT",
        rate_8h=0.00005,
        spot_price=70000.0,
        perp_price=70010.0
    )
    assert is_ok is False
    assert "APY_TOO_LOW" in reason or "FEE_BREAKEVEN_EXCEEDED" in reason


def test_basis_guard_rejects_dislocated_spread(trader):
    # High APY (25%), but spot is 100 and perp is 101.5 (1.5% basis > 0.80% max contango)
    is_ok, reason, details = trader.evaluate_opportunity(
        symbol="SOL/USDT",
        rate_8h=0.0003,
        spot_price=100.0,
        perp_price=101.5
    )
    assert is_ok is False
    assert "BASIS_DISLOCATION" in reason or "BASIS_EXTREME_CONTANGO" in reason



def test_evaluate_opportunity_passes_for_high_quality_setup(trader):
    # Rate 0.0003 (0.03% per 8h = ~32.8% APY), spot 100.0, perp 100.05 (basis 0.05%)
    # Maker fee 0.08%, breakeven = 0.08 / 0.09 = 0.89 days (< 2.5d max)
    is_ok, reason, details = trader.evaluate_opportunity(
        symbol="NEAR/USDT",
        rate_8h=0.0003,
        spot_price=100.0,
        perp_price=100.05
    )
    assert is_ok is True
    assert reason == "QUALIFIED"
    assert details["breakeven_days"] < 1.5
    assert details["projected_apy"] > 30.0


@pytest.mark.asyncio
async def test_open_delta_neutral_position_success(trader, mock_repo, mock_notifier):
    pos = await trader.open_delta_neutral_position(
        symbol="NEAR/USDT",
        notional_usdt=100.0,
        rate_8h=0.00025,
        spot_price=5.0,
        perp_price=5.002
    )
    assert pos is not None
    assert pos.symbol == "NEAR/USDT"
    assert pos.notional_usdt == 100.0
    assert pos.status == DeltaNeutralStatus.OPEN
    assert pos.position_id in trader.active_positions
    mock_repo.save_delta_neutral_position.assert_called_once()
    mock_notifier.notify.assert_called_once()


@pytest.mark.asyncio
async def test_atomic_rollback_when_leg2_fails(trader, mock_repo, mock_notifier):
    # Мокаємо збій на Нозі 2
    with patch.object(trader, '_execute_leg', side_effect=[True, False]):
        with patch.object(trader, '_rollback_leg', new_callable=AsyncMock) as mock_rollback:
            pos = await trader.open_delta_neutral_position(
                symbol="ETH/USDT",
                notional_usdt=100.0,
                rate_8h=0.00025,
                spot_price=3000.0,
                perp_price=3001.0
            )
            # Позиція не повинна створитися
            assert pos is None
            assert len(trader.active_positions) == 0
            # Атомарний відкат повинен викликатися негайно!
            mock_rollback.assert_called_once()
            # Повинно бути надіслано тривожне сповіщення про Rollback
            mock_notifier.notify.assert_called_once()
            assert "ATOMIC ROLLBACK EXECUTED" in mock_notifier.notify.call_args[0][0]


def test_accrue_funding_payments(trader, mock_repo):
    # Створюємо активну тестову позицію
    pos = DeltaNeutralPosition(
        position_id="dn_test_123",
        symbol="NEAR/USDT",
        mode=DeltaNeutralMode.SPOT_PERP,
        leg1_exchange="binance",
        leg1_symbol="NEAR/USDT",
        leg1_side=TradeSide.BUY,
        leg1_entry_price=5.0,
        leg1_amount=20.0,
        leg2_exchange="binance",
        leg2_symbol="NEAR/USDT:USDT",
        leg2_side=TradeSide.SELL,
        leg2_entry_price=5.0,
        leg2_amount=20.0,
        notional_usdt=100.0,
        current_8h_rate=0.0003,
        opened_at=time.time() - 30000,
        last_funding_time=time.time() - 30000
    )
    trader.active_positions[pos.position_id] = pos

    # Нараховуємо виплату (0.0003 * 100 = 0.03 USDT)
    events = trader.accrue_funding(rates_map={"NEAR/USDT": 0.0003})
    assert len(events) == 1
    assert events[0]["payment_usdt"] == 0.03
    assert pos.accrued_funding_usdt == 0.03
    assert pos.funding_cycles_collected == 1
    mock_repo.update_delta_neutral_funding.assert_called_once()
    mock_repo.save_balance.assert_called_once_with(1000.03)


@pytest.mark.asyncio
async def test_close_delta_neutral_position(trader, mock_repo):
    pos = DeltaNeutralPosition(
        position_id="dn_close_test",
        symbol="BTC/USDT",
        mode=DeltaNeutralMode.SPOT_PERP,
        leg1_exchange="binance",
        leg1_symbol="BTC/USDT",
        leg1_side=TradeSide.BUY,
        leg1_entry_price=70000.0,
        leg1_amount=0.0014,
        leg2_exchange="binance",
        leg2_symbol="BTC/USDT:USDT",
        leg2_side=TradeSide.SELL,
        leg2_entry_price=70000.0,
        leg2_amount=0.0014,
        notional_usdt=100.0,
        accrued_funding_usdt=0.35,  # заробили 0.35 USDT на фандингу
        entry_fees_usdt=0.04,
        funding_cycles_collected=4
    )
    trader.active_positions[pos.position_id] = pos

    res = await trader.close_delta_neutral_position("dn_close_test", reason="TARGET_REACHED")
    assert res is not None
    assert res["accrued_funding_usdt"] == 0.35
    # Total fees = 0.04 (entry) + 0.04 (exit) = 0.08
    assert res["total_fees_usdt"] == 0.08
    # Net profit = 0.35 - 0.08 = 0.27 USDT
    assert res["net_profit_usdt"] == 0.27
    assert "dn_close_test" not in trader.active_positions
    mock_repo.close_delta_neutral_position.assert_called_once_with("dn_close_test", "TARGET_REACHED")
    mock_repo.log_trade.assert_called_once()


def test_asymmetric_basis_guard_contango_vs_backwardation(trader):
    # 1. Беквордація: perp 99.85 при spot 100.0 (-0.15% < -0.05%) -> блокується
    is_ok_back, reason_back, _ = trader.evaluate_opportunity(
        symbol="ETH/USDT",
        rate_8h=0.0003,
        spot_price=100.0,
        perp_price=99.85
    )
    assert is_ok_back is False
    assert "BASIS_BACKWARDATION" in reason_back

    # 2. Контанго: perp 100.25 при spot 100.0 (+0.25% contango) -> дозволяється (додатковий дохід)
    is_ok_cont, reason_cont, details_cont = trader.evaluate_opportunity(
        symbol="ETH/USDT",
        rate_8h=0.0003,
        spot_price=100.0,
        perp_price=100.25
    )
    assert is_ok_cont is True
    assert reason_cont == "QUALIFIED"
    assert details_cont["basis_pct"] == 0.25


@pytest.mark.asyncio
async def test_funding_flip_auto_unwind(trader, mock_repo, mock_notifier):
    # Позиція відкрита з позитивним фандингом
    pos = DeltaNeutralPosition(
        position_id="dn_flip_test",
        symbol="SOL/USDT",
        mode=DeltaNeutralMode.SPOT_PERP,
        leg1_exchange="binance",
        leg1_symbol="SOL/USDT",
        leg1_side=TradeSide.BUY,
        leg1_entry_price=150.0,
        leg1_amount=0.66,
        leg2_exchange="binance",
        leg2_symbol="SOL/USDT:USDT",
        leg2_side=TradeSide.SELL,
        leg2_entry_price=150.0,
        leg2_amount=0.66,
        notional_usdt=100.0,
        accrued_funding_usdt=0.10,
        funding_cycles_collected=1
    )
    trader.active_positions[pos.position_id] = pos

    # Ставка розвертається в жорсткий мінус (-0.01%)
    unwound = await trader.check_and_auto_unwind_flipped_positions(rates_map={"SOL/USDT": -0.0001})
    assert len(unwound) == 1
    assert "dn_flip_test" not in trader.active_positions
    assert "FUNDING_FLIP" in unwound[0]["close_reason"]
    mock_notifier.notify.assert_called_once()
    assert "FUNDING FLIP" in mock_notifier.notify.call_args[0][0]


@pytest.mark.asyncio
async def test_evaluate_auto_exits_hard_threshold_instant(trader):
    pos = DeltaNeutralPosition(
        position_id="dn_hard_exit",
        symbol="BTC/USDT",
        mode=DeltaNeutralMode.SPOT_PERP,
        leg1_exchange="binance",
        leg1_symbol="BTC/USDT",
        leg1_side=TradeSide.BUY,
        leg1_entry_price=65000.0,
        leg1_amount=0.0015,
        leg2_exchange="binance",
        leg2_symbol="BTC/USDT:USDT",
        leg2_side=TradeSide.SELL,
        leg2_entry_price=65000.0,
        leg2_amount=0.0015,
        notional_usdt=100.0
    )
    trader.active_positions[pos.position_id] = pos

    # Миттєвий вихід при ставці <= -0.0001 (-0.01%)
    closed = await trader.evaluate_auto_exits({"BTC/USDT": -0.00015})
    assert len(closed) == 1
    assert "FUNDING_FLIP_HARD" in closed[0]["close_reason"]
    assert "dn_hard_exit" not in trader.active_positions


@pytest.mark.asyncio
async def test_evaluate_auto_exits_soft_threshold_two_strikes(trader):
    pos = DeltaNeutralPosition(
        position_id="dn_soft_exit",
        symbol="ETH/USDT",
        mode=DeltaNeutralMode.SPOT_PERP,
        leg1_exchange="binance",
        leg1_symbol="ETH/USDT",
        leg1_side=TradeSide.BUY,
        leg1_entry_price=3500.0,
        leg1_amount=0.03,
        leg2_exchange="binance",
        leg2_symbol="ETH/USDT:USDT",
        leg2_side=TradeSide.SELL,
        leg2_entry_price=3500.0,
        leg2_amount=0.03,
        notional_usdt=100.0
    )
    trader.active_positions[pos.position_id] = pos

    # Перевірка 1: легкий нуль/мінус (-0.00005 > -0.0001) -> 1 страйк, ще не закриваємо
    closed_1 = await trader.evaluate_auto_exits({"ETH/USDT": -0.00005})
    assert len(closed_1) == 0
    assert "dn_soft_exit" in trader.active_positions
    assert trader._negative_funding_strikes.get("dn_soft_exit") == 1

    # Перевірка 2: ставка досі нульова -> 2 страйк -> авто-вихід!
    closed_2 = await trader.evaluate_auto_exits({"ETH/USDT": 0.0})
    assert len(closed_2) == 1
    assert "FUNDING_FLIP_CONFIRMED" in closed_2[0]["close_reason"]
    assert "dn_soft_exit" not in trader.active_positions
    assert "dn_soft_exit" not in trader._negative_funding_strikes


@pytest.mark.asyncio
async def test_evaluate_auto_exits_strike_reset_on_recovery(trader):
    pos = DeltaNeutralPosition(
        position_id="dn_recovery_exit",
        symbol="BNB/USDT",
        mode=DeltaNeutralMode.SPOT_PERP,
        leg1_exchange="binance",
        leg1_symbol="BNB/USDT",
        leg1_side=TradeSide.BUY,
        leg1_entry_price=600.0,
        leg1_amount=0.16,
        leg2_exchange="binance",
        leg2_symbol="BNB/USDT:USDT",
        leg2_side=TradeSide.SELL,
        leg2_entry_price=600.0,
        leg2_amount=0.16,
        notional_usdt=100.0
    )
    trader.active_positions[pos.position_id] = pos

    # Перевірка 1: мінус -> 1 страйк
    await trader.evaluate_auto_exits({"BNB/USDT": -0.00002})
    assert trader._negative_funding_strikes.get("dn_recovery_exit") == 1

    # Перевірка 2: ринок розвернувся назад у плюс (+0.0001) -> страйки скидаються
    await trader.evaluate_auto_exits({"BNB/USDT": 0.0001})
    assert "dn_recovery_exit" not in trader._negative_funding_strikes
    assert "dn_recovery_exit" in trader.active_positions

    # Перевірка 3: повторний спайк починається знову з 1 страйку, не закриваючи позицію завчасно
    closed_3 = await trader.evaluate_auto_exits({"BNB/USDT": -0.00002})
    assert len(closed_3) == 0
    assert trader._negative_funding_strikes.get("dn_recovery_exit") == 1
    assert "dn_recovery_exit" in trader.active_positions


