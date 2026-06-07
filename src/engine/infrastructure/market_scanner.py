import logging
from typing import List
import asyncio

from src.engine.infrastructure.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self, exchange_manager: ExchangeManager):
        self.exchange_manager = exchange_manager
        
        # Використовуємо вже готовий та налаштований публічний клієнт з ExchangeManager
        self.public_exchange = self.exchange_manager.public_exchange
        
        self.stablecoins = {'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USD', 'FDUSD', 'USDE'}

    async def get_top_volatile_pairs(self, limit: int = 20, min_volume: float = 1000.0) -> List[str]:
        """Шукає пари з найбільшою волатильністю (через Public API)."""
        for attempt in range(3):
            try:
                logger.info("🔍 [Scanner] Шукаю монети з високою волатильністю (Public API)...")
                
                # Використовуємо публічний клієнт для отримання тікерів
                tickers = await self.public_exchange.fetch_tickers()
                pairs_data = []
                
                for symbol, data in tickers.items():
                    if '/USDT' not in symbol and '/USD' not in symbol:
                        continue
                    base_coin = symbol.split('/')[0]
                    if base_coin in self.stablecoins:
                        continue
                    
                    quote_vol = data.get('quoteVolume')
                    if quote_vol is None or float(quote_vol) < min_volume:
                        continue
                    
                    change_pct = abs(data.get('percentage') or 0.0)
                    pairs_data.append({'symbol': symbol, 'change': change_pct})
                
                sorted_pairs = sorted(pairs_data, key=lambda x: x['change'], reverse=True)
                top_pairs = [p['symbol'] for p in sorted_pairs[:limit]]
                
                if not top_pairs:
                    logger.warning("⚠️ Не знайдено пар, що відповідають критеріям об'єму.")
                    return []
                
                logger.info(f"🔥 Знайдено активні пари: {top_pairs}")
                return top_pairs

            except Exception as e:
                logger.error(f"❌ Помилка сканера (спроба {attempt+1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(5)  # Зачекати перед повторною спробою
                else:
                    logger.error("🛑 Вичерпано спроби сканування.")
                    return []
        return []