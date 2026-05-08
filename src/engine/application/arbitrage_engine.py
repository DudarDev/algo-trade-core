import logging
import time
import asyncio
from typing import Dict, Optional, Any

from src.shared.config import Settings
from src.engine.infrastructure.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class ArbitrageEngine:
    """Асинхронний рушій для міжбіржового арбітражу (Spatial Arbitrage)."""
    
    def __init__(self, settings: Settings, exchanges: Dict[str, ExchangeManager]):
        # 💉 Dependency Injection: Передаємо готові підключення до бірж
        self.settings = settings
        self.exchanges = exchanges
        
        # Стандартна комісія Taker (можна винести в Settings, зазвичай ~0.1%)
        self.estimated_fee_pct = 0.1 
        
        logger.info(f"🌍 Ініціалізація Арбітражу. Підключені біржі: {list(self.exchanges.keys())}")

    async def _fetch_ticker_safe(self, name: str, mgr: ExchangeManager, symbol: str) -> Optional[Dict[str, Any]]:
        """Асинхронний воркер для отримання тікера з однієї біржі."""
        try:
            ticker = await mgr.exchange.fetch_ticker(symbol)
            if ticker.get('bid') and ticker.get('ask'):
                return {
                    'exchange': name,
                    'bid': float(ticker['bid']), # Продаємо ТУТ
                    'ask': float(ticker['ask']), # Купуємо ТУТ
                    'last': float(ticker.get('last', 0))
                }
        except Exception as e:
            logger.debug(f"⚠️ [Арбітраж] Пропуск {name} для {symbol}: {e}")
        return None

    async def get_prices(self, symbol: str) -> Dict[str, Dict[str, float]]:
        """Отримує стакан цін ОДНОЧАСНО з усіх підключених бірж."""
        # ⚡ Магія Asyncio: створюємо масив задач і запускаємо паралельно
        tasks = [
            self._fetch_ticker_safe(name, mgr, symbol) 
            for name, mgr in self.exchanges.items()
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Фільтруємо None (якщо якась біржа впала) і збираємо в словник
        prices = {}
        for res in results:
            if res:
                prices[res.pop('exchange')] = res
                
        return prices

    async def find_opportunity(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Шукає прибуткову вилку між біржами з урахуванням комісій."""
        prices = await self.get_prices(symbol)
        
        # Для арбітражу треба ціни мінімум з 2 бірж
        if len(prices) < 2:
            return None 

        # 1. Знаходимо де НАЙДЕШЕВШЕ купити (min ASK)
        buy_exchange = min(prices, key=lambda x: prices[x]['ask'])
        buy_price = prices[buy_exchange]['ask']

        # 2. Знаходимо де НАЙДОРОЖЧЕ продати (max BID)
        sell_exchange = max(prices, key=lambda x: prices[x]['bid'])
        sell_price = prices[sell_exchange]['bid']

        if buy_exchange == sell_exchange:
            return None

        # 3. Рахуємо чистий спред у відсотках (Gross Spread)
        gross_spread_pct = ((sell_price - buy_price) / buy_price) * 100

        # 4. Рахуємо реальний прибуток (віднімаємо 2 комісії: за покупку і за продаж)
        net_spread_pct = gross_spread_pct - (self.estimated_fee_pct * 2)

        # 5. Якщо чистий спред (з урахуванням комісій) більший за наш поріг - це СИГНАЛ
        # Припустимо, ми хочемо мінімум 0.5% чистого прибутку після всіх комісій
        min_target_spread = getattr(self.settings, 'ARBITRAGE_MIN_SPREAD_PCT', 0.5)

        if net_spread_pct > min_target_spread:
            logger.info(f"🚨 АРБІТРАЖ: {symbol} | Купи на {buy_exchange} ({buy_price}) -> Продай на {sell_exchange} ({sell_price}) | Прибуток: {net_spread_pct:.2f}%")
            return {
                'symbol': symbol,
                'buy_ex': buy_exchange,
                'buy_price': buy_price,
                'sell_ex': sell_exchange,
                'sell_price': sell_price,
                'gross_spread': round(gross_spread_pct, 4),
                'net_spread': round(net_spread_pct, 4),
                'timestamp': time.time()
            }
        
        return None