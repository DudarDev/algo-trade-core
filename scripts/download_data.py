import ccxt
import pandas as pd
import os
import time
from datetime import datetime, timedelta

# Налаштування
EXCHANGE_ID = "binanceus"  # або 'binance' якщо не в США
TIMEFRAME = "5m"
DAYS = 30  # Скільки днів качати
PAIRS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "DOGE/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "LTC/USDT",
    "SHIB/USDT",
    "MATIC/USDT",
    "UNI/USDT",
    "ATOM/USDT",
]


def download_pair(exchange, symbol):
    print(f"⬇️ Скачую {symbol}...")

    # Вираховуємо час старту (в мілісекундах)
    since = exchange.parse8601((datetime.now() - timedelta(days=DAYS)).isoformat())

    all_candles = []

    while since < exchange.milliseconds():
        try:
            candles = exchange.fetch_ohlcv(
                symbol, timeframe=TIMEFRAME, since=since, limit=1000
            )
            if not candles:
                break

            all_candles += candles
            since = candles[-1][0] + 1  # Час останньої свічки + 1мс

            # Пауза щоб не забанили
            time.sleep(0.5)
            print(f"   Отримано {len(candles)} свічок...")

        except Exception as e:
            print(f"❌ Помилка: {e}")
            time.sleep(5)
            continue

    if not all_candles:
        return

    # Зберігаємо в CSV
    df = pd.DataFrame(
        all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")

    # Створюємо папку data/history
    filename = f"data/history/{symbol.replace('/', '_')}_{TIMEFRAME}.csv"
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    df.to_csv(filename, index=False)
    print(f"✅ Збережено: {filename} ({len(df)} рядків)")


def main():
    exchange = getattr(ccxt, EXCHANGE_ID)()
    print(f"🚀 Починаю завантаження даних з {EXCHANGE_ID}...")

    for symbol in PAIRS:
        download_pair(exchange, symbol)


if __name__ == "__main__":
    main()
