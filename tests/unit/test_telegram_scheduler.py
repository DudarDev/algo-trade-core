import pytest
from unittest.mock import MagicMock, patch

from src.engine.infrastructure.telegram_scheduler import TelegramDigestScheduler


def test_telegram_digest_generator_empty_history():
    """Тест генерації тексту щоденного дайджесту при відсутності угод."""
    bot = MagicMock()
    bot.enabled = True
    bot.chat_id = "123456789"

    sched = TelegramDigestScheduler(telegram_bot=bot)
    digest = sched.generate_daily_digest()

    assert "ЩОДЕННИЙ КВАНТ-ДАЙДЖЕСТ PnL" in digest
    assert "Добовий PnL (24h):" in digest
    assert "Вінрейт за добу:" in digest
    assert "Circuit Breaker:" in digest


def test_telegram_digest_generator_with_trades():
    """Тест вибору найкращої угоди дня та підрахунку прибутку."""
    bot = MagicMock()
    sched = TelegramDigestScheduler(telegram_bot=bot)

    mock_trade1 = MagicMock()
    mock_trade1.pnl = 2.50
    mock_trade1.symbol = "ETH/USDT"

    mock_trade2 = MagicMock()
    mock_trade2.pnl = -0.80
    mock_trade2.symbol = "SOL/USDT"

    with patch("src.engine.infrastructure.telegram_scheduler.Trade") as mock_trade_model:
        mock_trade_model.objects.filter.return_value = [mock_trade1, mock_trade2]
        
        digest = sched.generate_daily_digest()
        assert "+1.70 USDT" in digest  # 2.50 - 0.80
        assert "ETH/USDT (+2.50 USDT)" in digest # Найкраща угода
        assert "50.0%" in digest # 1 виграш з 2 угод
