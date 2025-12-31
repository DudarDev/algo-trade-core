import logging
from app.database import DatabaseManager

class PaperTrader:
    def __init__(self, initial_balance=1000.0):
        self.db = DatabaseManager()
        self.usdt_balance = self.db.load_balance(initial_balance)
        self.positions = {} 
        logging.info(f"💾 Баланс завантажено з БД: {self.usdt_balance:.2f} USDT")

    def get_balance(self):
        return round(self.usdt_balance, 2)

    def buy(self, symbol, price, amount_usdt):
        if symbol in self.positions: return
        if self.usdt_balance < 10: return

        trade_amount = min(amount_usdt, self.usdt_balance)
        fees = trade_amount * 0.001
        coin_amount = (trade_amount - fees) / price
        
        self.usdt_balance -= trade_amount
        self.db.save_balance(self.usdt_balance)
        self.db.log_trade(symbol, "BUY", price, coin_amount, trade_amount)
        
        self.positions[symbol] = {
            'amount': coin_amount,
            'entry_price': price,
            'highest_price': price 
        }
        
        logging.info(f"🟢 [BUY {symbol}] Entry: {price} | Amt: {coin_amount:.4f}")

    def update_high(self, symbol, current_price):
        if symbol in self.positions:
            if current_price > self.positions[symbol]['highest_price']:
                self.positions[symbol]['highest_price'] = current_price

    def sell(self, symbol, price, reason="Signal"):
        if symbol not in self.positions: return

        pos = self.positions[symbol]
        revenue = pos['amount'] * price
        fees = revenue * 0.001
        total_rec = revenue - fees
        
        profit_pct = ((price - pos['entry_price']) / pos['entry_price']) * 100 - 0.2
        icon = "🤑" if profit_pct > 0 else "🔻"
        
        self.usdt_balance += total_rec
        self.db.save_balance(self.usdt_balance)
        self.db.log_trade(symbol, "SELL", price, pos['amount'], total_rec, profit_pct)
        
        del self.positions[symbol]
        
        logging.info(f"🔴 [SELL {symbol}] Price: {price} | PnL: {profit_pct:.2f}% | {reason} {icon}")
        logging.info(f"💰 Balance: {self.usdt_balance:.2f} USDT")

    def log_status(self, current_prices):
        pass
