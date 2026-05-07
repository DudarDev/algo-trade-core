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
        
        # Базові налаштування
        exchange_config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        }
        
        # 🔐 Безпечне завантаження ключів для реальної торгівлі
        # Використовуємо .get_secret_value() для Pydantic SecretStr
        if self.settings.BINANCE_API_KEY and self.settings.BINANCE_SECRET_KEY:
            exchange_config['apiKey'] = self.settings.BINANCE_API_KEY.get_secret_value()
            exchange_config['secret'] = self.settings.BINANCE_SECRET_KEY.get_secret_value()

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
        """
        Повертає порожній DataFrame зі збереженою структурою.
        Захищає від KeyError у модулях, які залежать від наявності колонок.
        """
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    async def fetch_data(
        self, 
        symbol: str, 
        timeframe: str = '5m', 
        limit: int = 100, 
        retries: int = 3
    ) -> pd.DataFrame:
        """
        Асинхронно завантажує свічки з механізмом Retry.
        """
        for attempt in range(retries):
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                
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
        """
        Швидке отримання поточної ціни без завантаження масиву свічок.
        Корисно для моніторингу відкритих позицій (Трейлінг стопів).
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"❌ Помилка отримання тікера {symbol}: {e}")
            return None