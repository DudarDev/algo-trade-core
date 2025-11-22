import time
import json
import sys
import os
from datetime import datetime
from colorama import Fore, Style, init

# Додаємо папку поточного проекту в шляхи пошуку, щоб бачити папку app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Тепер імпортуємо з папки app
from app.exchange_manager import ExchangeManager
from app.strategy import Strategy
from app.paper_trader import PaperTrader
from app.csv_logger import CSVLogger
from app.chart_generator import ChartGenerator

init(autoreset=True)

def load_config():
    """Завантажує налаштування з JSON файлу"""
    try:
        with open('config/settings.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(Fore.RED + f"❌ Помилка читання конфігу (config/settings.json): {e}")
        sys.exit()

def run():
    # 1. Завантаження конфігурації
    cfg = load_config()
    
    symbol = cfg['exchange']['symbol']
    print(Fore.CYAN + f"""
    ╔══════════════════════════════════════╗
    ║       CRYPTO ALGO PRO BOT v2.0       ║
    ║       Target: {symbol:<16}       ║
    ╚══════════════════════════════════════╝
    """)

    # 2. Ініціалізація модулів з параметрами з JSON
    manager = ExchangeManager(cfg['exchange']['name'])
    
    strategy = Strategy(
        rsi_period=cfg['strategy']['rsi_period'],
        rsi_oversold=cfg['strategy']['buy_level'],
        rsi_overbought=cfg['strategy']['sell_level']
    )
    
    trader = PaperTrader(initial_usdt=cfg['risk_management']['start_balance'])
    
    # Передаємо шлях до файлу з конфігу
    logger = CSVLogger(filename=cfg['system']['log_file'])
    artist = ChartGenerator() 

    buy_points = []
    sell_points = []

    print(f"⚙️  Стратегія завантажена: RSI ({cfg['strategy']['rsi_period']})")
    print(f"   BUY < {cfg['strategy']['buy_level']} | SELL > {cfg['strategy']['sell_level']}\n")

    try:
        while True:
            # Використовуємо таймфрейм з конфігу
            df = manager.get_history(symbol, timeframe=cfg['exchange']['timeframe'])
            
            if df is not None:
                current_price = df['close'].iloc[-1]
                current_time = df['time'].iloc[-1]
                
                signal, rsi_value = strategy.check_signal(df)
                now = datetime.now().strftime("%H:%M:%S")
                
                total_val, pnl_str = trader.get_summary(current_price)
                pnl_color = Fore.GREEN if float(pnl_str) >= 0 else Fore.RED
                status_line = f"| 💼 Портфель: ${total_val:.2f} ({pnl_color}{pnl_str} USDT{Style.RESET_ALL})"

                # ЛОГІКА (використовуємо мін. суму з конфігу)
                min_trade = cfg['risk_management']['min_trade_usdt']

                if signal == "BUY" and trader.usdt > min_trade:
                    print(Fore.GREEN + f"[{now}] 🔥 СИГНАЛ BUY! -> Купуємо!")
                    trader.buy(current_price)
                    logger.log_trade("BUY", current_price, trader.crypto, trader.usdt, rsi_value)
                    buy_points.append((current_time, current_price))
                    # Малюємо графік у папку data
                    artist.create_chart(df, symbol, buy_points, sell_points)

                elif signal == "SELL" and trader.crypto * current_price > min_trade:
                    print(Fore.RED + f"[{now}] 🔻 СИГНАЛ SELL! -> Продаємо!")
                    trader.sell(current_price)
                    logger.log_trade("SELL", current_price, 0, trader.usdt, rsi_value)
                    sell_points.append((current_time, current_price))
                    artist.create_chart(df, symbol, buy_points, sell_points)

                elif trader.crypto * current_price > min_trade:
                    print(f"[{now}] ✊ Тримаємо... {current_price} | RSI: {rsi_value:.1f} {status_line}")
                
                else:
                    print(Fore.YELLOW + f"[{now}] 💤 Пошук входу... RSI: {rsi_value:.1f}")
            
            # Пауза з конфігу
            time.sleep(cfg['system']['check_interval_seconds'])

    except KeyboardInterrupt:
        print("\n👋 Роботу завершено.")

if __name__ == "__main__":
    run()