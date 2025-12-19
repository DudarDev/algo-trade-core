import os
import time
import pandas as pd
from dotenv import load_dotenv
import logging
import ccxt

from app.ai_brain import TradingAI
from app.paper_trader import PaperTrader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_market_price(exchange, symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        logging.error(f"Помилка отримання ціни: {e}")
        return None

def get_historical_data(exchange, symbol, limit=200):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1m', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return df
    except Exception as e:
        logging.error(f"Помилка історії: {e}")
        return pd.DataFrame()

def main():
    load_dotenv()
    
    SYMBOL = 'BTC/USDT'
    
    # --- ВИПРАВЛЕННЯ ---
    # Використовуємо Binance US, бо сервер Google знаходиться в США
    print("🇺🇸 Підключення до Binance US (через локацію сервера)...")
    exchange = ccxt.binanceus() 
    # -------------------
    
    ai_bot = TradingAI()
    trader = PaperTrader(initial_balance=1000.0)
    
    logging.info(f"🚀 Бот перезапущено (US Region Fix) на парі {SYMBOL}")
    logging.info(f"💰 Баланс: {trader.get_balance()} USDT")

    while True:
        try:
            current_price = get_market_price(exchange, SYMBOL)
            df = get_historical_data(exchange, SYMBOL)
            
            if df.empty or current_price is None:
                logging.warning("⏳ Чекаю дані від біржі...")
                time.sleep(10)
                continue

            if not ai_bot.is_trained:
                 logging.info("🧠 Треную AI...")
                 ai_bot.train_new_model(df)

            signal = ai_bot.predict(df)
            
            if signal == "BUY":
                trader.buy(symbol=SYMBOL, price=current_price, amount_usdt=100) 
            elif signal == "SELL":
                trader.sell(symbol=SYMBOL, price=current_price) 
            elif signal == "HOLD":
                pass 

            trader.log_status(current_price)
            
            time.sleep(60)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()