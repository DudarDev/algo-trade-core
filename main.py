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

# --- CONFIGURATION v6.7 (PROD) ---
# Чорний список (Стейбли та фіат)
BLACKLIST_PAIRS = [
    'USDC/USDT', 'USDP/USDT', 'TUSD/USDT', 'FDUSD/USDT', 'DAI/USDT', 
    'BUSD/USDT', 'EUR/USDT', 'GBP/USDT', 'USDC/USD', 'USDT/USD'
]

# Захист від комісій (Binance/Bybit Standard ~0.1% per side)
COMMISSION_RATE = 0.002    # 0.2% сумарно (вхід + вихід)
MIN_NET_PROFIT = 0.005     # 0.5% чистого прибутку для Take Profit

def filter_pairs(pairs):
    """Видаляє сміттєві пари зі списку"""
    return [p for p in pairs if p not in BLACKLIST_PAIRS]

def main():
    load_dotenv()
    print(f"🚀 Запуск AI-трейдера v6.7 (FULL POWER + Anti-Fee)...")

    exchange = ccxt.binanceus()
    ai_bot = TradingAI()
    trader = PaperTrader(initial_balance=1000.0)
    scanner = MarketScanner()

    # Стартовий список (фільтруємо одразу)
    active_pairs = filter_pairs(config.PAIRS)
    
    # ТАЙМЕРИ
    last_scan_time = 0
    last_ai_check_time = 0
    
    SCAN_INTERVAL = 4 * 60 * 60  # Сканування ринку раз на 4 години
    AI_INTERVAL = 300            # Аналіз AI раз на 5 хвилин
    CHECK_INTERVAL = 5           # Перевірка стопів кожні 5 секунд (швидше, бо сервер потужний)

    tg = None
    if tg_available:
        try:
            tg = TelegramInterface(trader)
            tg.send_alert("🚀 Bot v6.7 (e2-medium) Active. Full Power Mode.")
        except:
            tg = None

    while True:
        try:
            current_time = time.time()

            # --- 1. SCANNER (Global Market Check) ---
            if current_time - last_scan_time > SCAN_INTERVAL:
                logging.info("🔍 Сканую ринок...")
                # FULL POWER: Беремо топ-10 волатильних пар
                raw_pairs = scanner.get_top_volatile_pairs(limit=10)
                
                new_pairs = filter_pairs(raw_pairs)
                
                if new_pairs:
                    active_pairs = new_pairs
                    logging.info(f"📋 Нові активні пари: {active_pairs}")
                    if tg and tg.is_running:
                        tg.send_alert(f"🔄 Ринок змінився. Торгуємо: {active_pairs}")
                last_scan_time = current_time

            # --- 2. FAST LOOP (Stop Loss & Take Profit) ---
            for symbol in active_pairs:
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                except Exception as e:
                    logging.error(f"Error fetching ticker for {symbol}: {e}")
                    continue

                # Оновлюємо хай для Trailing Stop
                trader.update_high(symbol, current_price)

                if symbol in trader.positions:
                    pos = trader.positions[symbol]
                    entry = pos["entry_price"]
                    high = pos["highest_price"]

                    # PnL Розрахунки
                    raw_pnl = (current_price - entry) / entry
                    net_pnl = raw_pnl - COMMISSION_RATE # Чистий прибуток
                    drawdown = (high - current_price) / high

                    should_sell = False
                    reason = ""

                    # A. HARD STOP LOSS (Аварійний вихід)
                    if raw_pnl < -config.STOP_LOSS_PCT:
                        should_sell = True
                        reason = f"Stop Loss ({raw_pnl*100:.2f}%)"
                    
                    # B. SMART TAKE PROFIT (Забираємо гроші, якщо є чистий профіт)
                    elif net_pnl >= MIN_NET_PROFIT:
                        should_sell = True
                        reason = f"Take Profit (Net +{net_pnl*100:.2f}%)"

                    # C. TRAILING STOP
                    elif config.USE_TRAILING_STOP and raw_pnl > config.TRAILING_START_PCT:
                        if drawdown > config.TRAILING_DROP_PCT:
                            # Продаємо, навіть якщо комісія з'їсть частину, щоб зберегти те, що є
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
                    try:
                        # Завантажуємо свічки для AI
                        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=config.TIMEFRAME, limit=1000)
                        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                    except:
                        continue

                    if not ai_bot.is_trained:
                        ai_bot.train_new_model(df, symbol)

                    signal = ai_bot.predict(df)
                    
                    # Логіка виходу по AI (Smart Exit)
                    if symbol in trader.positions and signal == "SELL":
                        entry_price = trader.positions[symbol]["entry_price"]
                        raw_pnl = (current_price - entry_price) / entry_price
                        
                        # AI не має права продавати в мінус або в нуль (тільки якщо покрили комісію)
                        if raw_pnl > COMMISSION_RATE: 
                            trader.sell(symbol, current_price, "AI Signal (Profit)")
                            if tg and tg.is_running:
                                tg.send_alert(f"🤖 AI SELL {symbol} (Profit Secured)")

                    # Логіка входу (BUY)
                    elif signal == "BUY":
                        if len(trader.positions) < config.MAX_POSITIONS:
                            if symbol not in trader.positions:
                                trader.buy(symbol, current_price, config.TRADE_AMOUNT)
                                if tg and tg.is_running:
                                    tg.send_alert(f"🟢 BUY {symbol} @ {current_price}")

            # Оновлюємо таймер AI
            if current_time - last_ai_check_time > AI_INTERVAL:
                last_ai_check_time = current_time

            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            print("🛑 Stopping bot...")
            break
        except Exception as e:
            logging.error(f"Global Error: {e}")
            time.sleep(5) # Пауза при помилці трохи менша, бо сервер швидкий

if __name__ == "__main__":
    main()