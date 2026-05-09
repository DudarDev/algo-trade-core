import requests
import logging
from src.shared.config import settings

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.enabled = settings.ENABLE_TELEGRAM
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_message(self, text: str):
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
