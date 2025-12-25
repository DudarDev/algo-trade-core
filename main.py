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
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return price, df
    except:
        return None, pd.DataFrame()

def main():
    load_dotenv()
    
    # 🔥 СПИСОК ТОП-10 ПАР
    PAIRS = [
        'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
        'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'LTC/USDT'
    ]
    
    print(f"🇺🇸 Підключення до Binance US. Моніторинг {len(PAIRS)} пар...")
    exchange = ccxt.binanceus() 
    
    ai_bot = TradingAI()
    trader = PaperTrader(initial_balance=1000.0)
    
    logging.info(f"🚀 Мульти-бот активовано! Стратегія: Smart Exit")

    while True:
        try:
            current_prices = {}
            
            for symbol in PAIRS:
                price, df = get_data(exchange, symbol)
                if price is None or df.empty: continue
                
                current_prices[symbol] = price

                # 1. Тренування
                if not ai_bot.is_trained:
                     ai_bot.train_new_model(df)

                # 2. Аналіз AI
                signal = ai_bot.predict(df)
                
                # 3. Логіка купівлі
                if signal == "BUY":
                    trader.buy(symbol, price, 100) # Входимо на 100$
                
                # 4. РОЗУМНА ЛОГІКА ПРОДАЖУ (Smart Exit)
                # Перевіряємо, чи є у нас ця монета
                if symbol in trader.positions:
                    entry_price = trader.positions[symbol]['entry_price']
                    # Рахуємо поточний % зміни ціни (без комісій)
                    pnl_raw = ((price - entry_price) / entry_price) * 100
                    
                    # ПРАВИЛА ВИХОДУ:
                    
                    # А. Take Profit: Якщо прибуток > 0.7% -> ПРОДАЄМО (фіксуємо)
                    if pnl_raw > 0.7:
                        logging.info(f"💰 Take Profit спрацював для {symbol} (+{pnl_raw:.2f}%)")
                        trader.sell(symbol, price)
                        
                    # Б. Stop Loss: Якщо збиток більше -1.5% -> ПРОДАЄМО (рятуємо залишок)
                    elif pnl_raw < -1.5:
                        logging.info(f"🛡️ Stop Loss спрацював для {symbol} ({pnl_raw:.2f}%)")
                        trader.sell(symbol, price)
                        
                    # В. AI Signal: Якщо AI кричить "SELL", слухаємо його, АЛЕ...
                    # Тільки якщо ми вже в невеликому плюсі (>0.1%) або помітному мінусі (<-0.5%)
                    # Це захищає від продажу "в нуль" через комісії
                    elif signal == "SELL":
                        if pnl_raw > 0.1 or pnl_raw < -0.5:
                            logging.info(f"🤖 AI вихід для {symbol} (PnL: {pnl_raw:.2f}%)")
                            trader.sell(symbol, price)
                        else:
                            # Ігноруємо AI, якщо ціна стоїть на місці (-0.1% ... +0.1%)
                            pass 

                time.sleep(1) 

            # Статус
            if trader.positions:
                trader.log_status(current_prices)
            
            logging.info("💤 Пауза 5 хвилин...")
            time.sleep(300)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()