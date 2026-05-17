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
        
        # 🛡️ КРИТИЧНИЙ ФІКС: Явно забороняємо ccxt звертатися до dapi/fapi ф'ючерсів
        exchange_config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'fetchMarkets': ['spot']  # Вантажимо ТІЛЬКИ спотові пари
            }
        }
        
        # 🔐 Безпечне завантаження ключів
        if self.settings.BINANCE_API_KEY and self.settings.BINANCE_SECRET_KEY:
            api_key = self.settings.BINANCE_API_KEY.get_secret_value()
            secret_key = self.settings.BINANCE_SECRET_KEY.get_secret_value()
            if api_key and api_key != "dummy":
                exchange_config['apiKey'] = api_key
                exchange_config['secret'] = secret_key

        # Динамічна ініціалізація біржі
        exchange_class = getattr(ccxt_async, self.exchange_id)
        self.exchange = exchange_class(exchange_config)
        
        mode = "🔑 Private" if 'apiKey' in exchange_config else "🌍 Public"
        logger.info(f"🔌 [Exchange] Ініціалізовано підключення ({mode}): {self.exchange.name}")

    async def close(self) -> None:
        """Коректно закриває aiohttp сесії."""
        if hasattr(self.exchange, 'close'):
            await self.exchange.close()
            logger.info("🔌 [Exchange] Підключення закрито.")

    def _empty_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    async def fetch_data(
        self, 
        symbol: str, 
        timeframe: str = '5m', 
        limit: int = 100, 
        retries: int = 3
    ) -> pd.DataFrame:
        
        # 🛡️ ЗАХИСНЕ ПРОГРАМУВАННЯ: Ігноруємо limit=100 з main.py
        # ML моделі треба щонайменше 110 свічок (60 + 50 для EMA). Форсуємо 300.
        actual_limit = max(limit, 300)

        for attempt in range(retries):
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=actual_limit)
                
                if not ohlcv:
                    logger.warning(f"⚠️ [Exchange] Немає даних для {symbol}")
                    return self._empty_dataframe()
                    
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                cols_to_float = ['open', 'high', 'low', 'close', 'volume']
                df[cols_to_float] = df[cols_to_float].astype(float)
                
                return df

            except ccxt.RateLimitExceeded:
                wait_time = (attempt + 1) * 2 
                logger.warning(f"🐢 Rate limit для {symbol}. Спроба {attempt + 1}/{retries}. Чекаємо {wait_time}с...")
                await asyncio.sleep(wait_time)
                
            except ccxt.NetworkError as e:
                logger.warning(f"🌐 Помилка мережі для {symbol}: {e}. Спроба {attempt + 1}/{retries}...")
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Критична помилка fetch_data для {symbol}: {e}")
                break 
        
        logger.error(f"🛑 Не вдалося отримати дані для {symbol} після {retries} спроб.")
        return self._empty_dataframe()

    async def fetch_current_price(self, symbol: str) -> Optional[float]:
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"❌ Помилка отримання тікера {symbol}: {e}")
            return None