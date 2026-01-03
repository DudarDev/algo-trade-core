import ccxt
import pandas as pd
import logging


class MarketScanner:
    def __init__(self, exchange_id="binanceus"):
        self.exchange = getattr(ccxt, exchange_id)()

    def get_top_volatile_pairs(self, limit=10, min_volume=1000000):
        """
        Знаходить монети, які зараз рухаються найсильніше.
        :param limit: Скільки пар повернути (топ-10)
        :param min_volume: Мінімальний об'єм за 24г (в USDT), щоб не купити щиткоїн
        """
        logging.info("🔍 Сканую ринок на наявність кращих пар...")

        try:
            # Завантажуємо тикери (статистику за 24г) для всіх пар
            tickers = self.exchange.fetch_tickers()

            pairs_data = []

            for symbol, data in tickers.items():
                # Фільтруємо тільки USDT пари
                if "/USDT" not in symbol:
                    continue

                # Фільтруємо сміття з малим об'ємом
                quote_vol = data.get("quoteVolume")  # Об'єм в USDT
                if not quote_vol or quote_vol < min_volume:
                    continue

                # Рахуємо волатильність (зміна ціни у %)
                change_pct = abs(data.get("percentage", 0))

                pairs_data.append(
                    {"symbol": symbol, "change": change_pct, "volume": quote_vol}
                )

            # Сортуємо: спочатку найактивніші
            # (Можна змінити логіку: брати ті, що сильно впали, або сильно виросли)
            sorted_pairs = sorted(pairs_data, key=lambda x: x["change"], reverse=True)

            # Беремо топ N
            top_pairs = [p["symbol"] for p in sorted_pairs[:limit]]

            logging.info(f"🔥 Знайдено гарячі пари: {top_pairs}")
            return top_pairs

        except Exception as e:
            logging.error(f"Помилка сканера: {e}")
            # Повертаємо безпечний дефолтний список, якщо API відпало
            return ["BTC/USDT", "ETH/USDT", "SOL/USDT", "DOGE/USDT", "LTC/USDT"]
