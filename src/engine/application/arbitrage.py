# src/application/arbitrage.py
import logging
import asyncio
from typing import Dict, Optional

from src.shared.config import Settings
from src.engine.infrastructure.exchange_manager import ExchangeManager
from src.domain.models import ArbitrageOpportunity

logger = logging.getLogger(__name__)

class ArbitrageEngine:
    def __init__(self, settings: Settings, exchanges: Dict[str, ExchangeManager]):
        self.settings = settings
        self.exchanges = exchanges
        logger.info(f"🌍 Ініціалізація Арбітражу. Біржі: {list(self.exchanges.keys())}")

    async def _fetch_ticker_safe(self, name: str, mgr: ExchangeManager, symbol: str) -> Optional[Dict[str, float]]:
        try:
            # 🛡️ Захист від зависання біржі (Тайм-аут 3 секунди)
            ticker = await asyncio.wait_for(mgr.exchange.fetch_ticker(symbol), timeout=3.0)
            if ticker.get('bid') and ticker.get('ask'):
                return {
                    'exchange': name,
                    'bid': float(ticker['bid']),
                    'ask': float(ticker['ask']),
                }
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ [Арбітраж] Тайм-аут API для {name} ({symbol})")
        except Exception as e:
            logger.debug(f"⚠️ [Арбітраж] Помилка {name} для {symbol}: {e}")
        return None

    async def get_prices(self, symbol: str) -> Dict[str, Dict[str, float]]:
        tasks = [
            self._fetch_ticker_safe(name, mgr, symbol) 
            for name, mgr in self.exchanges.items()
        ]
        results = await asyncio.gather(*tasks)
        
        return {res['exchange']: res for res in results if res is not None}

    async def find_opportunity(self, symbol: str) -> Optional[ArbitrageOpportunity]:
        prices = await self.get_prices(symbol)
        
        if len(prices) < 2:
            return None 

        buy_exchange = min(prices, key=lambda x: prices[x]['ask'])
        buy_price = prices[buy_exchange]['ask']

        sell_exchange = max(prices, key=lambda x: prices[x]['bid'])
        sell_price = prices[sell_exchange]['bid']

        if buy_exchange == sell_exchange:
            return None

        gross_spread_pct = ((sell_price - buy_price) / buy_price) * 100
        net_spread_pct = gross_spread_pct - (self.settings.ARBITRAGE_FEE_PCT * 2)

        if net_spread_pct > self.settings.ARBITRAGE_MIN_SPREAD_PCT:
            logger.info(
                f"🚨 АРБІТРАЖ: {symbol} | "
                f"{buy_exchange}({buy_price}) -> {sell_exchange}({sell_price}) | "
                f"Net: {net_spread_pct:.2f}%"
            )
            # Повертаємо строгу Pydantic модель замість словника
            return ArbitrageOpportunity(
                symbol=symbol,
                buy_exchange=buy_exchange,
                buy_price=buy_price,
                sell_exchange=sell_exchange,
                sell_price=sell_price,
                gross_spread_pct=round(gross_spread_pct, 4),
                net_spread_pct=round(net_spread_pct, 4)
            )
        
        return None