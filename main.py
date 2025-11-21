import time
from datetime import datetime
from exchange_manager import ExchangeManager
from strategy import Strategy
from paper_trader import PaperTrader
from csv_logger import CSVLogger  # <--- Додали імпорт
from colorama import Fore, Style, init

init(autoreset=True)

SYMBOL = 'BTC/USDT'
TIMEFRAME = '1m'

def run():
    print(Fore.CYAN + f"🚀 ЗАПУСК PRO-БОТА (З ЖУРНАЛОМ) ДЛЯ {SYMBOL}...")
    
    manager = ExchangeManager('binance')
    # Стратегія для тесту (широкі межі для швидких угод)
    strategy = Strategy(rsi_period=14, rsi_oversold=45, rsi_overbought=55)
    trader = PaperTrader(initial_usdt=1000)
    logger = CSVLogger() # <--- Створили журналіста

    try:
        while True:
            df = manager.get_history(SYMBOL, timeframe=TIMEFRAME)
            
            if df is not None:
                current_price = df['close'].iloc[-1]
                signal, rsi_value = strategy.check_signal(df)
                now = datetime.now().strftime("%H:%M:%S")
                
                total_val, pnl_str = trader.get_summary(current_price)
                pnl_color = Fore.GREEN if float(pnl_str) >= 0 else Fore.RED
                
                status_line = f"| Портфель: ${total_val:.2f} ({pnl_color}{pnl_str} USDT{Style.RESET_ALL})"

                # 1. КУПІВЛЯ
                if signal == "BUY" and trader.usdt > 10:
                    print(Fore.GREEN + f"[{now}] 🔥 СИГНАЛ BUY! -> Купуємо!")
                    trader.buy(current_price)
                    
                    # Записуємо у файл
                    logger.log_trade("BUY", current_price, trader.crypto, trader.usdt, rsi_value)

                # 2. ПРОДАЖ
                elif signal == "SELL" and trader.crypto > 0.00001:
                    print(Fore.RED + f"[{now}] 🔻 СИГНАЛ SELL! -> Продаємо!")
                    trader.sell(current_price)
                    
                    # Записуємо у файл (вказуємо повний баланс у доларах)
                    logger.log_trade("SELL", current_price, 0, trader.usdt, rsi_value)

                elif trader.crypto > 0.00001:
                    print(f"[{now}] ✊ Тримаємо... {current_price} | RSI: {rsi_value:.1f} {status_line}")
                
                else:
                    print(Fore.YELLOW + f"[{now}] 💤 Пошук входу... RSI: {rsi_value:.1f}")
            
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n👋 Роботу завершено.")

if __name__ == "__main__":
    run()