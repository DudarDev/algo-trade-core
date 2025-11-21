class PaperTrader:
    def __init__(self, initial_usdt=1000.0):
        """
        Початковий баланс: 1000 USDT
        """
        self.usdt = initial_usdt  # Скільки у нас доларів
        self.crypto = 0.0         # Скільки у нас монет (BTC)
        self.start_balance = initial_usdt
        print(f"💼 СИМУЛЯТОР: Рахунок відкрито. Баланс: {self.usdt} USDT")

    def buy(self, price):
        """Симуляція покупки на всі гроші"""
        if self.usdt > 0:
            # Рахуємо, скільки можемо купити
            amount_to_buy = self.usdt / price
            
            # Оновлюємо баланси
            self.crypto = amount_to_buy
            self.usdt = 0
            
            print(f"💸 КУПІВЛЯ! Ціна: {price}. Отримано: {amount_to_buy:.5f} монет.")
            return True
        else:
            print("⚠️ Немає USDT для покупки (ми вже в позиції).")
            return False

    def sell(self, price):
        """Симуляція продажу всіх монет"""
        if self.crypto > 0:
            # Рахуємо, скільки отримаємо доларів
            amount_usdt = self.crypto * price
            
            # Рахуємо прибуток від цієї угоди
            profit = amount_usdt - self.start_balance # (спрощено)
            
            # Оновлюємо баланси
            self.usdt = amount_usdt
            self.crypto = 0
            
            print(f"💰 ПРОДАЖ! Ціна: {price}. Баланс став: {self.usdt:.2f} USDT")
            return True
        else:
            print("⚠️ Немає монет для продажу (ми у доларі).")
            return False
            
    def get_summary(self, current_price):
        """Показує загальну вартість портфеля зараз"""
        total_value = self.usdt + (self.crypto * current_price)
        pnl = total_value - self.start_balance # Profit and Loss (Прибуток/Збиток)
        
        if pnl >= 0:
            pnl_str = f"+{pnl:.2f}"
        else:
            pnl_str = f"{pnl:.2f}"
            
        return total_value, pnl_str