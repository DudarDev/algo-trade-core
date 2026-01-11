import os
import time
import pandas as pd
from dotenv import load_dotenv
import logging
import ccxt

from app.ai_brain import TradingAI
from app.paper_trader import PaperTrader
from app.market_scanner import MarketScanner
import app.config as config

try:
    from app.telegram_interface import TelegramInterface
    tg_available = True
except ImportError:
    tg_available = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# --- CONFIGURATION v6.8 (PROD + FIXES) ---
BLACKLIST_PAIRS = [
    'USDC/USDT', 'USDP/USDT', 'TUSD/USDT', 'FDUSD/USDT', 'DAI/USDT', 
    'BUSD/USDT', 'EUR/USDT', 'GBP/USDT', 'USDC/USD', 'USDT/USD'
]

COMMISSION_RATE = 0.002    # 0.2% сумарно
MIN_NET_PROFIT = 0.005     # 0.5% чистого прибутку

def filter_pairs(pairs):
    return [p for p in pairs if p not in BLACKLIST_PAIRS]

def main():
    load_dotenv()
    print(f"🚀 Запуск AI-трейдера v6.8 (FINAL STABLE)...")

    exchange = ccxt.binanceus()
    ai_bot = TradingAI()
    trader = PaperTrader(initial_balance=1000.0)
    scanner = MarketScanner()

    active_pairs = filter_pairs(config.PAIRS)
    
    last_scan_time = 0
    last_ai_check_time = 0
    
    SCAN_INTERVAL = 4 * 60 * 60 
    AI_INTERVAL = 300            
    CHECK_INTERVAL = 5           

    tg = None
    if tg_available:
        try:
            tg = TelegramInterface(trader)
            tg.send_alert("🚀 Bot v6.8 Active. Ready to trade.")
        except:
            tg = None

    while True:
        try:
            current_time = time.time()

            # --- 1. SCANNER (Global Market Check) ---
            if current_time - last_scan_time > SCAN_INTERVAL:
                logging.info("🔍 Сканую ринок...")
                try:
                    raw_pairs = scanner.get_top_volatile_pairs(limit=10)
                    new_pairs = filter_pairs(raw_pairs)
                    
                    # FIXED: Оновлюємо тільки якщо знайшли пари
                    if new_pairs:
                        active_pairs = new_pairs
                        logging.info(f"📋 Нові активні пари: {active_pairs}")
                        if tg and tg.is_running:
                            tg.send_alert(f"🔄 Ринок змінився. Торгуємо: {active_pairs}")
                except Exception as e:
                    logging.error(f"Scanner error: {e}")
                
                last_scan_time = current_time

            # --- 2. FAST LOOP (Stop Loss & Take Profit) ---
            # OPTIMIZED: Один запит замість 10
            try:
                tickers = exchange.fetch_tickers(active_pairs)
            except Exception as e:
                logging.error(f"Tickers fetch error: {e}")
                time.sleep(5)
                continue

            for symbol in active_pairs:
                if symbol not in tickers: continue
                
                current_price = tickers[symbol]['last']
                
                # Оновлюємо хай для Trailing Stop
                trader.update_high(symbol, current_price)

                if symbol in trader.positions:
                    pos = trader.positions[symbol]
                    entry = pos["entry_price"]
                    high = pos["highest_price"]

                    raw_pnl = (current_price - entry) / entry
                    net_pnl = raw_pnl - COMMISSION_RATE
                    drawdown = (high - current_price) / high

                    should_sell = False
                    reason = ""

                    # A. HARD STOP LOSS
                    if raw_pnl < -config.STOP_LOSS_PCT:
                        should_sell = True
                        reason = f"Stop Loss ({raw_pnl*100:.2f}%)"
                    
                    # B. SMART TAKE PROFIT
                    elif net_pnl >= MIN_NET_PROFIT:
                        should_sell = True
                        reason = f"Take Profit (Net +{net_pnl*100:.2f}%)"

                    # C. TRAILING STOP
                    elif config.USE_TRAILING_STOP and raw_pnl > config.TRAILING_START_PCT:
                        if drawdown > config.TRAILING_DROP_PCT:
                            should_sell = True
                            reason = f"Trailing Exit ({raw_pnl*100:.2f}%)"

                    if should_sell:
                        trader.sell(symbol, current_price, reason)
                        if tg and tg.is_running:
                            new_bal = trader.get_balance()
                            tg.send_alert(f"💰 SELL {symbol} @ {current_price}\nReason: {reason}\n💵 Bal: {new_bal}")
                        continue 

            # --- 3. SLOW LOOP (AI Analysis) ---
            if current_time - last_ai_check_time > AI_INTERVAL:
                logging.info(f"🧠 AI аналізує {len(active_pairs)} пар...")
                
                for symbol in active_pairs:
                    try:
                        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=config.TIMEFRAME, limit=1000)
                        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                        
                        if not ai_bot.is_trained:
                            ai_bot.train_new_model(df, symbol)

                        # --- FIXED: CRITICAL AI FIX ---
                        # Видаляємо останній рядок (незакриту свічку),
                        # щоб AI не бачив RVOL=0 і не думав, що ринок стоїть.
                        # Ми аналізуємо останню ПОВНІСТЮ ЗАКРИТУ свічку.
                        completed_df = df.iloc[:-1] 
                        
                        signal = ai_bot.predict(completed_df)
                        # ------------------------------
                        
                        if symbol in trader.positions and signal == "SELL":
                            entry_price = trader.positions[symbol]["entry_price"]
                            raw_pnl = (tickers[symbol]['last'] - entry_price) / entry_price
                            
                            # Продаємо по AI, тільки якщо ми хоча б покрили комісію
                            if raw_pnl > COMMISSION_RATE: 
                                trader.sell(symbol, tickers[symbol]['last'], "AI Signal (Profit)")
                                if tg and tg.is_running:
                                    tg.send_alert(f"🤖 AI SELL {symbol} (Profit Secured)")

                        elif signal == "BUY":
                            # Перевіряємо, чи немає вже позиції
                            if symbol not in trader.positions and len(trader.positions) < config.MAX_POSITIONS:
                                trader.buy(symbol, tickers[symbol]['last'], config.TRADE_AMOUNT)
                                if tg and tg.is_running:
                                    tg.send_alert(f"🟢 BUY {symbol} @ {tickers[symbol]['last']}")
                    
                    except Exception as e:
                        logging.error(f"AI Check Error for {symbol}: {e}")
                        continue

                last_ai_check_time = current_time

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("🛑 Stopping bot...")
            break
        except Exception as e:
            logging.error(f"Global Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()