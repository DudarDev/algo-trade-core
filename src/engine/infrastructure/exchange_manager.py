import ccxt.async_support as ccxt_async
import ccxt
import pandas as pd
import logging
import asyncio
from typing import Optional, Dict, Any

from src.shared.config import Settings

logger = logging.getLogger(__name__)

class ExchangeManager:
    """
    Розділяє з'єднання на публічне (ринкові дані) і приватне (торгівля/баланс).
    Приватний клієнт створюється тільки тоді, коли ключі реально надані та проходять перевірку.
    """

    def __init__(self, settings: Settings, exchange_id: str = "binance"):
        self.settings = settings
        self.exchange_id = exchange_id

        # --------------------- ПУБЛІЧНИЙ КЛІЄНТ (без ключів) ---------------------
        public_config = {
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'fetchMarkets': ['spot'],
            }
        }
        self.public_exchange: ccxt_async.Exchange = getattr(ccxt_async, exchange_id)(public_config)
        logger.info(f"🌍 [Exchange] Публічне підключення: {self.public_exchange.name}")

        # --------------------- ПРИВАТНИЙ КЛІЄНТ (спроба) ---------------------
        self.private_exchange: Optional[ccxt_async.Exchange] = None
        self._init_private_client()

    def _init_private_client(self) -> None:
        """
        Створює приватний клієнт тільки якщо ключі схожі на справжні.
        Справжність ключів перевіряється асинхронно при першому використанні.
        """
        try:
            api_key = self.settings.BINANCE_API_KEY.get_secret_value()
            secret = self.settings.BINANCE_SECRET_KEY.get_secret_value()
        except Exception:
            logger.info("🔐 Ключі API не знайдено – працюємо тільки в публічному режимі.")
            return

        # Прості евристики: не порожні, не 'dummy' і довжина > 10 символів
        if (not api_key or not secret or
            api_key.lower() == 'dummy' or secret.lower() == 'dummy' or
            len(api_key) < 10 or len(secret) < 10):
            logger.info("🔐 Ключі API некоректні/заглушки – працюємо тільки в публічному режимі.")
            return

        private_config = {
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'fetchMarkets': ['spot'],
            }
        }
        self.private_exchange = getattr(ccxt_async, self.exchange_id)(private_config)
        logger.info(f"🔑 [Exchange] Приватне підключення: {self.private_exchange.name} (чекає валідації)")

    async def validate_private_keys(self) -> bool:
        """
        Асинхронно перевіряє, чи приймає біржа надані ключі.
        Викличте один раз після запуску. Повертає True, якщо ключі робочі.
        """
        if not self.private_exchange:
            logger.warning("🔐 Приватний клієнт відсутній – перевірка не потрібна.")
            return False

        try:
            # Безпечний запит, який не змінює стан
            await self.private_exchange.fetch_balance()
            logger.info("✅ Приватні ключі валідні.")
            return True
        except Exception as e:
            logger.error(f"❌ Приватні ключі НЕВАЛІДНІ: {e}. Відключаю приватний режим.")
            await self.private_exchange.close()
            self.private_exchange = None
            return False

    async def close(self) -> None:
        """Коректно закриває обидві сесії."""
        if hasattr(self.public_exchange, 'close'):
            await self.public_exchange.close()
        if self.private_exchange and hasattr(self.private_exchange, 'close'):
            await self.private_exchange.close()
        logger.info("🔌 [Exchange] Усі з'єднання закрито.")

    def _empty_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    async def fetch_data(
        self,
        symbol: str,
        timeframe: str = '5m',
        limit: int = 100,
        retries: int = 3
    ) -> pd.DataFrame:
        """
        Завжди використовує ПУБЛІЧНЕ з'єднання для отримання OHLCV.
        """
        actual_limit = max(limit, 300)  # вимога ML-моделі

        for attempt in range(retries):
            try:
                ohlcv = await self.public_exchange.fetch_ohlcv(symbol, timeframe, limit=actual_limit)
                if not ohlcv:
                    logger.warning(f"⚠️ Немає даних для {symbol}")
                    return self._empty_dataframe()

                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                cols = ['open', 'high', 'low', 'close', 'volume']
                df[cols] = df[cols].astype(float)
                return df

            except ccxt.RateLimitExceeded:
                wait = (attempt + 1) * 2
                logger.warning(f"🐢 Rate limit ({symbol}). Спроба {attempt+1}/{retries}, чекаємо {wait}с...")
                await asyncio.sleep(wait)
            except ccxt.NetworkError as e:
                logger.warning(f"🌐 Мережева помилка ({symbol}): {e}. Спроба {attempt+1}/{retries}...")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Критична помилка fetch_data для {symbol}: {e}")
                break

        logger.error(f"🛑 Не вдалося отримати дані для {symbol} після {retries} спроб.")
        return self._empty_dataframe()

    async def fetch_current_price(self, symbol: str) -> Optional[float]:
        """
        Публічний отримувач ціни.
        """
        try:
            ticker = await self.public_exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"❌ Помилка отримання тікера {symbol}: {e}")
            return None

    # ------------- Приватні методи (трейдинг / баланс) -------------
    async def get_private_exchange(self) -> Optional[ccxt_async.Exchange]:
        """Повертає приватний екземпляр, якщо він доступний та пройшов валідацію."""
        if self.private_exchange is None:
            logger.warning("🔒 Приватний клієнт недоступний.")
        return self.private_exchange

    # Далі можна додати методи для торгівлі, наприклад:
    # async def create_order(self, symbol, type, side, amount, price=None, params={}):
    #     ex = await self.get_private_exchange()
    #     if not ex:
    #         raise RuntimeError("Приватний клієнт відсутній")
    #     return await ex.create_order(symbol, type, side, amount, price, params)