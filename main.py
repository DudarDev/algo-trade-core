import os
import time
import logging
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ccxt

from app.ai_brain import TradingAI
from app.strategy import Strategy
from app.paper_trader import PaperTrader
from app.market_scanner import MarketScanner 
from app.notifier import TelegramNotifier
from app.config import Config
from app.exchange_manager import ExchangeManager
from app.arbitrage_engine import ArbitrageEngine
from app.auto_pruner import AutoPruner  

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler("logs/bot_runtime.log"), logging.StreamHandler()]
)
logger = logging.getLogger("Main")

# 🔥 Глобальний список сміттєвих монет (Стейблкоїни, Золото, Фіат)
IGNORE_LIST = {'USDC/USDT', 'TUSD/USDT', 'FDUSD/USDT', 'BUSD/USDT', 'EUR/USDT', 'PAXG/USDT', 'USDP/USDT'}
DAILY_LOSS_LIMIT = 0.03  # 3% максимальна просадка за добу

def main():
    load_dotenv()
    notifier = TelegramNotifier()
    logger.info(f"🚀 Старт {Config.PROJECT_NAME} v{Config.VERSION} (Hybrid Mode + MTFA + AutoPruner + RiskShield)")
    
    try:
        exchange_mgr = ExchangeManager("binanceus") 
        exchange = exchange_mgr.exchange 
    except Exception as e:
        logger.critical(f"🔥 Exchange Error: {e}")
        return

    try:
        arb_engine = ArbitrageEngine()
        logger.info("✅ Arbitrage Engine: Active")
    except Exception as e:
        arb_engine = None

    ai_bot = TradingAI()
    strategy = Strategy()
    trader = PaperTrader() 
    scanner = MarketScanner()
    pruner = AutoPruner()  

    # 🔥 Фільтруємо навіть початковий конфіг, щоб стейблкоїни не пролізли на старті
    active_pairs = [p for p in Config.SYMBOLS if p not in IGNORE_LIST]
    
    last_scan_time = 0
    last_prune_time = 0
    last_analysis_time = {symbol: 0 for symbol in active_pairs}

    # 🔥 Змінні для Daily Loss Limit
    current_date = datetime.now().date()
    # Намагаємось отримати баланс безпечно (залежить від реалізації trader)
    daily_start_balance = getattr(trader, 'balance', 1000.0) 

    notifier.send_message(f"🤖 <b>{Config.PROJECT_NAME}</b>: Скальпінг активовано. AutoPruner та Daily Loss Limit (3%) увімкнено 🛡️")

    while True:
        try:
            current_time = time.time()
            now_dt = datetime.now()

            # --- 0. DAILY RISK SHIELD (Оновлення доби та перевірка просадки) ---
            if now_dt.date() > current_date:
                current_date = now_dt.date()
                daily_start_balance = getattr(trader, 'balance', daily_start_balance)
                logger.info(f"🔄 Новий торговий день. Баланс зафіксовано: {daily_start_balance}")

            current_balance = getattr(trader, 'balance', daily_start_balance)
            drawdown = (current_balance - daily_start_balance) / daily_start_balance

            if drawdown <= -DAILY_LOSS_LIMIT:
                msg = f"🚨 ЕКСТРЕНА ЗУПИНКА: Денний ліміт втрат перевищено ({drawdown*100:.2f}%). Торги призупинено до кінця доби."
                logger.critical(msg)
                notifier.send_message(msg)
                
                # Вираховуємо час до опівночі і відправляємо бота спати
                tomorrow = now_dt + timedelta(days=1)
                midnight = datetime(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day, hour=0, minute=0, second=0)
                seconds_to_sleep = (midnight - now_dt).seconds
                logger.info(f"💤 Бот переходить у режим сну на {seconds_to_sleep} секунд...")
                time.sleep(seconds_to_sleep)
                
                # Після сну оновлюємо стартовий баланс
                daily_start_balance = getattr(trader, 'balance', current_balance)
                continue # Починаємо новий день

            # --- 1. AUTO-PRUNER (Раз на добу: 86400 сек) ---
            if current_time - last_prune_time > 86400:
                logger.info("🕵️‍♂️ Запуск AutoPruner: аналіз ефективності монет...")
                pruner.update_blacklist(min_trades=5, min_win_rate=35.0)
                last_prune_time = current_time

            # --- 2. SCANNER (Раз на 30 хвилин: 1800 сек) ---
            if current_time - last_scan_time > 1800:
                try:
                    logger.info("📡 Сканування ринку...")
                    raw_new_pairs = scanner.get_top_volatile_pairs(limit=20)
                    
                    # 🔥 Відсікаємо сміття відразу
                    new_pairs = [p for p in raw_new_pairs if p not in IGNORE_LIST][:10]

                    active_positions = list(trader.positions.keys())
                    raw_active = set(new_pairs + active_positions)
                    
                    # Залишаємо монети, яких немає в Blacklist (або якщо по них вже відкрита позиція)
                    active_pairs = [p for p in raw_active if p not in pruner.blacklist or p in active_positions]
                    
                    last_scan_time = current_time
                    logger.info(f"✅ Активний список: {active_pairs}")
                except Exception as e:
                    logger.error(f"❌ Scanner Error: {e}")

            # --- 3. RISK ENGINE & EXECUTION ---
            try:
                tickers = exchange.fetch_tickers(active_pairs)
            except Exception as e:
                time.sleep(5)
                continue

            for symbol in active_pairs:
                # Arbitrage Logic
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

                try: 
                    if symbol not in tickers: continue
                    current_price = tickers[symbol]['last']
                    
                    # Перевірка виходів (AI-Exit, SL, TP)
                    if symbol in trader.positions:
                        trader.check_auto_exits(symbol, current_price)
                    
                    # Аналіз та входи (Раз на 60 сек)
                    if current_time - last_analysis_time.get(symbol, 0) > 60:
                        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=Config.TIMEFRAME, limit=500)
                        if not ohlcv: continue
                        
                        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                        
                        # 🔥 ШІ робить прогноз
                        _, ai_conf = ai_bot.predict(df, symbol)
                        
                        # 🔥 Оновлюємо впевненість для відкритої позиції (для AI-Exit)
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
                                    logger.info(f"✅ Вхід дозволено: Глобальний тренд {symbol} висхідний. Conf: {ai_conf:.2f}")
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
            logger.info("🛑 Зупинка бота користувачем...")
            break
        except Exception as e:
            logger.error(f"⚠️ Глобальна помилка циклу: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()