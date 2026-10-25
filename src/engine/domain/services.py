import time
from typing import Tuple, Optional
from src.engine.domain.models import Position, TradeSide
from src.shared.config import Settings


class OrderExecutionService:
    @staticmethod
    def calculate_trailing_stop(pos: Position, current_price: float, settings: Settings) -> Tuple[float, float]:
        """
        Прораховує пікову ціну та новий рівень Stop Loss (Breakeven + Trailing Stop).
        Повертає Tuple[highest_price, stop_loss].
        """
        highest_price = pos.highest_price
        sl = pos.sl

        if pos.side == TradeSide.BUY:
            if current_price > highest_price:
                highest_price = current_price

            # 1. Early Breakeven Stop Lock:
            # Фіксація беззбитковості при підйомі ціни на >= be_trigger (+0.60%)
            # або після Partial TP. Встановлюємо SL на +0.20% (повне покриття комісій + гарантований плюс)
            be_trigger = getattr(settings, 'BREAK_EVEN_TRIGGER_PCT', 0.006)
            if getattr(pos, 'partial_tp_hit', False) or highest_price >= pos.entry_price * (1 + be_trigger):
                be_sl = pos.entry_price * 1.0020
                if be_sl > sl:
                    sl = be_sl

            # 2. Dynamic Trailing Stop:
            activation_pct = getattr(settings, 'TRAILING_STOP_ACTIVATION_PCT', 0.025)
            offset_pct = getattr(settings, 'TRAILING_OFFSET_PCT', 0.010)
            activation_price = pos.entry_price * (1 + activation_pct)
            if highest_price >= activation_price:
                new_sl = highest_price * (1 - offset_pct)
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
                if pos.sl >= pos.entry_price * 1.001:
                    return "Breakeven Stop 🔒"
                return "Trailing Stop 🛡️" if pos.sl > pos.entry_price else "Stop Loss 🛑"
            
            if current_price >= pos.tp:
                return "Take Profit 🎯"

            # 3. Partial Take Profit (Scale-Out Engine: фіксація 50% об'єму на TP1)
            partial_tp_pct = getattr(settings, 'PARTIAL_TP_PCT', 0.015)
            if not getattr(pos, 'partial_tp_hit', False) and current_price >= pos.entry_price * (1 + partial_tp_pct):
                return "Take Profit 1 (50%) 🎯"
                
            if (time.time() - pos.entry_time) > settings.TRADE_TIMEOUT_SECONDS:
                return "Тайм-аут ⏳"
                
        return None