import logging
from typing import List

from src.engine.infrastructure.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self, exchange_manager: ExchangeManager):
        # 💉 Dependency Injection: ми не створюємо підключення, ми використовуємо існуюче
        self.exchange_manager = exchange_manager
        self.exchange = self.exchange_manager.exchange
        
        # Розширений список стейблкоїнів для сучасного ринку
        self.stablecoins = {'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USD', 'FDUSD', 'USDE'}

    async def get_top_volatile_pairs(self, limit: int = 20, min_volume: float = 1000.0) -> List[str]:
        """Шукає пари з найбільшою абсолютною волатильністю."""
        logger.info("🔍 [Scanner] Шукаю монети з високою волатильністю...")
        
        try:
            tickers = await self.exchange.fetch_tickers()
            pairs_data = []
            
            for symbol, data in tickers.items():
                # Фільтр 1: Тільки пари до USD/USDT
                if '/USDT' not in symbol and '/USD' not in symbol: 
                    continue
                
                # Фільтр 2: Відкидаємо стейблкоїни (напр. USDC/USDT)
                base_coin = symbol.split('/')[0]
                if base_coin in self.stablecoins:
                    continue
                
                # Захист від None значень у відповіді біржі
                quote_vol = data.get('quoteVolume')
                if quote_vol is None or float(quote_vol) < min_volume: 
                    continue
                
                change_pct = abs(data.get('percentage') or 0.0)
                pairs_data.append({'symbol': symbol, 'change': change_pct})
            
            # Сортування від найбільш до найменш волатильних
            sorted_pairs = sorted(pairs_data, key=lambda x: x['change'], reverse=True)
            top_pairs = [p['symbol'] for p in sorted_pairs[:limit]]
            
            if not top_pairs:
                logger.warning("⚠️ Не знайдено пар, що відповідають критеріям об'єму.")
                return [] # Безпечний Fallback: Оркестратор просто пропустить цикл

            logger.info(f"🔥 Знайдено активні пари: {top_pairs}")
            return top_pairs

        except Exception as e:
            # Не хардкодимо пари при помилці. Краще почекати відновлення зв'язку.
            logger.error(f"❌ Помилка сканера під час fetch_tickers: {e}")
            return []