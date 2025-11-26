import pandas as pd
import sys
import os
from colorama import Fore, Style, init

# Додаємо папку app, щоб бачити стратегію
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.strategy import Strategy

init(autoreset=True)

def run_backtest(file_path, rsi_period=14, buy_level=30, sell_level=70, start_balance=1000):
    """
    Симуляція торгівлі на історичних даних
    """
    print(Fore.CYAN + f"🔄 Запуск бектесту на файлі: {file_path}")
    print(f"⚙️  Налаштування: RSI={rsi_period} | BUY<{buy_level} | SELL>{sell_level}")
    
    # 1. Завантажуємо дані
    if not os.path.exists(file_path):
        print(Fore.RED + f"❌ Файл {file_path} не знайдено! Спочатку запусти download_data.py")
        return

    df = pd.read_csv(file_path)
    
    # 2. Ініціалізуємо стратегію
    strategy = Strategy(
        rsi_period=rsi_period, 
        rsi_oversold=buy_level, 
        rsi_overbought=sell_level
    )

    # 3. Гаманець симулятора
    usdt = start_balance
    crypto = 0
    trades_count = 0
    
    # Початкова ціна (для розрахунку Hold стратегії)
    start_price = df['close'].iloc[0]

    print("⏳ Обробка даних...", end="")

    # 4. Проганяємо цикл (Швидкий метод)
    # Спочатку рахуємо RSI для всього файлу одразу (це дуже швидко)
    df = strategy.calculate_rsi(df)

    # Тепер йдемо по рядках
    for i in range(len(df)):
        if i < rsi_period: continue # Пропускаємо перші рядки без RSI
        
        price = df['close'].iloc[i]
        rsi = df['rsi'].iloc[i]
        
        # ЛОГІКА ТОРГІВЛІ (Спрощена для швидкості)
        
        # КУПІВЛЯ: Якщо RSI низький І у нас є USDT
        if rsi < buy_level and usdt > 10:
            crypto = usdt / price
            usdt = 0
            trades_count += 1
            # print(f"  🟢 BUY at {price} (RSI: {rsi:.1f})") # Можна розкоментувати для деталізації

        # ПРОДАЖ: Якщо RSI високий І у нас є Крипта
        elif rsi > sell_level and crypto > 0:
            usdt = crypto * price
            crypto = 0
            trades_count += 1
            # print(f"  🔴 SELL at {price} (RSI: {rsi:.1f})")

    print(" Готово!\n")

    # 5. Підсумки
    final_price = df['close'].iloc[-1]
    
    # Якщо залишились у крипті - продаємо по останній ціні, щоб порахувати баланс
    if crypto > 0:
        usdt = crypto * final_price

    total_pnl = usdt - start_balance
    pnl_percent = (total_pnl / start_balance) * 100

    # Порівняння з "Buy & Hold" (просто купив і тримав)
    hold_crypto = start_balance / start_price
    hold_usdt = hold_crypto * final_price
    hold_pnl = hold_usdt - start_balance
    hold_percent = (hold_pnl / start_balance) * 100

    # Вивід результатів
    print("="*40)
    print(Fore.YELLOW + "📊 РЕЗУЛЬТАТИ БЕКТЕСТУ")
    print("="*40)
    print(f"💰 Початковий баланс: ${start_balance}")
    print(f"💵 Кінцевий баланс:   ${usdt:.2f}")
    
    color = Fore.GREEN if total_pnl > 0 else Fore.RED
    print(f"📈 Чистий прибуток:   {color}${total_pnl:.2f} ({pnl_percent:.2f}%){Style.RESET_ALL}")
    print(f"🔄 Кількість угод:    {trades_count}")
    
    print("-" * 40)
    print(f"🐢 Стратегія 'Тримати' (Buy&Hold): {hold_percent:.2f}%")
    
    if pnl_percent > hold_percent:
        print(Fore.GREEN + "🏆 БОТ ПЕРЕМІГ РИНОК!")
    else:
        print(Fore.RED + "🐢 'Тримати' було вигідніше.")
    print("="*40)

if __name__ == "__main__":
    # Налаштування для тесту
    FILE = "data/BTC_USDT_history.csv"
    
    # Спробуй змінити ці цифри, щоб покращити результат!
    run_backtest(FILE, rsi_period=14, buy_level=30, sell_level=70)