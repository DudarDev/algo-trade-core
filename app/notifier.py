import requests
import logging
from app.config import Config

logger = logging.getLogger("Notifier")

class TelegramNotifier:
    def __init__(self):
        self.token = Config.TELEGRAM_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        
        if not self.token or not self.chat_id:
            logger.warning("⚠️ TELEGRAM не налаштовано! Повідомлення не будуть надсилатися. Перевір .env")

    def send_message(self, message: str):
        """Відправка звичайного текстового повідомлення (HTML)."""
        if not self.token or not self.chat_id:
            return

        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            requests.post(self.base_url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"❌ Помилка Telegram: {e}")

    def send_trade_notification(self, action: str, symbol: str, price: float, balance: float, reason: str = ""):
        """Красиве повідомлення про угоду."""
        if not self.token: return

        emoji = "🟢" if action == "BUY" else "🔴"
        
        msg = (
            f"{emoji} <b>{action} {symbol}</b>\n"
            f"💵 Price: <code>{price}</code>\n"
            f"💰 Balance: <code>{balance:.2f} USDT</code>\n"
            f"📊 Logic: {reason}"
        )
        self.send_message(msg)

    def send_error(self, error_msg: str):
        """Відправка критичних помилок."""
        if not self.token: return
        msg = f"🚨 <b>CRITICAL ERROR</b>\n<pre>{error_msg}</pre>"
        self.send_message(msg)