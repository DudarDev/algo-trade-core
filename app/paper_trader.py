class PaperTrader:
    def __init__(self, initial_usdt=1000.0):
        """
        Початковий баланс: 1000 USDT
        """
        self.usdt = initial_usdt
        self.crypto = 0.0
        self.start_balance = initial_usdt
        self.last_price = 0.0  # <--- НОВЕ: Пам'ятаємо останню ціну ринку
        print(f"💼 СИМУЛЯТОР: Рахунок відкрито. Баланс: {self.usdt} USDT")

    def set_current_price(self, price):
        """Оновлює поточну ринкову ціну (для розрахунку портфеля)"""
        self.last_price = price

    def buy(self, price):
        """Симуляція покупки на всі гроші"""
        if self.usdt > 0:
            amount_to_buy = self.usdt / price
            self.crypto = amount_to_buy
            self.usdt = 0
            self.last_price = price # Оновлюємо ціну
            print(f"💸 КУПІВЛЯ! Ціна: {price}. Отримано: {amount_to_buy:.5f} монет.")
            return True
        else:
            print("⚠️ Немає USDT для покупки.")
            return False

    def sell(self, price):
        """Симуляція продажу всіх монет"""
        if self.crypto > 0:
            amount_usdt = self.crypto * price
            self.usdt = amount_usdt
            self.crypto = 0
            self.last_price = price # Оновлюємо ціну
            print(f"💰 ПРОДАЖ! Ціна: {price}. Баланс став: {self.usdt:.2f} USDT")
            return True
        else:
            print("⚠️ Немає монет для продажу.")
            return False
            
    def get_summary(self, current_price=None):
        """Показує загальну вартість портфеля"""
        # Якщо ціну не передали, беремо останню відому
        price = current_price if current_price else self.last_price
        
        total_value = self.usdt + (self.crypto * price)
        pnl = total_value - self.start_balance
        
        if pnl >= 0:
            pnl_str = f"+{pnl:.2f}"
        else:
            pnl_str = f"{pnl:.2f}"
            
        return total_value, pnl_str