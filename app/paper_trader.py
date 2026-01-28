import logging
from typing import Dict, Any, Optional
from app.database import DatabaseManager

logger = logging.getLogger("PaperTrader")

class PaperTrader:
    def __init__(self, initial_balance: float = 1000.0, fee_rate: float = 0.001):
        self.db = DatabaseManager()
        self.fee_rate = fee_rate
        
        # Завантажуємо баланс та відновлюємо відкриті позиції з БД
        self.usdt_balance = self.db.load_balance(initial_balance)
        self.positions: Dict[str, Any] = self.db.load_open_positions()
        
        logger.info(f"💾 Баланс: {self.usdt_balance:.2f} USDT | Відкритих позицій: {len(self.positions)}")

    def get_balance(self) -> float:
        return round(self.usdt_balance, 2)

    def buy(self, symbol: str, price: float, amount_usdt: float):
        """Відкриття позиції з миттєвим збереженням у БД."""
        if symbol in self.positions:
            return

        if self.usdt_balance < 10.0:
            logger.warning(f"⚠️ Недостатньо балансу для купівлі {symbol}")
            return

        # Розрахунок витрат
        trade_amount = min(amount_usdt, self.usdt_balance)
        fee_cost = trade_amount * self.fee_rate
        coin_amount = (trade_amount - fee_cost) / price

        # Оновлення стану
        self.usdt_balance -= trade_amount
        
        pos_data = {
            "amount": coin_amount,
            "entry_price": price,
            "highest_price": price,
            "cost": trade_amount # Зберігаємо скільки реально витратили USDT
        }
        self.positions[symbol] = pos_data

        # Атомарний запис у БД
        try:
            self.db.save_balance(self.usdt_balance)
            self.db.save_position(symbol, pos_data) # Додаємо цей метод у DBManager
            self.db.log_trade(symbol, "BUY", price, coin_amount, trade_amount)
            logger.info(f"🟢 [BUY {symbol}] Entry: {price} | Amt: {coin_amount:.4f}")
        except Exception as e:
            logger.error(f"❌ Помилка БД при купівлі: {e}")

    def update_high(self, symbol: str, current_price: float):
        """Оновлення пікової ціни для Trailing Stop."""
        if symbol in self.positions:
            if current_price > self.positions[symbol]["highest_price"]:
                self.positions[symbol]["highest_price"] = current_price
                # Оновлюємо в БД, щоб після перезапуску трейлінг не збився
                self.db.update_position_high(symbol, current_price)

    def sell(self, symbol: str, price: float, reason: str = "Signal"):
        """Закриття позиції та розрахунок чистого PnL."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        gross_revenue = pos["amount"] * price
        fee_cost = gross_revenue * self.fee_rate
        net_revenue = gross_revenue - fee_cost

        # Точний розрахунок профіту (враховуючи комісії на вході і виході)
        profit_usdt = net_revenue - pos["cost"]
        profit_pct = (profit_usdt / pos["cost"]) * 100
        
        icon = "🤑" if profit_usdt > 0 else "🔻"

        self.usdt_balance += net_revenue
        
        try:
            self.db.save_balance(self.usdt_balance)
            self.db.delete_position(symbol) # Видаляємо з відкритих позицій
            self.db.log_trade(symbol, "SELL", price, pos["amount"], net_revenue, profit_pct)
            
            del self.positions[symbol]
            
            logger.info(
                f"🔴 [SELL {symbol}] Price: {price} | PnL: {profit_pct:.2f}% ({profit_usdt:.2f} USDT) | {reason} {icon}"
            )
            logger.info(f"💰 Поточний баланс: {self.usdt_balance:.2f} USDT")
        except Exception as e:
            logger.error(f"❌ Помилка БД при продажу: {e}")