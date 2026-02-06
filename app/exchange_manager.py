import ccxt
import pandas as pd
import os
import time
from dotenv import load_dotenv

class ExchangeManager:
    # 👇 За замовчуванням ставимо 'binanceus' для серверів у США (GCP us-central1)
    def __init__(self, exchange_id="binanceus"):
        load_dotenv()
        self.api_key = os.getenv("BINANCE_API_KEY", "") # Або просто пусті рядки для публічних даних
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")

        # Налаштування CCXT
        exchange_class = getattr(ccxt, exchange_id)
        
        config = {
            "enableRateLimit": True, 
            "options": {"defaultType": "spot"},
            "timeout": 30000,  # 30 секунд таймаут
        }

        # Додаємо ключі тільки якщо вони є (для торгівлі)
        # Для отримання цін (fetch_ohlcv) ключі не обов'язкові
        if self.api_key and self.api_secret:
            config["apiKey"] = self.api_key
            config["secret"] = self.api_secret

        self.exchange = exchange_class(config)
        print(f"🔌 [Exchange] Підключено до: {self.exchange.name} (US-Compatible)")

    def get_price(self, symbol):
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker["last"]
        except Exception as e:
            print(f"❌ [Price Error] {symbol}: {e}")
            return None

    def fetch_candles(self, symbol, timeframe, limit=100):
        try:
            # Запит до біржі
            bars = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

            if not bars:
                print(f"⚠️ Пусті дані для {symbol}. Перевірте назву пари на {self.exchange.name}.")
                return pd.DataFrame()

            df = pd.DataFrame(
                bars, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
        except Exception as e:
            print(f"❌ [Candle Error] {symbol}: {e}")
            return pd.DataFrame()
    
    def get_markets(self):
        try:
            return self.exchange.load_markets()
        except Exception as e:
            print(f"❌ Error loading markets: {e}")
            return {}