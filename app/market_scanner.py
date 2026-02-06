import logging
from app.exchange_manager import ExchangeManager

class MarketScanner:
    def __init__(self):
        # 👇 Використовуємо централізований менеджер (Geo-Fix)
        # Він автоматично вибере binanceus і налаштує параметри з'єднання
        self.mgr = ExchangeManager("binanceus")
        self.exchange = self.mgr.exchange
        
    def get_top_volatile_pairs(self, limit=10, min_volume=50000): # <-- Поріг 50k$
        """
        Шукає пари, які мають найбільшу волатильність (рух ціни), 
        навіть якщо вони не дуже популярні.
        """
        logging.info("🔍 [Scanner] Шукаю монети з високою волатильністю...")
        
        try:
            # Отримуємо всі тікери (використовуємо API, яке налаштував менеджер)
            tickers = self.exchange.fetch_tickers()
            pairs_data = []
            
            for symbol, data in tickers.items():
                # Працюємо тільки з USDT парами
                if '/USDT' not in symbol: continue
                
                # Фільтр за об'ємом (ліквідність)
                quote_vol = data.get('quoteVolume')
                if not quote_vol or quote_vol < min_volume: continue
                
                # change_pct - модуль зміни ціни за 24г (абсолютна волатильність)
                change_pct = abs(data.get('percentage', 0))
                
                pairs_data.append({
                    'symbol': symbol,
                    'change': change_pct
                })
            
            # Сортуємо: зверху ті, що найбільше рухаються
            sorted_pairs = sorted(pairs_data, key=lambda x: x['change'], reverse=True)
            
            # Беремо топ-N найактивніших
            top_pairs = [p['symbol'] for p in sorted_pairs[:limit]]
            
            logging.info(f"🔥 Знайдено активні пари: {top_pairs}")
            return top_pairs

        except Exception as e:
            logging.error(f"❌ Помилка сканера: {e}")
            # Повертаємо "безпечний" список, якщо API недоступне, щоб бот не зупинився
            return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'ADA/USDT']