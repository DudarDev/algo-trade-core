import requests
import logging
import os


class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TG_TOKEN", "")
        self.chat_id = os.getenv("TG_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)

    def send(self, message):
        if not self.enabled:
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, json=data, timeout=5)
        except:
            pass

    def send_trade(self, action, symbol, price, amount, pnl=None, balance=None):
        if not self.enabled:
            return
        if action == "BUY":
            msg = f"🟢 *BUY {symbol}*\nPrice: {price}"
        elif action == "SELL":
            msg = f"🔴 *SELL {symbol}*\nPnL: {pnl:.2f}%"
        self.send(msg)
