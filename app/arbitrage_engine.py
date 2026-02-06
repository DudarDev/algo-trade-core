import logging
import time
from app.exchange_manager import ExchangeManager
from app.config import Config

class ArbitrageEngine:
    def __init__(self):
        self.exchanges = {}
        self.logger = logging.getLogger("Arbitrage")
        
        self.logger.info(f"🌍 Ініціалізація Арбітражу на біржах: {Config.EXCHANGES}")
        
        # Підключаємо всі біржі з конфігу
        for name in Config.EXCHANGES:
            try:
                # ExchangeManager сам розбереться з ключами та проксі
                mgr = ExchangeManager(name)
                self.exchanges[name] = mgr.exchange
            except Exception as e:
                self.logger.error(f"❌ Failed to connect to {name}: {e}")

    def get_prices(self, symbol):
        """Отримує стакан цін (Order Book) на всіх біржах для однієї пари"""
        prices = {}
        for name, exchange in self.exchanges.items():
            try:
                # Отримуємо ticker (миттєва ціна)
                ticker = exchange.fetch_ticker(symbol)
                
                # Нам потрібні bid (найвища ціна, за яку готові купити) 
                # та ask (найнижча ціна, за яку готові продати)
                if ticker['bid'] and ticker['ask']:
                    prices[name] = {
                        'bid': ticker['bid'], # Продати ТУТ
                        'ask': ticker['ask'], # Купити ТУТ
                        'last': ticker['last']
                    }
            except Exception as e:
                # self.logger.debug(f"Skipping {name} for {symbol}: {e}")
                pass
        return prices

    def find_opportunity(self, symbol):
        """Шукає вилку між біржами"""
        prices = self.get_prices(symbol)
        
        # Для арбітражу треба ціни мінімум з 2 бірж
        if len(prices) < 2:
            return None 

        # 1. Знаходимо де НАЙДЕШЕВШЕ купити (min ASK)
        buy_exchange = min(prices, key=lambda x: prices[x]['ask'])
        buy_price = prices[buy_exchange]['ask']

        # 2. Знаходимо де НАЙДОРОЖЧЕ продати (max BID)
        sell_exchange = max(prices, key=lambda x: prices[x]['bid'])
        sell_price = prices[sell_exchange]['bid']

        # Перевірка на "самоторгівлю" (тієї ж біржі)
        if buy_exchange == sell_exchange:
            return None

        # 3. Рахуємо чистий спред у відсотках
        # (Продаж - Купівля) / Купівля * 100
        spread_pct = ((sell_price - buy_price) / buy_price) * 100

        # 4. Якщо спред більший за наш поріг (наприклад 1.5%) - це СИГНАЛ
        if spread_pct > Config.ARBITRAGE_MIN_SPREAD_PCT:
            return {
                'symbol': symbol,
                'buy_ex': buy_exchange,
                'buy_price': buy_price,
                'sell_ex': sell_exchange,
                'sell_price': sell_price,
                'spread': spread_pct,
                'timestamp': time.time()
            }
        
        return None