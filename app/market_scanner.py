import logging
from typing import List
from app.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class MarketScanner:
    def __init__(self):
        self.mgr = ExchangeManager("binanceus")
        self.exchange = self.mgr.exchange
        
    def get_top_volatile_pairs(self, limit: int = 10, min_volume: float = 50000.0) -> List[str]:
        """Шукає пари з найбільшою абсолютною волатильністю."""
        logger.info("🔍 [Scanner] Шукаю монети з високою волатильністю...")
        
        try:
            tickers = self.exchange.fetch_tickers()
            pairs_data = []
            
            for symbol, data in tickers.items():
                if '/USDT' not in symbol: 
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
