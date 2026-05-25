#!/usr/bin/env python3
"""Завантаження історичних OHLCV-даних з біржі."""
import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import ccxt
import pandas as pd

# Корінь проєкту – батьківська тека для scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("DataDownloader")

# Типові значення
DEFAULT_EXCHANGE = "binance"
DEFAULT_TIMEFRAME = "5m"
DEFAULT_DAYS = 60
DEFAULT_PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "DOGE/USDT", "ADA/USDT", "AVAX/USDT",
    "LINK/USDT", "LTC/USDT", "SHIB/USDT", "UNI/USDT",
    "ATOM/USDT",
]
OUTPUT_DIR = PROJECT_ROOT / "data_storage" / "history"

def download_pair(exchange, symbol, timeframe, days):
    """Завантажує дані для одного символу та зберігає в CSV."""
    logger.info(f"⬇️  Завантаження {symbol}...")
    since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())
    all_candles = []

    while since < exchange.milliseconds():
        try:
            candles = exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, since=since, limit=1000
            )
            if not candles:
                break
            all_candles += candles
            since = candles[-1][0] + 1
            time.sleep(0.5)  # повага до rate limit
        except Exception as e:
            logger.error(f"Помилка при отриманні {symbol}: {e}. Чекаю 5 сек...")
            time.sleep(5)
            continue

    if not all_candles:
        logger.warning(f"Немає даних для {symbol}")
        return

    df = pd.DataFrame(
        all_candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms")

    # Збереження
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = OUTPUT_DIR / f"{symbol.replace('/', '_')}_{timeframe}.csv"
    df.to_csv(filename, index=False)
    logger.info(f"✅ Збережено: {filename} ({len(df)} рядків)")

def main():
    parser = argparse.ArgumentParser(description="Завантажувач історичних даних")
    parser.add_argument("--exchange", default=DEFAULT_EXCHANGE, help="ID біржі")
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME, help="Таймфрейм")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="Кількість днів")
    parser.add_argument("--pairs", nargs="+", default=DEFAULT_PAIRS, help="Список пар")
    args = parser.parse_args()

    exchange = getattr(ccxt, args.exchange)()
    logger.info(f"🚀 Старт завантаження з {args.exchange}, таймфрейм {args.timeframe}, глибина {args.days} днів")

    for symbol in args.pairs:
        try:
            download_pair(exchange, symbol, args.timeframe, args.days)
        except Exception as e:
            logger.error(f"Критична помилка для {symbol}: {e}")

    logger.info("🏁 Завантаження завершено")

if __name__ == "__main__":
    main()