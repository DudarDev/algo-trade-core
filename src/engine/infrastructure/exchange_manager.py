import ccxt.async_support as ccxt_async
import ccxt
import pandas as pd
import logging
import asyncio
from typing import Optional

from src.shared.config import Settings

logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self, settings: Settings, exchange_id: str = "binance"):
        self.settings = settings
        self.exchange_id = exchange_id

        # --------------------- ПУБЛІЧНИЙ КЛІЄНТ (МАКСИМАЛЬНО ПРОСТИЙ) ---------------------
        # Жодних options['defaultType']. Просто чистий анонімний клієнт.
        self.public_exchange = getattr(ccxt_async, exchange_id)({
            'enableRateLimit': True,
            'apiKey': '', # Явно кажемо CCXT: "у мене немає ключів"
            'secret': '',
        })
        logger.info(f"🌍 [Exchange] Публічне підключення: {self.public_exchange.name}")

        # --------------------- ПРИВАТНИЙ КЛІЄНТ ---------------------
        self.private_exchange: Optional[ccxt_async.Exchange] = None
        self._init_private_client()

    def _init_private_client(self) -> None:
        try:
            api_key = self.settings.BINANCE_API_KEY.get_secret_value()
            secret = self.settings.BINANCE_SECRET_KEY.get_secret_value()
        except Exception:
            return

        if not api_key or not secret or len(api_key) < 10:
            logger.info("🔐 Працюємо в Paper Trading режимі (без реальних ключів).")
            return

        self.private_exchange = getattr(ccxt_async, self.exchange_id)({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
        })

    async def close(self) -> None:
        if hasattr(self.public_exchange, 'close'):
            await self.public_exchange.close()
        if self.private_exchange and hasattr(self.private_exchange, 'close'):
            await self.private_exchange.close()

    def _empty_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    async def fetch_data(self, symbol: str, timeframe: str = '5m', limit: int = 100, retries: int = 3) -> pd.DataFrame:
        actual_limit = max(limit, 300)

        for attempt in range(retries):
            try:
                # CCXT автоматично зрозуміє, що ключі порожні, і не підписуватиме запит
                ohlcv = await self.public_exchange.fetch_ohlcv(symbol, timeframe, limit=actual_limit)
                
                if not ohlcv:
                    return self._empty_dataframe()

                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                cols = ['open', 'high', 'low', 'close', 'volume']
                df[cols] = df[cols].astype(float)
                return df

            except ccxt.RateLimitExceeded:
                await asyncio.sleep((attempt + 1) * 2)
            except ccxt.NetworkError as e:
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Критична помилка fetch_data для {symbol}: {e}")
                break

        return self._empty_dataframe()

    async def fetch_current_price(self, symbol: str) -> Optional[float]:
        try:
            ticker = await self.public_exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception:
            return None

    async def get_private_exchange(self) -> Optional[ccxt_async.Exchange]:
        return self.private_exchange