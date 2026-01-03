import requests
import os


class TelegramNotifier:
    def __init__(self, token, chat_id, enabled=True):
        self.token = token
        self.chat_id = chat_id
        self.enabled = enabled
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    def send(self, message):
        """Відправляє просто текст"""
        if not self.enabled:
            return
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            requests.post(url, data=payload, timeout=5)
        except Exception as e:
            print(f"⚠️ Помилка Telegram (Текст): {e}")

    def send_image(self, image_path, caption=""):
        """Відправляє фото з підписом"""
        if not self.enabled:
            return

        if not os.path.exists(image_path):
            print(f"⚠️ Файлу з графіком немає: {image_path}")
            return

        try:
            url = f"{self.api_url}/sendPhoto"
            # Відкриваємо картинку і відправляємо
            with open(image_path, "rb") as img:
                payload = {"chat_id": self.chat_id, "caption": caption}
                files = {"photo": img}
                requests.post(url, data=payload, files=files, timeout=10)
                print("📸 Графік полетів у Telegram!")
        except Exception as e:
            print(f"⚠️ Помилка Telegram (Фото): {e}")
