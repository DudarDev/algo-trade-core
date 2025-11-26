import time
import json
import sys
import os
from datetime import datetime
from colorama import Fore, Style, init
from dotenv import load_dotenv

# Додаємо папку app, щоб Python бачив наші файли
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Імпортуємо наші модулі
from app.exchange_manager import ExchangeManager
from app.strategy import Strategy
from app.paper_trader import PaperTrader
from app.csv_logger import CSVLogger
from app.chart_generator import ChartGenerator
from app.telegram_bot import TelegramBot  # <-- Використовуємо нову версію з кнопками

# Ініціалізація
init(autoreset=True)
load_dotenv()  # Завантажуємо секрети з .env

def load_config():
    """Завантажує налаштування з файлу"""
    try:
        with open('config/settings.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"❌ Помилка читання конфігу: {e}")
        sys.exit()

def run():
    # 1. Завантаження налаштувань
    cfg = load_config()
    symbol = cfg['exchange']['symbol']
    
    print(Fore.CYAN + f"🚀 ALGO PRO BOT v3.3 (Final) | {symbol}")

    # 2. Отримання ключів (безпечно)
    tg_token = os.getenv('TELEGRAM_TOKEN')
    tg_chat_id = os.getenv('TELEGRAM_CHAT_ID')

    if not tg_token:
        print(Fore.RED + "⚠️ ПОМИЛКА: Токен Telegram не знайдено в .env!")
        return

    # 3. Створення компонентів бота
    manager = ExchangeManager(cfg['exchange']['name'])
    
    strategy = Strategy(
        rsi_period=cfg['strategy']['rsi_period'],
        rsi_oversold=cfg['strategy']['buy_level'],
        rsi_overbought=cfg['strategy']['sell_level']
    )
    
    # Гаманець (паперовий трейдинг)
    trader = PaperTrader(initial_usdt=cfg['risk_management']['start_balance'])
    
    # Інструменти для звітів
    logger = CSVLogger(filename=cfg['system']['log_file'])
    artist = ChartGenerator()
    chart_path = cfg['system']['chart_file']

    # 4. Запуск Телеграм-бота (з кнопками)
    # Ми передаємо об'єкт 'trader', щоб бот міг показувати баланс
    bot = TelegramBot(token=tg_token, chat_id=tg_chat_id, trader=trader)
    
    if cfg['telegram']['enabled']:
        bot.start() # Запускаємо слухача кнопок у фоні

    buy_points = []
    sell_points = []

    print(Fore.YELLOW + "⏳ Починаю аналіз ринку... (Натисни 'СТОП' у Телеграмі для виходу)")

    # 5. Головний цикл торгівлі
    try:
        # Цикл працює, поки в боті не натиснули кнопку "СТОП"
        while bot.is_running:
            
            # Отримуємо свічки
            df = manager.get_history(symbol, timeframe=cfg['exchange']['timeframe'])
            
            if df is not None:
                current_price = df['close'].iloc[-1]
                current_time = df['time'].iloc[-1]
                
                # --- ВАЖЛИВО: Оновлюємо ціну в гаманці (для кнопки PnL) ---
                trader.set_current_price(current_price)
                
                # Аналіз стратегії
                signal, rsi_value = strategy.check_signal(df)
                now = datetime.now().strftime("%H:%M:%S")
                
                # Статистика для логу
                total_val, pnl_str = trader.get_summary(current_price)
                min_trade = cfg['risk_management']['min_trade_usdt']

                # --- ЛОГІКА ПОКУПКИ (BUY) ---
                if signal == "BUY" and trader.usdt > min_trade:
                    print(Fore.GREEN + f"[{now}] 🔥 BUY SIGNAL! RSI: {rsi_value:.1f}")
                    trader.buy(current_price)
                    
                    # Логуємо
                    logger.log_trade("BUY", current_price, trader.crypto, trader.usdt, rsi_value)
                    
                    # Малюємо графік
                    buy_points.append((current_time, current_price))
                    artist.create_chart(df, symbol, buy_points, sell_points)
                    
                    # Відправляємо фото в Телеграм
                    caption = f"🟢 **BUY {symbol}**\nЦіна: `{current_price}`\nRSI: `{rsi_value:.1f}`"
                    bot.send_image(chart_path, caption)

                # --- ЛОГІКА ПРОДАЖУ (SELL) ---
                elif signal == "SELL" and trader.crypto * current_price > min_trade:
                    print(Fore.RED + f"[{now}] 🔻 SELL SIGNAL! RSI: {rsi_value:.1f}")
                    trader.sell(current_price)
                    
                    # Логуємо
                    logger.log_trade("SELL", current_price, 0, trader.usdt, rsi_value)
                    
                    # Малюємо графік
                    sell_points.append((current_time, current_price))
                    artist.create_chart(df, symbol, buy_points, sell_points)
                    
                    # Відправляємо фото в Телеграм
                    profit_icon = "🤑" if float(pnl_str) > 0 else "🔻"
                    caption = f"🔴 **SELL {symbol}**\nЦіна: `{current_price}`\nПрибуток: {profit_icon} `{pnl_str}` USDT"
                    bot.send_image(chart_path, caption)

                # --- РЕЖИМ ОЧІКУВАННЯ ---
                elif trader.crypto * current_price > min_trade:
                    # Якщо ми в позиції (чекаємо росту)
                    print(f"[{now}] ✊ Тримаємо... Ціна: {current_price:.2f} | RSI: {rsi_value:.1f}")
                
                else:
                    # Якщо ми в доларі (чекаємо падіння)
                    print(Fore.YELLOW + f"[{now}] 💤 Пошук входу... RSI: {rsi_value:.1f}")
            
            # Пауза між перевірками (з конфігу)
            time.sleep(cfg['system']['check_interval_seconds'])

    except KeyboardInterrupt:
        print("\n👋 Зупинено через термінал (Ctrl+C).")
    
    print("🛑 Роботу завершено.")

if __name__ == "__main__":
    run()