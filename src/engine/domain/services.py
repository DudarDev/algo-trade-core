import time
from typing import Tuple, Optional
from src.engine.domain.models import Position, TradeSide
from src.shared.config import Settings


class OrderExecutionService:
    @staticmethod
    def calculate_trailing_stop(pos: Position, current_price: float, settings: Settings) -> Tuple[float, float]:
        """
        Прораховує пікову ціну та новий рівень Stop Loss.
        Повертает Tuple[highest_price, stop_loss].
        """
        highest_price = pos.highest_price
        sl = pos.sl

        if pos.side == TradeSide.BUY:
            if current_price > highest_price:
                highest_price = current_price

            activation_price = pos.entry_price * (1 + settings.TRAILING_STOP_ACTIVATION_PCT)
            if highest_price >= activation_price:
                new_sl = highest_price * (1 - settings.TRAILING_OFFSET_PCT)
                if new_sl > sl:
                    sl = new_sl

        return highest_price, sl

    @staticmethod
    def evaluate_exit_conditions(pos: Position, current_price: float, settings: Settings) -> Optional[str]:
        """
        Аналізує поточний стан ринку щодо лімітів позиції.
        Повертає рядок з причиною закриття (reason) або None, якщо позицію треба утримувати.
        """
        if pos.side == TradeSide.BUY:
            if current_price <= pos.sl:
                return "Trailing Stop 🛡️" if pos.sl > pos.entry_price else "Stop Loss 🛑"
            
            if current_price >= pos.tp:
                return "Take Profit 🎯"
                
            if (time.time() - pos.entry_time) > settings.TRADE_TIMEOUT_SECONDS:
                return "Тайм-аут ⏳"
                
        return None