import logging
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
    """Симулятор торгів (Paper Trading) для перевірки стратегій без ризику."""
    def __init__(self, initial_balance: float = 1000.0):
        self.balance = initial_balance
        self.positions: Dict[str, Position] = {}
        logger.info(f"💾 Баланс завантажено: {self.balance:.2f} USDT")

    def get_balance(self) -> float:
        return self.balance

    def has_open_position(self, symbol: str) -> bool:
        return symbol in self.positions

    def open_position(self, symbol: str, side: str, amount_usdt: float, price: float, sl: float, tp: float):
        if symbol in self.positions:
            logger.warning(f"⚠️ Позиція по {symbol} вже відкрита.")
            return

        if amount_usdt > self.balance:
            logger.warning(f"⚠️ Недостатньо коштів для відкриття позиції {symbol}. Баланс: {self.balance:.2f}")
            return

        amount_coins = amount_usdt / price
        self.balance -= amount_usdt
        
        self.positions[symbol] = Position(
            symbol=symbol, side=side, entry_price=price, 
            amount_usdt=amount_usdt, amount_coins=amount_coins, 
            sl=sl, tp=tp
        )
        logger.info(f"✅ ВІДКРИТО {side} {symbol} | Ціна: {price:.4f} | Об'єм: {amount_usdt:.2f}$ | SL: {sl:.4f} | TP: {tp:.4f}")

    def update_position(self, symbol: str, current_price: float):
        """Оновлює стан позиції, перевіряє перетин SL або TP."""
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        
        # Логіка для Long
        if pos.side == "BUY":
            if current_price <= pos.sl:
                self._close_position(symbol, current_price, "Stop Loss")
            elif current_price >= pos.tp:
                self._close_position(symbol, current_price, "Take Profit")
                
        # Логіка для Short (на майбутнє)
        elif pos.side == "SELL":
            if current_price >= pos.sl:
                self._close_position(symbol, current_price, "Stop Loss")
            elif current_price <= pos.tp:
                self._close_position(symbol, current_price, "Take Profit")

    def _close_position(self, symbol: str, close_price: float, reason: str):
        pos = self.positions.pop(symbol)
        
        if pos.side == "BUY":
            pnl = (close_price - pos.entry_price) * pos.amount_coins
        else:
            pnl = (pos.entry_price - close_price) * pos.amount_coins

        return_amount = pos.amount_usdt + pnl
        self.balance += return_amount
        
        emoji = "🟢" if pnl > 0 else "🔴"
        logger.info(f"{emoji} ЗАКРИТО {pos.side} {symbol} ({reason}) | Ціна: {close_price:.4f} | PnL: {pnl:.2f}$ | Баланс: {self.balance:.2f}$")
