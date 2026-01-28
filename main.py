import os
import time
import logging
import pandas as pd
from dotenv import load_dotenv
import ccxt

from app.ai_brain import TradingAI
from app.paper_trader import PaperTrader
from app.market_scanner import MarketScanner
from app.config import TradingConfig

# Конфігурація логування для Production
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("data/bot_runtime.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Main")

def main():
    load_dotenv()
    cfg = TradingConfig()
    logger.info("🚀 Запуск AI-трейдера v7.2 (Stable Production)")

    # Ініціалізація біржі з автоматичним контролем лімітів запитів
    exchange = ccxt.binanceus({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
        'timeout': 30000
    })
    
    ai_bot = TradingAI()
    trader = PaperTrader(initial_balance=1000.0) 
    scanner = MarketScanner()

    active_pairs = cfg.PAIRS
    last_scan_time = 0
    last_ai_check_per_pair = {symbol: 0 for symbol in active_pairs}

    while True:
        try:
            current_time = time.time()

            # --- 1. SCANNER: Оновлення ринкового фокусу (Кожні 4 години) ---
            if current_time - last_scan_time > 14400:
                logger.info("🔍 [Scanner] Оновлення списку волатильних пар...")
                try:
                    top_volatile = scanner.get_top_volatile_pairs(limit=15)
                    # Фільтруємо через чорний список та лімітуємо кількість
                    active_pairs = [p for p in top_volatile if p not in cfg.BLACKLIST][:10]
                    logger.info(f"📋 Активний список монет: {active_pairs}")
                    last_scan_time = current_time
                except Exception as e:
                    logger.error(f"❌ Scanner Error: {e}")

            # --- 2. FAST TICKER: Отримання цін одним запитом ---
            try:
                tickers = exchange.fetch_tickers(active_pairs)
            except Exception as e:
                logger.warning(f"⚠️ Помилка отримання тікерів: {e}")
                time.sleep(5)
                continue

            # --- 3. RISK & DECISION LOOP ---
            for symbol in active_pairs:
                if symbol not in tickers:
                    continue
                
                current_price = tickers[symbol]['last']
                
                # Оновлюємо стан трейдера (важливо для Trailing Stop)
                trader.update_high(symbol, current_price)

                # A. ПЕРЕВІРКА ВИХОДУ (Risk Engine)
                if symbol in trader.positions:
                    pos = trader.positions[symbol]
                    # Розраховуємо поточний PnL
                    pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
                    
                    exit_signal, reason = check_exit_conditions(pos, current_price, pnl_pct, cfg)
                    if exit_signal:
                        trader.sell(symbol, current_price, reason)
                        continue # Переходимо до наступної монети

                # B. ПЕРЕВІРКА ВХОДУ (AI Engine)
                # Перевіряємо кожну пару за власним таймером (5 хв)
                time_since_last_check = current_time - last_ai_check_per_pair.get(symbol, 0)
                if time_since_last_check > 300:
                    analyze_entry(symbol, current_price, exchange, ai_bot, trader, cfg)
                    last_ai_check_per_pair[symbol] = current_time

            # Короткий сон для запобігання перевантаженню процесора
            time.sleep(1)

        except KeyboardInterrupt:
            logger.info("🛑 Бот зупинений користувачем.")
            break
        except Exception as e:
            logger.critical(f"🚨 КРИТИЧНА ПОМИЛКА ЦИКЛУ: {e}", exc_info=True)
            time.sleep(30) # Пауза перед спробою відновлення

def check_exit_conditions(pos, price, pnl, cfg):
    """Централізована логіка виходів."""
    # 1. Stop Loss (Захист капіталу)
    if pnl < -cfg.STOP_LOSS_PCT:
        return True, "Stop Loss"
    
    # 2. Trailing Stop (Захист прибутку)
    if cfg.USE_TRAILING and pnl > cfg.TRAILING_ACTIVATION:
        drawdown = (pos["highest_price"] - price) / pos["highest_price"]
        if drawdown > cfg.TRAILING_DISTANCE:
            return True, "Trailing Stop"
            
    # 3. Take Profit (Фіксація цілі)
    if pnl >= cfg.TAKE_PROFIT_PCT:
        return True, "Take Profit"
        
    return False, None

def analyze_entry(symbol, price, exchange, ai_bot, trader, cfg):
    """Аналіз ринку через AI для відкриття нових позицій."""
    # Перевіряємо ліміт відкритих позицій
    if len(trader.positions) >= cfg.MAX_POSITIONS:
        return

    try:
        # Завантажуємо свіжі дані
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=cfg.TIMEFRAME, limit=250)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        
        # Використовуємо AI мозок для предикту
        signal = ai_bot.predict(df, symbol)
        
        if signal == "BUY":
            # Розрахунок розміру позиції
            balance = trader.get_balance()
            amount_usdt = balance * cfg.POSITION_SIZE_FRACTION
            
            # Мінімальний поріг для входу (напр. 10 USDT)
            if amount_usdt >= 10.0:
                amount_coins = amount_usdt / price
                trader.buy(symbol, price, amount_coins)
            else:
                logger.warning(f"Insufficient funds for {symbol}: {amount_usdt:.2f} USDT")
                
    except Exception as e:
        logger.error(f"❌ Помилка аналізу {symbol}: {e}")

if __name__ == "__main__":
    main()