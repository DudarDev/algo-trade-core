import ccxt
import pandas as pd
import os
import time
from datetime import datetime, timedelta

EXCHANGE_ID = "binance"  # використовуйте "binanceus" якщо ви в США
TIMEFRAME = "5m"
DAYS = 60
PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "DOGE/USDT", "ADA/USDT", "AVAX/USDT",
    "LINK/USDT", "LTC/USDT", "SHIB/USDT", "UNI/USDT",
    "ATOM/USDT",
]

def download_pair(exchange, symbol):
    print(f"⬇️ Скачую {symbol}...")
    since = exchange.parse8601((datetime.now() - timedelta(days=DAYS)).isoformat())
    all_candles = []
    while since < exchange.milliseconds():
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, since=since, limit=1000)
            if not candles:
                break
            all_candles += candles
            since = candles[-1][0] + 1
            time.sleep(0.5)
            print(f"   Отримано {len(candles)} свічок...")
        except Exception as e:
            print(f"❌ Помилка: {e}")
            time.sleep(5)
            continue

    if not all_candles:
        return

    df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")

    # ВИПРАВЛЕНИЙ ШЛЯХ
    filename = f"data_storage/history/{symbol.replace('/', '_')}_{TIMEFRAME}.csv"
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
