import ccxt
import pandas as pd
import os
from dotenv import load_dotenv

class ExchangeManager:
    def __init__(self, exchange_id='binance'):
        # Завантажуємо ключі (якщо є файл .env)
        load_dotenv()
        self.api_key = os.getenv('API_KEY')
        self.api_secret = os.getenv('API_SECRET')
        
        # Налаштування підключення
        exchange_class = getattr(ccxt, exchange_id)
        self.exchange = exchange_class({
            'apiKey': self.api_key,
            'secret': self.api_secret,
            'enableRateLimit': True,  # Захист від блокування
            'options': {'defaultType': 'spot'}
        })

    def get_price(self, symbol):
        """Отримує лише поточну ціну"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            print(f"❌ Помилка отримання ціни: {e}")
            return None

    def get_history(self, symbol, timeframe='1m', limit=100):
        """
        Завантажує історію (свічки) для аналізу.
        Повертає таблицю з даними.
        """
        try:
            # Отримуємо свічки: [Час, Відкриття, Макс, Мін, Закриття, Об'єм]
            bars = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            
            # Перетворюємо в зручну таблицю (DataFrame)
            df = pd.DataFrame(bars, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            
            # Робимо час зрозумілим для людей
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            return df
        except Exception as e:
            print(f"❌ Помилка історії: {e}")
            return None