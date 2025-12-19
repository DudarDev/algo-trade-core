import logging

class PaperTrader:
    def __init__(self, initial_balance=1000.0):
        self.usdt_balance = initial_balance
        self.crypto_balance = 0.0
        self.in_position = False
        self.entry_price = 0.0

    def get_balance(self):
        return round(self.usdt_balance, 2)

    def buy(self, symbol, price, amount_usdt):
        """Симуляція покупки"""
        if self.in_position:
            # logging.info("Вже в позиції, пропускаю BUY")
            return

        if self.usdt_balance < 10:
            logging.warning("Недостатньо коштів для покупки")
            return

        # Розрахунок
        trade_amount = min(amount_usdt, self.usdt_balance)
        fees = trade_amount * 0.001 # 0.1% комісія (як на Binance)
        cost = trade_amount + fees
        
        self.crypto_balance = (trade_amount / price)
        self.usdt_balance -= cost
        
        self.in_position = True
        self.entry_price = price
        
        logging.info(f"🟢 [PAPER BUY] Купив {self.crypto_balance:.5f} {symbol} по {price}. Баланс USDT: {self.usdt_balance:.2f}")

    def sell(self, symbol, price):
        """Симуляція продажу"""
        if not self.in_position:
            return

        # Розрахунок
        revenue = self.crypto_balance * price
        fees = revenue * 0.001 # 0.1% комісія
        total_receive = revenue - fees
        
        profit = total_receive - (self.crypto_balance * self.entry_price)
        profit_percent = (profit / (self.crypto_balance * self.entry_price)) * 100
        
        self.usdt_balance += total_receive
        self.crypto_balance = 0.0
        self.in_position = False
        
        icon = "🤑" if profit > 0 else "🔻"
        logging.info(f"🔴 [PAPER SELL] Продав по {price}. PnL: {profit:.2f}$ ({profit_percent:.2f}%) {icon}")
        logging.info(f"💰 Загальний баланс: {self.usdt_balance:.2f} USDT")

    def log_status(self, current_price):
        if self.in_position:
            unrealized_pnl = (current_price - self.entry_price) / self.entry_price * 100
            logging.info(f"📊 Позиція відкрита. PnL (плаваючий): {unrealized_pnl:.2f}%")