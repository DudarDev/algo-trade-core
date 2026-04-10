import logging
from typing import List
from app.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self):
        self.mgr = ExchangeManager("kraken") # Гарантуємо, що тут Kraken
        self.exchange = self.mgr.exchange
        
    def get_top_volatile_pairs(self, limit: int = 20, min_volume: float = 1000.0) -> List[str]:
        """Шукає пари з найбільшою абсолютною волатильністю."""
        logger.info("🔍 [Scanner] Шукаю монети з високою волатильністю...")
        
        try:
            tickers = self.exchange.fetch_tickers()
            pairs_data = []
            
            stablecoins = ['USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USD']
            
            for symbol, data in tickers.items():
                if '/USDT' not in symbol and '/USD' not in symbol: 
                    continue
                
                # ФІЛЬТР: Відкидаємо стейблкоїни (напр. USDT/USD)
                base_coin = symbol.split('/')[0]
                if base_coin in stablecoins:
                    continue
                
                quote_vol = data.get('quoteVolume', 0.0)
                if not quote_vol or quote_vol < min_volume: 
                    continue
                
                change_pct = abs(data.get('percentage', 0.0))
                pairs_data.append({'symbol': symbol, 'change': change_pct})
            
            sorted_pairs = sorted(pairs_data, key=lambda x: x['change'], reverse=True)
            top_pairs = [p['symbol'] for p in sorted_pairs[:limit]]
            
            if not top_pairs:
                logger.warning("⚠️ Не знайдено пар, що відповідають критеріям.")
                return ['BTC/USDT', 'ETH/USDT']

            logger.info(f"🔥 Знайдено активні пари: {top_pairs}")
            return top_pairs

        except Exception as e:
            logger.error(f"❌ Помилка сканера: {e}", exc_info=True)
            return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'ADA/USDT']
