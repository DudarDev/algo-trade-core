import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from pathlib import Path

from src.engine.infrastructure.telegram_bot import InteractiveTelegramBot


@pytest.fixture
def telegram_bot(tmp_path):
    bot = InteractiveTelegramBot(token="mock_token_123", chat_id="123456789")
    bot.data_dir = tmp_path
    bot.cmd_file = tmp_path / "command_queue.json"
    return bot


def test_telegram_bot_authorization(telegram_bot):
    """Тест авторизації за chat_id."""
    assert telegram_bot.is_authorized("123456789") is True
    assert telegram_bot.is_authorized(123456789) is True
    assert telegram_bot.is_authorized("999999999") is False


def test_telegram_panic_close_command_queue(telegram_bot):
    """Тест створення файлу екстреної ліквідації всіх позицій (Panic Close)."""
    res = telegram_bot.trigger_panic_close_all()
    assert "PANIC CLOSE" in res
    assert telegram_bot.cmd_file.exists()

    with open(telegram_bot.cmd_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"action": "close_all"}


def test_telegram_format_status_message(telegram_bot):
    """Тест форматування повідомлення статусу системи."""
    with patch("src.engine.infrastructure.telegram_bot.BotControlService.get_current_status", return_value="active"):
        text, is_active = telegram_bot.format_status_message()
        assert "Quantum Scalper Pro" in text
        assert "Стан:" in text
        assert "Circuit Breaker:" in text
        assert is_active is True


def test_telegram_format_pnl_and_positions(telegram_bot):
    """Тест безпечного форматування PnL та списку позицій."""
    pnl_text = telegram_bot.format_pnl_message()
    assert isinstance(pnl_text, str)
    assert len(pnl_text) > 0

    pos_text = telegram_bot.format_positions_message()
    assert isinstance(pos_text, str)
    assert len(pos_text) > 0


@pytest.mark.asyncio
async def test_telegram_handle_text_pause_and_resume(telegram_bot):
    """Тест команд /pause та /resume із зміною стану системи."""
    mock_session = MagicMock()

    with patch("src.engine.infrastructure.telegram_bot.BotControlService") as mock_bcs, \
         patch.object(telegram_bot, "format_status_message", return_value=("Status OK", True)), \
         patch.object(telegram_bot, "_send_request", new_callable=AsyncMock) as mock_send:

        # 1. Тест /pause
        pause_update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 123456789},
                "text": "/pause"
            }
        }
        await telegram_bot.handle_update(mock_session, pause_update)
        mock_bcs.change_status.assert_called_with("stop")
        assert mock_send.called

        # 2. Тест /resume
        resume_update = {
            "update_id": 2,
            "message": {
                "chat": {"id": 123456789},
                "text": "/resume"
            }
        }
        await telegram_bot.handle_update(mock_session, resume_update)
        mock_bcs.change_status.assert_called_with("start")


@pytest.mark.asyncio
async def test_telegram_handle_inline_callbacks(telegram_bot):
    """Тест реакції на натискання інтерактивних inline кнопок."""
    mock_session = MagicMock()

    with patch.object(telegram_bot, "edit_message", new_callable=AsyncMock) as mock_edit, \
         patch.object(telegram_bot, "answer_callback", new_callable=AsyncMock) as mock_answer, \
         patch.object(telegram_bot, "format_status_message", return_value=("Status OK", True)), \
         patch.object(telegram_bot, "_send_request", new_callable=AsyncMock, return_value={"ok": True}), \
         patch("src.engine.infrastructure.telegram_bot.BotControlService") as mock_bcs:

        # Тест callback cmd_pause
        cb_pause = {
            "update_id": 3,
            "callback_query": {
                "id": "cb_1",
                "message": {
                    "chat": {"id": 123456789},
                    "message_id": 100
                },
                "data": "cmd_pause"
            }
        }
        await telegram_bot.handle_update(mock_session, cb_pause)
        mock_bcs.change_status.assert_called_with("stop")
        assert mock_edit.called
        assert mock_answer.called

        # Тест callback cmd_close_all
        cb_close = {
            "update_id": 4,
            "callback_query": {
                "id": "cb_2",
                "message": {
                    "chat": {"id": 123456789},
                    "message_id": 101
                },
                "data": "cmd_close_all"
            }
        }
        await telegram_bot.handle_update(mock_session, cb_close)
        assert telegram_bot.cmd_file.exists()


@pytest.mark.asyncio
async def test_telegram_unauthorized_access(telegram_bot):
    """Тест відхилення команд від неавторизованого користувача."""
    mock_session = MagicMock()

    with patch.object(telegram_bot, "_send_request", new_callable=AsyncMock) as mock_send:
        intruder_update = {
            "update_id": 5,
            "message": {
                "chat": {"id": 999999999},  # Чужий chat_id
                "text": "/pause"
            }
        }
        await telegram_bot.handle_update(mock_session, intruder_update)
        
        # Перевіряємо, що було надіслано повідомлення про заборону доступу
        assert mock_send.called
        call_args = mock_send.call_args[0]
        assert "Доступ заборонено" in call_args[2]["text"]


@pytest.mark.asyncio
async def test_telegram_ai_intel_command(telegram_bot):
    """Тест команди /ai та інтерактивного виклику Gemini Sentinel."""
    mock_session = MagicMock()

    with patch.object(telegram_bot, "_send_request", new_callable=AsyncMock) as mock_send, \
         patch.object(telegram_bot, "get_ai_intel_message", new_callable=AsyncMock, return_value="AI Intel Summary"):

        ai_update = {
            "update_id": 6,
            "message": {
                "chat": {"id": 123456789},
                "text": "/ai"
            }
        }
        await telegram_bot.handle_update(mock_session, ai_update)
        assert mock_send.called
        call_args = mock_send.call_args[0]
        assert call_args[2]["text"] == "AI Intel Summary"
