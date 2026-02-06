import os
import time
import logging
import pandas as pd
from dotenv import load_dotenv
import ccxt

# Імпорти
from app.ai_brain import TradingAI
from app.strategy import Strategy
from app.paper_trader import PaperTrader
from app.market_scanner import MarketScanner 
from app.notifier import TelegramNotifier
from app.config import Config
from app.exchange_manager import ExchangeManager
from app.arbitrage_engine import ArbitrageEngine # <--- НОВИЙ МОДУЛЬ

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("logs/bot_runtime.log"), logging.StreamHandler()]
)
logger = logging.getLogger("Main")

def main():
    load_dotenv()
    notifier = TelegramNotifier()
    logger.info(f"🚀 Старт {Config.PROJECT_NAME} v{Config.VERSION} (Hybrid Mode)")
    
    # 1. Основна біржа для скальпінгу (Binance US)
    try:
        exchange_mgr = ExchangeManager("binanceus") 
        exchange = exchange_mgr.exchange 
    except Exception as e:
        logger.critical(f"🔥 Exchange Error: {e}")
        return

    # 2. Ініціалізація Арбітражного Двигуна
    try:
        arb_engine = ArbitrageEngine()
        logger.info("✅ Arbitrage Engine: Active")
    except Exception as e:
        logger.error(f"⚠️ Arbitrage Init Failed: {e}")
        arb_engine = None

    # Компоненти скальпера
    ai_bot = TradingAI()
    strategy = Strategy()
    trader = PaperTrader() 
    scanner = MarketScanner()

    active_pairs = Config.SYMBOLS
    last_scan_time = 0
    last_analysis_time = {symbol: 0 for symbol in active_pairs}

    notifier.send_message(f"🤖 <b>{Config.PROJECT_NAME}</b>: Скальпінг + Арбітраж активовано.")

    while True:
        try:
            current_time = time.time()

            # --- 1. SCANNER ---
            if current_time - last_scan_time > 14400:
                try:
                    logger.info("📡 Сканування ринку...")
                    new_pairs = scanner.get_top_volatile_pairs(limit=10)
                    active_positions = list(trader.positions.keys())
                    active_pairs = list(set(new_pairs + active_positions))
                    last_scan_time = current_time
                    logger.info(f"✅ Активний список: {active_pairs}")
                except Exception as e:
                    logger.error(f"❌ Scanner Error: {e}")

            # --- 2. RISK ENGINE & ARBITRAGE ---
            try:
                tickers = exchange.fetch_tickers(active_pairs)
            except Exception as e:
                logger.error(f"⚠️ API Error: {e}")
                time.sleep(5)
                continue

            for symbol in active_pairs:
                # === АРБІТРАЖНИЙ БЛОК ===
                if arb_engine:
                    try:
                        opportunity = arb_engine.find_opportunity(symbol)
                        if opportunity:
                            msg = (f"⚡ ARBITRAGE: {symbol} | Spread: {opportunity['spread']:.2f}%\n"
                                   f"🔵 BUY: {opportunity['buy_ex']} @ {opportunity['buy_price']}\n"
                                   f"🟠 SELL: {opportunity['sell_ex']} @ {opportunity['sell_price']}")
                            logger.info(msg)
                            notifier.send_message(msg)
                            # Тут можна додати логіку виконання, якщо є баланси на обох біржах
                    except Exception as e:
                        # logger.debug(f"Arb check failed for {symbol}")
                        pass

                # === СКАЛЬПІНГ БЛОК (Звичайний) ===
                try: 
                    if symbol not in tickers: continue
                    current_price = tickers[symbol]['last']
                    
                    # Risk Check
                    if symbol in trader.positions:
                        trader.check_auto_exits(symbol, current_price)
                    
                    # AI Analysis
                    if current_time - last_analysis_time.get(symbol, 0) > 300:
                        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=Config.TIMEFRAME, limit=500)
                        if not ohlcv: continue
                        
                        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                        _, ai_conf = ai_bot.predict(df, symbol)
                        df_tech = strategy.calculate_indicators(df)
                        in_pos = symbol in trader.positions
                        
                        signal, meta = strategy.get_signal(df_tech, ai_confidence=ai_conf, in_position=in_pos)
                        
                        if signal == "BUY" and not in_pos:
                            atr = meta.get('atr', 0)
                            if atr > 0:
                                trader.buy(symbol, current_price, atr)
                                notifier.send_trade_notification("BUY", symbol, current_price, trader.usdt_balance, str(meta))
                        
                        elif signal == "SELL" and in_pos:
                            trader.sell(symbol, current_price, reason=meta.get('reason', 'Signal'))
                            notifier.send_trade_notification("SELL", symbol, current_price, trader.usdt_balance, str(meta))

                        last_analysis_time[symbol] = current_time
                        time.sleep(0.5) 

                except KeyError as e:
                    # Zombie-Killer (залишаємо, бо він працює!)
                    if 'stop_loss' in str(e):
                        logger.warning(f"🧹 ВИДАЛЕННЯ ПОШКОДЖЕНОЇ ПОЗИЦІЇ {symbol}...")
                        if symbol in trader.positions:
                            del trader.positions[symbol]
                            logger.info(f"✅ Позицію {symbol} успішно видалено. Бот продовжує роботу.")
                except Exception as e:
                    logger.error(f"❌ Error {symbol}: {e}")
                    continue 

            time.sleep(1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.critical(f"🔥 CRITICAL: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()