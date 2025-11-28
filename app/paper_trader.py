import datetime

class PaperTrader:
    def __init__(self, initial_balance=1000.0):
        """
        Симулятор торгівлі (Paper Trading).
        initial_balance: Стартовий баланс у USDT
        """
        self.usdt = initial_balance
        self.crypto = 0.0
        self.start_balance = initial_balance
        self.last_price = 0.0
        
        # --- ВАЖЛИВО ДЛЯ СТРАТЕГІЇ ---
        # Ці змінні потрібні, щоб main.py знав, чи ми в угоді
        self.in_position = False
        self.entry_price = 0.0

        print(f"💼 СИМУЛЯТОР: Рахунок відкрито. Баланс: {self.usdt} USDT")

    def buy(self, symbol, price, time):
        """
        Купівля на всі USDT.
        Приймає:
          - symbol: пара (напр. 'BTC/USDT')
          - price: ціна покупки
          - time: час угоди
        """
        if self.usdt > 0:
            amount_to_buy = self.usdt / price
            self.crypto = amount_to_buy
            self.usdt = 0
            
            # Оновлюємо статус для стратегії
            self.in_position = True
            self.entry_price = price
            self.last_price = price
            
            print(f"💸 КУПІВЛЯ {symbol}! Ціна: {price}. Отримано: {amount_to_buy:.5f} монет. Час: {time}")
            return True
        else:
            print("⚠️ Немає USDT для покупки.")
            return False

    def sell(self, symbol, price, time):
        """
        Продаж всієї крипти.
        """
        if self.crypto > 0:
            amount_usdt = self.crypto * price
            
            # Рахуємо прибуток від цієї конкретної угоди
            profit = amount_usdt - (self.crypto * self.entry_price)
            profit_percent = (profit / (self.crypto * self.entry_price)) * 100
            
            self.usdt = amount_usdt
            self.crypto = 0
            
            # Оновлюємо статус
            self.in_position = False
            self.entry_price = 0.0
            self.last_price = price
            
            print(f"💰 ПРОДАЖ {symbol}! Ціна: {price}. Баланс: {self.usdt:.2f} USDT.")
            print(f"📊 Результат угоди: {profit:.2f} USDT ({profit_percent:.2f}%)")
            return True
        else:
            print("⚠️ Немає монет для продажу.")
            return False
            
    def get_summary(self):
        """Повертає загальну вартість портфеля"""
        total_value = self.usdt + (self.crypto * self.last_price)
        pnl = total_value - self.start_balance
        return total_value, pnl