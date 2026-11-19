# tests/unit/test_bnb_manager.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock

from src.engine.application.bnb_manager import BNBAutoBalanceManager


@pytest.fixture
def mock_exchange():
    exchange = MagicMock()
    exchange.get_spot_free_balance = AsyncMock(return_value=0.01)  # 0.01 BNB
    exchange.get_spot_price = AsyncMock(return_value=600.0)        # $6.00 value
    exchange.buy_spot_market_quote = AsyncMock(return_value={"id": "ord_123", "status": "closed"})
    return exchange


@pytest.mark.asyncio
async def test_bnb_manager_paper_mode_does_nothing(mock_exchange):
    manager = BNBAutoBalanceManager(exchange=mock_exchange, trading_mode="PAPER")
    res = await manager.check_and_refill()
    assert res is False
    mock_exchange.get_spot_free_balance.assert_not_called()
    mock_exchange.buy_spot_market_quote.assert_not_called()


@pytest.mark.asyncio
async def test_bnb_manager_sufficient_balance_skips(mock_exchange):
    # Баланс BNB = 0.02 * 600 = $12.00 >= $3.00 (min_bnb_usdt)
    mock_exchange.get_spot_free_balance = AsyncMock(side_effect=lambda asset: 0.02 if asset == "BNB" else 500.0)
    manager = BNBAutoBalanceManager(exchange=mock_exchange, trading_mode="LIVE", min_bnb_usdt=3.0)

    res = await manager.check_and_refill()
    assert res is False
    mock_exchange.buy_spot_market_quote.assert_not_called()


@pytest.mark.asyncio
async def test_bnb_manager_insufficient_free_usdt_skips(mock_exchange):
    # Баланс BNB низький: 0.001 * 600 = $0.60 < $3.00
    # Але вільний USDT = $25.00 < ($10.0 докупівля + $20.0 резерв = $30.0)
    mock_exchange.get_spot_free_balance = AsyncMock(side_effect=lambda asset: 0.001 if asset == "BNB" else 25.0)
    manager = BNBAutoBalanceManager(
        exchange=mock_exchange,
        trading_mode="LIVE",
        min_bnb_usdt=3.0,
        top_up_usdt=10.0,
        min_free_usdt_reserve=20.0
    )

    res = await manager.check_and_refill()
    assert res is False
    mock_exchange.buy_spot_market_quote.assert_not_called()


@pytest.mark.asyncio
async def test_bnb_manager_live_refill_success(mock_exchange):
    # Баланс BNB низький ($0.60), вільного USDT достатньо ($150.0)
    mock_exchange.get_spot_free_balance = AsyncMock(side_effect=lambda asset: 0.001 if asset == "BNB" else 150.0)
    mock_notify = AsyncMock()

    manager = BNBAutoBalanceManager(
        exchange=mock_exchange,
        trading_mode="LIVE",
        min_bnb_usdt=3.0,
        top_up_usdt=10.0,
        min_free_usdt_reserve=20.0
    )

    res = await manager.check_and_refill(notify_callback=mock_notify)
    assert res is True
    mock_exchange.buy_spot_market_quote.assert_called_once_with("BNB/USDT", 10.0)
    mock_notify.assert_called_once()
    assert "BNB AUTO-REFILL" in mock_notify.call_args[0][0]
    assert manager._last_top_up_at is not None


@pytest.mark.asyncio
async def test_bnb_manager_cooldown_prevents_duplicate_buys(mock_exchange):
    mock_exchange.get_spot_free_balance = AsyncMock(side_effect=lambda asset: 0.001 if asset == "BNB" else 150.0)
    manager = BNBAutoBalanceManager(
        exchange=mock_exchange,
        trading_mode="LIVE",
        min_bnb_usdt=3.0,
        top_up_usdt=10.0,
        cooldown_minutes=60
    )

    # 1. Перша купівля проходить
    res_1 = await manager.check_and_refill()
    assert res_1 is True

    # 2. Друга купівля відразу після першої блокується кулдауном
    res_2 = await manager.check_and_refill()
    assert res_2 is False
    assert mock_exchange.buy_spot_market_quote.call_count == 1


@pytest.mark.asyncio
async def test_bnb_manager_error_handling(mock_exchange):
    mock_exchange.get_spot_free_balance = AsyncMock(side_effect=Exception("API connection timeout"))
    manager = BNBAutoBalanceManager(exchange=mock_exchange, trading_mode="LIVE")

    res = await manager.check_and_refill()
    assert res is False
