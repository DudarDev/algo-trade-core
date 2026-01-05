import ccxt
import pandas as pd
import logging

class MarketScanner:
    def __init__(self, exchange_id='binanceus'):
        self.exchange = getattr(ccxt, exchange_id)()
        
    def get_top_volatile_pairs(self, limit=10, min_volume=50000): # <-- Зменшили поріг до 50k$
        """
        Шукає пари, які мають найбільшу волатильність (рух ціни), 
        навіть якщо вони не дуже популярні.
        """
        logging.info("🔍 [Scanner] Шукаю монети з високою волатильністю...")
        
        try:
            tickers = self.exchange.fetch_tickers()
            pairs_data = []
            
            for symbol, data in tickers.items():
                if '/USDT' not in symbol: continue
                
                quote_vol = data.get('quoteVolume')
                # Фільтруємо зовсім "мертві" монети, але беремо середні
                if not quote_vol or quote_vol < min_volume: continue
                
                # change_pct - це наскільки змінилася ціна за 24 години (без знаку мінус)
                # Нам байдуже, впала вона чи виросла. Головне - що вона РУХАЄТЬСЯ.
                change_pct = abs(data.get('percentage', 0))
                
                pairs_data.append({
                    'symbol': symbol,
                    'change': change_pct
                })
            
            # Сортуємо: зверху ті, що найбільше скачуть
            sorted_pairs = sorted(pairs_data, key=lambda x: x['change'], reverse=True)
            
            # Беремо топ-10 найактивніших
            top_pairs = [p['symbol'] for p in sorted_pairs[:limit]]
            
            logging.info(f"🔥 Знайдено активні пари: {top_pairs}")
            return top_pairs

        except Exception as e:
            logging.error(f"Помилка сканера: {e}")
            return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT']