import os
import time
import pandas as pd
from dotenv import load_dotenv
import logging
import ccxt

from app.ai_brain import TradingAI
from app.paper_trader import PaperTrader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_data(exchange, symbol):
    try:
        # Отримуємо і ціну, і історію одразу
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        return current_price, df
    except:
        return None, pd.DataFrame()

def main():
    load_dotenv()
    
    # 🔥 ТОП-10 ПАР (Висока ліквідність + Волатильність)
    PAIRS = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'XRP/USDT',
        'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'LTC/USDT', 'SHIB/USDT'
    ]
    
    print(f"🇺🇸 Підключення до Binance US. Моніторинг {len(PAIRS)} пар...")
    exchange = ccxt.binanceus() 
    
    # Використовуємо наш розумний мозок v3.1
    ai_bot = TradingAI()
    
    # Стартуємо з 1000 USDT
    trader = PaperTrader(initial_balance=1000.0)
    
    logging.info(f"🚀 Мульти-бот запущено! Портфель пустий.")

    while True:
        try:
            current_prices_map = {} # Для звіту по PnL

            for symbol in PAIRS:
                # 1. Тягнемо дані
                price, df = get_data(exchange, symbol)
                
                if price is None or df.empty:
                    continue
                
                current_prices_map[symbol] = price

                # 2. Тренування (якщо треба, бот сам вирішить)
                # Тренуємось тільки раз на цикл, якщо модель не готова
                if not ai_bot.is_trained:
                     ai_bot.train_new_model(df)

                # 3. Аналіз
                signal = ai_bot.predict(df)
                
                # 4. Дії
                if signal == "BUY":
                    # Ставимо 100$ на одну монету (максимум 10 позицій)
                    trader.buy(symbol, price, amount_usdt=100)
                
                elif signal == "SELL":
                    trader.sell(symbol, price)
                
                # Пауза щоб не забанили API (1 секунда)
                time.sleep(1)

            # Виводимо статус портфеля
            trader.log_status(current_prices_map)
            
            logging.info("💤 Пауза 5 хвилин...")
            time.sleep(300)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Error loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()