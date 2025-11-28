import ccxt
import pandas as pd
import os
from dotenv import load_dotenv

class ExchangeManager:
    # 👇 ЗМІНА: За замовчуванням ставимо 'kraken' замість 'binance'
    # Binance блокує сервери Google (США). Kraken працює стабільно.
    def __init__(self, exchange_id='kraken'):
        load_dotenv()
        self.api_key = os.getenv('API_KEY')
        self.api_secret = os.getenv('API_SECRET')
        
        # Динамічний вибір біржі
        try:
            exchange_class = getattr(ccxt, exchange_id)
        except AttributeError:
            print(f"⚠️ Біржа '{exchange_id}' не знайдена в ccxt. Перемикаюсь на Kraken.")
            exchange_class = ccxt.kraken

        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        }
        
        # Додаємо ключі тільки якщо вони є
        if self.api_key and self.api_secret:
            config['apiKey'] = self.api_key
            config['secret'] = self.api_secret

        self.exchange = exchange_class(config)
        print(f"🔌 Підключено до біржі: {self.exchange.name}")

    def get_price(self, symbol):
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            print(f"❌ Помилка отримання ціни: {e}")
            return None

    def fetch_candles(self, symbol, timeframe, limit=100):
        try:
            # Запит до біржі
            bars = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            
            if not bars:
                print(f"⚠️ {self.exchange.name} повернув пусті дані для {symbol}. Можливо, пара не підтримується або IP заблоковано.")
                return pd.DataFrame()

            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"❌ Помилка з'єднання з біржею: {e}")
            return pd.DataFrame()