import asyncio
import requests
import logging
from src.shared.config import settings

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.enabled = getattr(settings, 'ENABLE_TELEGRAM', False)
        raw_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if raw_token and hasattr(raw_token, 'get_secret_value'):
            self.token = raw_token.get_secret_value()
        else:
            self.token = str(raw_token) if raw_token else None

        self.chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage" if self.token else ""

    def _sync_post(self, text: str) -> None:
        if not self.enabled or not self.token or not self.chat_id:
            return
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            response = requests.post(self.base_url, json=payload, timeout=5)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"❌ Помилка відправки Telegram: {e}")

    async def send_message(self, text: str) -> None:
        if not self.enabled or not self.token or not self.chat_id:
            return
        await asyncio.to_thread(self._sync_post, text)
