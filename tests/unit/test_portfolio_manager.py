import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.shared.config import Settings
from src.engine.application.portfolio_manager import PortfolioManager


@pytest.mark.asyncio
async def test_portfolio_manager_cash_only():
    """Тест підрахунку портфеля, коли відкритих угод немає."""
    mock_mgr = MagicMock()
    mock_mgr.private_exchange = None
    mock_mgr.fetch_current_price = AsyncMock(return_value=600.0)

    pm = PortfolioManager(settings=Settings(), exchange_manager=mock_mgr)
    summary = await pm.get_portfolio_summary()

    assert "total_portfolio_usdt" in summary
    assert summary["total_portfolio_usdt"] >= 0.0
    assert len(summary["assets"]) >= 1
    assert summary["assets"][0]["asset"] == "USDT"
    assert summary["assets"][0]["allocation_pct"] == 100.0


@pytest.mark.asyncio
async def test_portfolio_manager_bnb_discount_active():
    """Тест перевірки активації 25% знижки біржових комісій при наявності BNB >= $5."""
    mock_mgr = MagicMock()
    mock_mgr.private_exchange = MagicMock()
    # 0.05 BNB по курсу $600 = $30 USDT (> $5)
    mock_mgr.private_exchange.fetch_balance = AsyncMock(return_value={
        "free": {"BNB": 0.05, "USDT": 1000.0}
    })
    mock_mgr.fetch_current_price = AsyncMock(return_value=600.0)

    pm = PortfolioManager(settings=Settings(), exchange_manager=mock_mgr)
    summary = await pm.get_portfolio_summary()

    opt = summary["bnb_optimizer"]
    assert opt["discount_active"] is True
    assert opt["current_fee_rate_pct"] == 0.075
    assert opt["savings_pct"] == 25.0
    assert "АКТИВНА" in opt["status_message"]


@pytest.mark.asyncio
async def test_portfolio_manager_bnb_discount_inactive():
    """Тест перевірки рекомендації поповнення BNB при балансі < $5."""
    mock_mgr = MagicMock()
    mock_mgr.private_exchange = MagicMock()
    # 0.001 BNB по $600 = $0.6 USDT (< $5)
    mock_mgr.private_exchange.fetch_balance = AsyncMock(return_value={
        "free": {"BNB": 0.001, "USDT": 500.0}
    })
    mock_mgr.fetch_current_price = AsyncMock(return_value=600.0)

    pm = PortfolioManager(settings=Settings(), exchange_manager=mock_mgr)
    summary = await pm.get_portfolio_summary()

    opt = summary["bnb_optimizer"]
    assert opt["discount_active"] is False
    assert opt["current_fee_rate_pct"] == 0.100
    assert "Рекомендація" in opt["status_message"]
