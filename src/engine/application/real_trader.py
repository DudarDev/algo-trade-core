"""
DEPRECATED / EXPERIMENTAL:
Поточна версія рушія використовує асинхронний PaperTrader (src/engine/application/paper_trader.py).
Цей модуль є застарілим прототипом синхронного виконання.
"""
import logging


class RealTrader:
    def __init__(self, exchange_manager):
        """
        Реальний трейдер. Виконує ордери на біржі.
        Приймає об'єкт exchange_manager для зв'язку з API.
        """
        self.manager = exchange_manager
        self.in_position = False
        self.entry_price = 0.0
        self.logger = logging.getLogger("CryptoBot")
        self.logger.info("⚠️ УВАГА: Запущено режим РЕАЛЬНОЇ торгівлі!")

    def buy(self, symbol, price, time):
        """Відправляє ринковий ордер на КУПІВЛЮ"""
        try:
            # 1. Отримуємо баланс (USD або USDT)
            balance = self.manager.exchange.fetch_balance()
            # Для Kraken часто використовується 'USD', для інших 'USDT'
            # Перевіряємо обидва варіанти
            currency = "USDT" if "USDT" in symbol else "USD"
            fiat_balance = balance["total"].get(currency, 0)

            if fiat_balance < 10:  # Мінімалка на Kraken ~$10
                self.logger.warning(
                    f"⚠️ Недостатньо коштів ({fiat_balance} {currency}) для ордера."
                )
                return False

            # 2. Розраховуємо кількість (на всі гроші - 1% на комісію)
            amount = (fiat_balance * 0.99) / price

            # 3. Відправляємо ордер!
            self.logger.info(f"📤 Відправляю ордер BUY: {amount:.6f} {symbol}...")
            order = self.manager.exchange.create_order(symbol, "market", "buy", amount)

            self.logger.info(f"💸 ОРДЕР ВИКОНАНО! ID: {order['id']}")
            self.in_position = True
            self.entry_price = price
            return True

        except Exception as e:
            self.logger.error(f"❌ Помилка купівлі: {e}")
            return False

    def sell(self, symbol, price, time):
        """Відправляє ринковий ордер на ПРОДАЖ"""
        try:
            # 1. Отримуємо баланс монети (наприклад, ETH)
            coin = symbol.split("/")[0]  # Беремо 'ETH' з 'ETH/USD'
            balance = self.manager.exchange.fetch_balance()
            coin_balance = balance["total"].get(coin, 0)

            if coin_balance == 0:
                self.logger.warning(f"⚠️ Немає {coin} для продажу.")
                return False

            # 2. Продаємо все, що є
            self.logger.info(
                f"📤 Відправляю ордер SELL: {coin_balance:.6f} {symbol}..."
            )
            order = self.manager.exchange.create_order(
                symbol, "market", "sell", coin_balance
            )

            self.logger.info(f"💰 ОРДЕР ВИКОНАНО! ID: {order['id']}")
            self.in_position = False
            self.entry_price = 0.0
            return True

        except Exception as e:
            self.logger.error(f"❌ Помилка продажу: {e}")
            return False
