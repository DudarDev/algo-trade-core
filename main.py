import os
import time
import pandas as pd
from dotenv import load_dotenv
import logging
import ccxt

from app.ai_brain import TradingAI
from app.paper_trader import PaperTrader
from app.notifier import TelegramNotifier
import app.config as config  # Імпортуємо наш конфіг

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_data(exchange, symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=config.TIMEFRAME, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        return price, df
    except:
        return None, pd.DataFrame()

def main():
    load_dotenv()
    
    print(f"🇺🇸 Підключення до Binance US. Стратегія: Trailing Stop.")
    exchange = ccxt.binanceus() 
    
    ai_bot = TradingAI()
    trader = PaperTrader(initial_balance=1000.0)
    notify = TelegramNotifier()
    
    notify.send("🚀 Bot Restarted with Trailing Stop Logic")

    while True:
        try:
            current_prices = {}
            
            for symbol in config.PAIRS:
                price, df = get_data(exchange, symbol)
                if price is None or df.empty: continue
                
                current_prices[symbol] = price

                # 1. Оновлюємо максимум для трейлінгу
                trader.update_high(symbol, price)

                # 2. Тренування
                if not ai_bot.is_trained:
                     ai_bot.train_new_model(df)

                # 3. Аналіз AI
                signal = ai_bot.predict(df)
                
                # 4. Вхід в угоду
                if signal == "BUY":
                    if len(trader.positions) < config.MAX_POSITIONS:
                        trader.buy(symbol, price, config.TRADE_AMOUNT)
                        if symbol in trader.positions:
                            notify.send_trade("BUY", symbol, price, config.TRADE_AMOUNT)

                # 5. ВИХІД (Trailing Stop Logic)
                if symbol in trader.positions:
                    pos = trader.positions[symbol]
                    entry_price = pos['entry_price']
                    highest_price = pos['highest_price']
                    
                    # Поточний % зміни
                    pnl_current = (price - entry_price) / entry_price
                    # Відкат від максимуму
                    drawdown = (highest_price - price) / highest_price
                    
                    should_sell = False
                    reason = ""

                    # А. Stop Loss (Аварійний вихід)
                    if pnl_current < -config.STOP_LOSS_PCT:
                        should_sell = True
                        reason = "Stop Loss 🛡️"
                    
                    # Б. Trailing Take Profit (Розумний вихід)
                    elif config.USE_TRAILING_STOP and pnl_current > config.TRAILING_START_PCT:
                        # Якщо ціна почала падати від піку більше ніж на DROP_PCT
                        if drawdown > config.TRAILING_DROP_PCT:
                            should_sell = True
                            reason = f"Trailing Stop (High: {highest_price}) 🎣"
                    
                    # В. Звичайний Take Profit (якщо трейлінг вимкнено)
                    elif not config.USE_TRAILING_STOP and pnl_current > config.TAKE_PROFIT_PCT:
                        should_sell = True
                        reason = "Take Profit 💰"

                    # Г. AI Exit (Тільки якщо є мінімальний плюс, щоб відбити комісію)
                    elif signal == "SELL" and pnl_current > 0.002:
                         should_sell = True
                         reason = "AI Signal 🤖"

                    if should_sell:
                        trader.sell(symbol, price, reason)
                        new_bal = trader.get_balance()
                        notify.send_trade("SELL", symbol, price, 0, pnl_current*100, new_bal)

                time.sleep(1)

            if trader.positions:
                trader.log_status(current_prices)
            
            time.sleep(300) # 5 хвилин пауза
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()