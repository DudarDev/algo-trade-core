import logging
import sqlite3
from datetime import datetime
from typing import Dict
from dataclasses import dataclass
from app.config import settings

logger = logging.getLogger(__name__)

@dataclass
class Position:
    symbol: str
    side: str
    entry_price: float
    amount_usdt: float
    amount_coins: float
    sl: float
    tp: float

class PaperTrader:
    """Симулятор торгів (Paper Trading) із записом у базу даних для дашборду."""
    def __init__(self, initial_balance: float = 1000.0):
        self.db_path = "data/bot_data.db"
        self.positions: Dict[str, Position] = {}
        
        # Завантажуємо баланс із бази даних, або створюємо новий
        self.balance = self._load_balance(initial_balance)
        logger.info(f"💾 Баланс завантажено: {self.balance:.2f} USDT")

    def _execute_db(self, query: str, params: tuple = ()):
        """Допоміжна функція для запису в базу даних SQLite."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
        except Exception as e:
            logger.error(f"❌ Помилка БД: {e}")

    def _load_balance(self, default_balance: float) -> float:
        """Читає поточний баланс із бази даних."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT usdt_balance FROM wallet ORDER BY id DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    return row[0]
                else:
                    # Якщо база порожня, записуємо стартовий баланс
                    cursor.execute("INSERT INTO wallet (usdt_balance) VALUES (?)", (default_balance,))
                    conn.commit()
                    return default_balance
        except Exception:
            return default_balance

    def _update_db_balance(self):
        """Оновлює баланс у базі даних."""
        # Оновлюємо всі записи балансу (зазвичай там один)
        self._execute_db("UPDATE wallet SET usdt_balance = ?", (self.balance,))

    def _log_trade_to_db(self, symbol: str, side: str, price: float, amount_coins: float, cost: float, pnl: float):
        """Записує торгову операцію в таблицю trades для відображення на дашборді."""
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        query = """
            INSERT INTO trades (symbol, side, price, amount, cost, pnl, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        self._execute_db(query, (symbol, side, price, amount_coins, cost, pnl, now))

    def get_balance(self) -> float:
        return self.balance

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.positions

    def open_position(self, symbol: str, side: str, amount_usdt: float, price: float, sl: float, tp: float):
        if symbol in self.positions:
            return

        # РИЗИК-МЕНЕДЖМЕНТ: Беремо 20% від загального балансу (або залишок, якщо його менше)
        trade_fraction = 0.20
        max_trade_amount = 1000.0 * trade_fraction # 1000.0 - це базовий депозит, щоб завжди брати $200
        
        # Захист: якщо на балансі менше $200, беремо все що є
        actual_amount = min(max_trade_amount, self.balance * 0.98)

        if actual_amount < 10.0: # Захист від відкриття мікро-угод
            logger.warning(f"⚠️ Недостатньо коштів для {symbol}. Потрібно мін $10, є: {self.balance:.2f}")
            return

        amount_coins = actual_amount / price
        self.balance -= actual_amount
        
        self.positions[symbol] = Position(
            symbol=symbol, side=side, entry_price=price, 
            amount_usdt=actual_amount, amount_coins=amount_coins, 
            sl=sl, tp=tp
        )
        
        # ОНОВЛЮЄМО БАЗУ ДАНИХ
        self._update_db_balance()
        self._log_trade_to_db(symbol, side, price, amount_coins, actual_amount, 0.0)
        
        logger.info(f"✅ ВІДКРИТО {side} {symbol} | Ціна: {price:.4f} | Об'єм: {actual_amount:.2f}$")

    def update_position(self, symbol: str, current_price: float):
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        
        if pos.side == "BUY":
            if current_price <= pos.sl:
                self._close_position(symbol, current_price, "Stop Loss")
            elif current_price >= pos.tp:
                self._close_position(symbol, current_price, "Take Profit")

    def _close_position(self, symbol: str, close_price: float, reason: str):
        pos = self.positions.pop(symbol)
        
        if pos.side == "BUY":
            pnl = (close_price - pos.entry_price) * pos.amount_coins
        else:
            pnl = (pos.entry_price - close_price) * pos.amount_coins

        return_amount = pos.amount_usdt + pnl
        self.balance += return_amount
        
        # ОНОВЛЮЄМО БАЗУ ДАНИХ
        self._update_db_balance()
        self._log_trade_to_db(symbol, "SELL", close_price, pos.amount_coins, return_amount, pnl)
        
        emoji = "🟢" if pnl > 0 else "🔴"
        logger.info(f"{emoji} ЗАКРИТО {pos.side} {symbol} ({reason}) | Ціна: {close_price:.4f} | PnL: {pnl:.2f}$ | Баланс: {self.balance:.2f}$")
