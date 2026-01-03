import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np

# Налаштування для перевірки
TIMEFRAME = "5m"
PAIRS = ["BTC/USDT", "SOL/USDT", "ETH/USDT"]  # Тільки сильні монети


def run_smart_backtest(symbol, tp, sl, trail_on):
    exchange = ccxt.binanceus()
    # Качаємо більше даних (5 днів)
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=1500)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])

    # --- ІМІТАЦІЯ МОЗКУ AI ---
    # 1. Тренд (SMA 200)
    df["SMA_200"] = ta.sma(df["close"], length=200)
    # 2. Імпульс (RSI)
    df["RSI"] = ta.rsi(df["close"], length=14)
    # 3. Напрямок (MACD)
    macd = ta.macd(df["close"])
    df["MACD"] = macd["MACD_12_26_9"]

    balance = 1000
    position = None
    trades = 0
    wins = 0

    # Починаємо з 200-ї свічки (щоб SMA порахувалась)
    for i in range(200, len(df)):
        price = df["close"].iloc[i]

        # Поточні індикатори
        rsi = df["RSI"].iloc[i]

        # Перевірка на існування SMA (захист від NaN)
        sma_val = df["SMA_200"].iloc[i]
        if pd.isna(sma_val):
            continue

        trend = price > sma_val  # Ціна вище довгострокової лінії
        macd_val = df["MACD"].iloc[i]

        if position is None:
            # ЛОГІКА ВХОДУ (Близька до AI)
            # Купуємо тільки по тренду (Trend=True) і на відкаті (RSI < 45)
            if trend and rsi < 45 and macd_val > 0:
                position = {"entry": price, "high": price}
        else:
            # ЛОГІКА ВИХОДУ
            entry = position["entry"]
            if price > position["high"]:
                position["high"] = price

            pnl = (price - entry) / entry
            drawdown = (position["high"] - price) / position["high"]

            sell = False

            # Stop Loss
            if pnl < -sl:
                sell = True
            # Trailing Take Profit
            elif trail_on and pnl > 0.005 and drawdown > 0.003:
                sell = True
            # Hard Take Profit
            elif not trail_on and pnl > tp:
                sell = True

            if sell:
                profit = 100 * pnl  # Ставка 100$
                balance += profit
                trades += 1
                if profit > 0:
                    wins += 1
                position = None

    return balance, trades, wins


print("🧠 Запуск Розумного Бектесту...")
print(f"Пари: {PAIRS}")

best_profit = -9999
best_config = {}

# Перебираємо варіанти
for sl in [0.01, 0.015]:  # Stop: 1%, 1.5%
    for tp in [0.008, 0.015]:  # Take: 0.8%, 1.5%
        total_profit = 0
        total_trades = 0

        for pair in PAIRS:
            bal, tr, _ = run_smart_backtest(pair, tp, sl, True)
            total_profit += bal - 1000
            total_trades += tr

        print(
            f"⚙️ SL: {sl*100}% | TP: {tp*100}% -> Profit: {total_profit:.2f}$ ({total_trades} угод)"
        )

        if total_profit > best_profit:
            best_profit = total_profit
            best_config = {"SL": sl, "TP": tp}

print(f"\n🏆 ПЕРЕМОЖЕЦЬ: {best_config}")
