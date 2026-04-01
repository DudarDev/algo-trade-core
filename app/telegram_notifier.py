import requests
import os
import logging

logger = logging.getLogger("TG_Notifier")

class TelegramNotifier:
    def __init__(self, token, chat_id, enabled=True):
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, message):
        """Відправляє текстове повідомлення (Alert)"""
        if not self.enabled or not self.token or not self.chat_id:
            return
            
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML", # HTML дозволяє робити красиві жирні тексти <b>...</b>
                "disable_web_page_preview": True
            }
            response = requests.post(url, data=payload, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"⚠️ Помилка відправки Telegram алерта: {e}")

    def send_image(self, image_path, caption=""):
        """Відправляє фотографію графіка з підписом"""
        if not self.enabled or not self.token or not self.chat_id:
            return

        if not os.path.exists(image_path):
            logger.error(f"⚠️ Неможливо відправити графік. Файл не знайдено: {image_path}")
            return

        try:
            url = f"{self.api_url}/sendPhoto"
            with open(image_path, "rb") as img:
                payload = {
                    "chat_id": self.chat_id, 
                    "caption": caption,
                    "parse_mode": "HTML"
                }
                files = {"photo": img}
                response = requests.post(url, data=payload, files=files, timeout=15)
                response.raise_for_status()
                logger.info("📸 Графік успішно відправлено у Telegram!")
        except Exception as e:
            logger.error(f"⚠️ Помилка відправки графіка у Telegram: {e}")