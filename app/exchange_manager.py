import ccxt
import pandas as pd
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class ExchangeManager:
    # Перемикаємось на Kraken - він дружить з серверами в США і має об'єми
    def __init__(self, exchange_id: str = "kraken"):
        self.exchange_id = exchange_id
        exchange_class = getattr(ccxt, self.exchange_id)
        self.exchange = exchange_class({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        self.client = self.exchange
        print(f"🔌 [Exchange] Підключено до: {self.exchange.name}")

    def fetch_data(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> pd.DataFrame:
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if not ohlcv: return pd.DataFrame()
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return df
        except Exception as e:
            logger.error(f"❌ Помилка fetch_data для {symbol}: {e}")
            return pd.DataFrame()
