import logging

class PaperTrader:
    def __init__(self, initial_balance=1000.0):
        self.usdt_balance = initial_balance
        # Словник для зберігання позицій: {'BTC/USDT': {'amount': 0.1, 'entry': 50000}, ...}
        self.positions = {} 

    def get_balance(self):
        # Рахуємо загальний баланс (USDT + вартість всіх монет за ціною входу)
        # У реалі треба брати поточну ціну, але для логу вистачить і так
        equity = self.usdt_balance
        return round(equity, 2)

    def buy(self, symbol, price, amount_usdt):
        """Купівля конкретної монети"""
        if symbol in self.positions:
            # Вже є ця монета, докуповувати не будемо (спрощена логіка)
            return

        if self.usdt_balance < 10:
            return # Немає грошей

        # Купуємо на вказану суму (або на залишок)
        trade_amount_usdt = min(amount_usdt, self.usdt_balance)
        
        # Комісія 0.1%
        fees = trade_amount_usdt * 0.001
        actual_spend = trade_amount_usdt
        
        # Кількість монет
        coin_amount = (trade_amount_usdt - fees) / price
        
        self.usdt_balance -= actual_spend
        
        # Записуємо в портфель
        self.positions[symbol] = {
            'amount': coin_amount,
            'entry_price': price
        }
        
        logging.info(f"🟢 [BUY {symbol}] Ціна: {price}. Куплено: {coin_amount:.4f}. Залишок USDT: {self.usdt_balance:.2f}")

    def sell(self, symbol, price):
        """Продаж конкретної монети"""
        if symbol not in self.positions:
            return # Немає що продавати

        position = self.positions[symbol]
        amount = position['amount']
        entry = position['entry_price']

        # Продаємо
        revenue = amount * price
        fees = revenue * 0.001
        total_receive = revenue - fees
        
        # Рахуємо профіт
        profit_percent = ((price - entry) / entry) * 100 - 0.2
        icon = "🤑" if profit_percent > 0 else "🔻"
        
        self.usdt_balance += total_receive
        
        # Видаляємо з портфеля
        del self.positions[symbol]
        
        logging.info(f"🔴 [SELL {symbol}] Ціна: {price}. PnL: {profit_percent:.2f}% {icon}")
        logging.info(f"💰 Вільний USDT: {self.usdt_balance:.2f}")

    def log_status(self, current_prices):
        """Виводить статус усіх відкритих позицій"""
        if not self.positions:
            return

        logging.info("--- 📊 АКТИВНІ ПОЗИЦІЇ ---")
        for symbol, pos in self.positions.items():
            # Якщо ми знаємо поточну ціну для цієї пари
            if symbol in current_prices:
                curr_price = current_prices[symbol]
                pnl = ((curr_price - pos['entry_price']) / pos['entry_price']) * 100
                logging.info(f"   🔹 {symbol}: {pnl:.2f}%")
        logging.info("---------------------------")