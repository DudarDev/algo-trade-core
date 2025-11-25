import time
import json
import sys
import os
from datetime import datetime
from colorama import Fore, Style, init

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.exchange_manager import ExchangeManager
from app.strategy import Strategy
from app.paper_trader import PaperTrader
from app.csv_logger import CSVLogger
from app.chart_generator import ChartGenerator
# Підключаємо НОВИЙ файл
from app.telegram_bot import TelegramBot

init(autoreset=True)

def load_config():
    try:
        with open('config/settings.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"❌ Помилка конфігу: {e}")
        sys.exit()

def run():
    cfg = load_config()
    symbol = cfg['exchange']['symbol']
    
    print(Fore.CYAN + f"🚀 ALGO PRO BOT v3.0 (Interactive) | {symbol}")

    # 1. Створюємо компоненти
    manager = ExchangeManager(cfg['exchange']['name'])
    strategy = Strategy(
        rsi_period=cfg['strategy']['rsi_period'],
        rsi_oversold=cfg['strategy']['buy_level'],
        rsi_overbought=cfg['strategy']['sell_level']
    )
    # Гаманець
    trader = PaperTrader(initial_usdt=cfg['risk_management']['start_balance'])
    
    logger = CSVLogger(filename=cfg['system']['log_file'])
    artist = ChartGenerator()
    chart_path = cfg['system']['chart_file']

    # 2. Ініціалізуємо ТЕЛЕГРАМ БОТА (передаємо йому trader!)
    bot = TelegramBot(
        token=cfg['telegram']['token'], 
        chat_id=cfg['telegram']['chat_id'],
        trader=trader  # <--- Ось тут магія зв'язку
    )
    
    # 3. Запускаємо прослуховування кнопок
    if cfg['telegram']['enabled']:
        bot.start()

    buy_points = []
    sell_points = []

    try:
        # Головний цикл працює, поки в боті не натиснули "СТОП"
        while bot.is_running:
            df = manager.get_history(symbol, timeframe=cfg['exchange']['timeframe'])
            
            if df is not None:
                current_price = df['close'].iloc[-1]
                current_time = df['time'].iloc[-1]
                signal, rsi_value = strategy.check_signal(df)
                now = datetime.now().strftime("%H:%M:%S")
                
                total_val, pnl_str = trader.get_summary(current_price)
                min_trade = cfg['risk_management']['min_trade_usdt']

                # --- КУПІВЛЯ ---
                if signal == "BUY" and trader.usdt > min_trade:
                    print(Fore.GREEN + f"[{now}] 🔥 BUY! -> Купуємо!")
                    trader.buy(current_price)
                    
                    logger.log_trade("BUY", current_price, trader.crypto, trader.usdt, rsi_value)
                    
                    buy_points.append((current_time, current_price))
                    artist.create_chart(df, symbol, buy_points, sell_points)
                    
                    caption = f"🟢 **BUY {symbol}**\nЦіна: `{current_price}`\nRSI: `{rsi_value:.1f}`"
                    bot.send_image(chart_path, caption)

                # --- ПРОДАЖ ---
                elif signal == "SELL" and trader.crypto * current_price > min_trade:
                    print(Fore.RED + f"[{now}] 🔻 SELL! -> Продаємо!")
                    trader.sell(current_price)
                    
                    logger.log_trade("SELL", current_price, 0, trader.usdt, rsi_value)
                    
                    sell_points.append((current_time, current_price))
                    artist.create_chart(df, symbol, buy_points, sell_points)
                    
                    profit_icon = "🤑" if float(pnl_str) > 0 else "🔻"
                    caption = f"🔴 **SELL {symbol}**\nЦіна: `{current_price}`\nПрибуток: {profit_icon} `{pnl_str}` USDT"
                    bot.send_image(chart_path, caption)

                elif trader.crypto * current_price > min_trade:
                    print(f"[{now}] ✊ Тримаємо... {current_price} | RSI: {rsi_value:.1f}")
                
                else:
                    print(Fore.YELLOW + f"[{now}] 💤 Пошук... RSI: {rsi_value:.1f}")
            
            time.sleep(cfg['system']['check_interval_seconds'])

    except KeyboardInterrupt:
        print("\n👋 Роботу завершено вручну.")
    
    print("🛑 Бот повністю зупинився.")

if __name__ == "__main__":
    run()