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
from app.arbitrage_engine import ArbitrageEngine
from app.auto_pruner import AutoPruner  # 🔥 НОВЕ: Імпортуємо модуль очищення

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
    logger.info(f"🚀 Старт {Config.PROJECT_NAME} v{Config.VERSION} (Hybrid Mode + MTFA + AutoPruner)")
    
    # 1. Основна біржа для скальпінгу
    try:
        exchange_mgr = ExchangeManager("binanceus") 
        exchange = exchange_mgr.exchange 
    except Exception as e:
        logger.critical(f"🔥 Exchange Error: {e}")
        return

    # 2. Арбітраж
    try:
        arb_engine = ArbitrageEngine()
        logger.info("✅ Arbitrage Engine: Active")
    except Exception as e:
        arb_engine = None

    # Компоненти бота
    ai_bot = TradingAI()
    strategy = Strategy()
    trader = PaperTrader() 
    scanner = MarketScanner()
    pruner = AutoPruner()  # 🔥 НОВЕ: Ініціалізуємо Прунер

    active_pairs = Config.SYMBOLS
    last_scan_time = 0
    last_prune_time = 0  # 🔥 НОВЕ: Таймер для очищення
    last_analysis_time = {symbol: 0 for symbol in active_pairs}

    notifier.send_message(f"🤖 <b>{Config.PROJECT_NAME}</b>: Скальпінг активовано. AutoPruner увімкнено 🧹")

    while True:
        try:
            current_time = time.time()

            # --- 🔥 НОВЕ: 1. AUTO-PRUNER (Раз на добу) ---
            if current_time - last_prune_time > 86400:  # 86400 секунд = 24 години
                logger.info("🕵️‍♂️ Запуск AutoPruner: аналіз ефективності монет...")
                pruner.update_blacklist(min_trades=5, min_win_rate=35.0)
                last_prune_time = current_time

            # --- 2. SCANNER (Раз на 30 хвилин) ---
            if current_time - last_scan_time > 1800:
                try:
                    logger.info("📡 Сканування ринку...")
                    new_pairs = scanner.get_top_volatile_pairs(limit=10)
                    active_positions = list(trader.positions.keys())
                    
                    # 🔥 Об'єднуємо списки, АЛЕ викидаємо монети з Чорного списку (якщо вони не у відкритій позиції)
                    raw_active = set(new_pairs + active_positions)
                    active_pairs = [p for p in raw_active if p not in pruner.blacklist or p in active_positions]
                    
                    last_scan_time = current_time
                    logger.info(f"✅ Активний список: {active_pairs}")
                except Exception as e:
                    logger.error(f"❌ Scanner Error: {e}")

            # --- 3. RISK ENGINE & EXECUTION ---
            try:
                tickers = exchange.fetch_tickers(active_pairs)
            except Exception as e:
                logger.error(f"⚠️ API Error: {e}")
                time.sleep(5)
                continue

            for symbol in active_pairs:
                # === АРБІТРАЖ ===
                if arb_engine:
                    try:
                        opportunity = arb_engine.find_opportunity(symbol)
                        if opportunity:
                            msg = (f"⚡ ARBITRAGE: {symbol} | Spread: {opportunity['spread']:.2f}%\n"
                                   f"🔵 BUY: {opportunity['buy_ex']} @ {opportunity['buy_price']}\n"
                                   f"🟠 SELL: {opportunity['sell_ex']} @ {opportunity['sell_price']}")
                            notifier.send_message(msg)
                    except:
                        pass

                # === СКАЛЬПІНГ ===
                try: 
                    if symbol not in tickers: continue
                    current_price = tickers[symbol]['last']
                    
                    if symbol in trader.positions:
                        trader.check_auto_exits(symbol, current_price)
                    
                    if current_time - last_analysis_time.get(symbol, 0) > 60:
                        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=Config.TIMEFRAME, limit=500)
                        if not ohlcv: continue
                        
                        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                        
                        _, ai_conf = ai_bot.predict(df, symbol)
                        
                        if symbol in trader.positions:
                            trader.update_position_confidence(symbol, ai_conf)
                            
                        df_tech = strategy.calculate_indicators(df)
                        in_pos = symbol in trader.positions
                        
                        signal, meta = strategy.get_signal(df_tech, ai_confidence=ai_conf, in_position=in_pos)
                        
                        if signal == "BUY" and not in_pos:
                            is_global_uptrend = strategy.check_global_trend(exchange, symbol)
                            
                            if is_global_uptrend:
                                atr = meta.get('atr', 0)
                                if atr > 0:
                                    trader.buy(symbol, current_price, atr, reason=f"AI Conf: {ai_conf:.2f}", ai_conf=ai_conf)
                                    logger.info(f"✅ Вхід дозволено: Глобальний тренд {symbol} висхідний.")
                            else:
                                logger.info(f"⛔ Вхід скасовано: Глобальний тренд {symbol} спадний.")
                        
                        elif signal == "SELL" and in_pos:
                            trader.sell(symbol, current_price, reason=meta.get('reason', 'Signal'))

                        last_analysis_time[symbol] = current_time
                        time.sleep(0.1) 

                except KeyError as e:
                    if 'stop_loss' in str(e):
                        if symbol in trader.positions: del trader.positions[symbol]
                except Exception as e:
                    continue 

            time.sleep(1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(30)

if __name__ == "__main__":
    main()