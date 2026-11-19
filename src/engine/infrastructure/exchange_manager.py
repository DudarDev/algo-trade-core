import ccxt.async_support as ccxt_async
import ccxt
import pandas as pd
import logging
import asyncio
from typing import Optional

from src.shared.config import Settings

logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self, settings: Settings, exchange_id: str = "binance", default_type: str = "spot"):
        self.settings = settings
        self.exchange_id = exchange_id
        self.default_type = default_type

        # --------------------- ПУБЛІЧНИЙ КЛІЄНТ (МАКСИМАЛЬНО ПРОСТИЙ) ---------------------
        config = {
            'enableRateLimit': True,
            'apiKey': '', # Явно кажемо CCXT: "у мене немає ключів"
            'secret': '',
        }
        if default_type and default_type != "spot":
            config['options'] = {'defaultType': default_type}

        self.public_exchange = getattr(ccxt_async, exchange_id)(config)
        logger.info(f"🌍 [Exchange] Публічне підключення: {self.public_exchange.name} ({default_type})")

        # --------------------- ПРИВАТНИЙ КЛІЄНТ ---------------------
        self.private_exchange: Optional[ccxt_async.Exchange] = None
        self._init_private_client()

    @property
    def exchange(self):
        """Зворотна сумісність для модулів, що звертаються до manager.exchange."""
        return self.public_exchange

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
        # 1. Перевірка надшвидкого WebSocket стріму (<20ms)
        if getattr(self.settings, 'WS_STREAM_ENABLED', True):
            try:
                from src.engine.infrastructure.websocket_feed import ws_feed
                ws_p = ws_feed.get_price(symbol, self.exchange_id)
                if ws_p is not None and ws_p > 0:
                    return ws_p
            except Exception:
                pass

        try:
            from src.engine.infrastructure.cache_manager import cache_manager
            cache_key = f"ticker:{self.exchange_id}:{symbol}"
            cached = cache_manager.get(cache_key)
            if cached is not None:
                return float(cached)
        except Exception:
            pass

        try:
            ticker = await self.public_exchange.fetch_ticker(symbol)
            price = float(ticker['last'])
            try:
                from src.engine.infrastructure.cache_manager import cache_manager
                cache_manager.set(f"ticker:{self.exchange_id}:{symbol}", price, ttl=3)
            except Exception:
                pass
            return price
        except Exception:
            return None

    async def fetch_bbo(self, symbol: str) -> Optional[dict]:
        """Отримує Best Bid / Best Ask (з WebSocket стріму або через REST)."""
        if getattr(self.settings, 'WS_STREAM_ENABLED', True):
            try:
                from src.engine.infrastructure.websocket_feed import ws_feed
                ws_bbo = ws_feed.get_bbo(symbol, self.exchange_id)
                if ws_bbo is not None:
                    return ws_bbo
            except Exception:
                pass

        try:
            ticker = await self.public_exchange.fetch_ticker(symbol)
            bid = float(ticker.get('bid') or ticker.get('last') or 0.0)
            ask = float(ticker.get('ask') or ticker.get('last') or 0.0)
            last = float(ticker.get('last') or 0.0)
            return {"bid": bid, "ask": ask, "last": last}
        except Exception:
            return None

    async def get_private_exchange(self) -> Optional[ccxt_async.Exchange]:
        return self.private_exchange

    async def get_futures_margin_ratio(self, symbol: str) -> Optional[float]:
        """
        Повертає Margin Ratio (%) з біржі для Live режиму або None для Paper-розрахунку.
        """
        if getattr(self.settings, 'PAPER_TRADING', True) or not self.private_exchange:
            return None

        try:
            if hasattr(self.private_exchange, 'fapiPrivateV2GetAccount'):
                acc = await self.private_exchange.fapiPrivateV2GetAccount()
                positions = acc.get('positions', [])
                clean_sym = symbol.replace('/', '').replace(':USDT', '')
                for p in positions:
                    if p.get('symbol') == clean_sym:
                        m_ratio = float(acc.get('totalMaintMargin', 0.0)) / max(0.0001, float(acc.get('totalMarginBalance', 1.0))) * 100.0
                        return round(m_ratio, 2)
            return None
        except Exception as e:
            logger.warning(f"⚠️ [Margin Query] Помилка отримання Margin Ratio для {symbol}: {e}")
            return None

    async def transfer_spot_to_futures(self, amount_usdt: float) -> bool:
        """
        Переказ USDT зі Spot на USD-M Futures для порятунку маржі.
        Підтримує Paper-режим та Live Binance Universal Transfer API.
        """
        if getattr(self.settings, 'PAPER_TRADING', True) or not self.private_exchange:
            logger.info(f"📝 [Paper Transfer] Імітація переказу {amount_usdt:.2f} USDT зі Spot на Futures. Успішно!")
            return True

        try:
            logger.info(f"🔄 [Universal Transfer] Переказ {amount_usdt:.2f} USDT зі Spot на USD-M Futures...")
            if hasattr(self.private_exchange, 'transfer'):
                await self.private_exchange.transfer('USDT', amount_usdt, 'spot', 'future')
                return True
            elif hasattr(self.private_exchange, 'sapiPostAssetTransfer'):
                await self.private_exchange.sapiPostAssetTransfer({
                    'type': 'MAIN_UMFUTURE',
                    'asset': 'USDT',
                    'amount': amount_usdt
                })
                return True
            return False
        except Exception as e:
            logger.error(f"❌ [Universal Transfer Error] Не вдалося переказати {amount_usdt:.2f} USDT: {e}")
            return False