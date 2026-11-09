import time
from typing import Tuple, Optional
from src.engine.domain.models import Position, TradeSide
from src.shared.config import Settings


class OrderExecutionService:
    @staticmethod
    def calculate_trailing_stop(pos: Position, current_price: float, settings: Settings) -> Tuple[float, float]:
        """
        Багаторівневий адаптивний розрахунок Stop Loss (Breakeven + Trailing Stop Ladder).
        1. Рівень 1 (Breakeven Lock): при русі +0.70% переносимо SL у беззбиток (+0.25% net).
        2. Рівень 2 (Trailing Profit): при досягненні +1.10% вмикається активний трейлінг (відступ 0.45%).
        3. Рівень 3 (Mega-Runner): при русі +1.80%+ відступ звужується до 0.35% для максимізації профіту.
        """
        highest_price = pos.highest_price
        sl = pos.sl

        if pos.side == TradeSide.BUY:
            if current_price > highest_price:
                highest_price = current_price

            is_mean_rev = getattr(pos, 'regime', '') in ['MEAN_REVERSION', 'BEAR_MARKET', 'CHOPPY_FLAT']
            
            # 1. Рівень 1: Захист беззбитковості (Breakeven Stop Lock)
            default_be = 0.0065 if is_mean_rev else 0.0075
            be_trigger = getattr(settings, 'BREAK_EVEN_TRIGGER_PCT', default_be)
            if getattr(pos, 'partial_tp_hit', False) or highest_price >= pos.entry_price * (1 + be_trigger):
                be_sl = pos.entry_price * 1.0025
                if be_sl > sl:
                    sl = be_sl

            # 2. Рівень 2 та 3: Динамічний Трейлінг-прибуток (Profit Ladder Trailing)
            default_activation = 0.0090 if is_mean_rev else 0.0110
            activation_pct = getattr(settings, 'TRAILING_STOP_ACTIVATION_PCT', default_activation)
            if highest_price >= pos.entry_price * (1 + activation_pct):
                # Базовий відступ 0.45%
                offset_pct = getattr(settings, 'TRAILING_OFFSET_PCT', 0.0045)
                # Якщо тренд дуже сильний (+1.8%+), звужуємо відступ до 0.35% для збереження прибутку
                if highest_price >= pos.entry_price * 1.018:
                    offset_pct = 0.0035

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
                if pos.sl >= pos.entry_price * 1.0060:
                    return "Trailing Stop 🎯"
                if pos.sl >= pos.entry_price * 1.0010:
                    return "Breakeven Stop 🔒"
                return "Stop Loss 🛑"
            
            if current_price >= pos.tp:
                return "Take Profit 🎯"

            # 3. Partial Take Profit (Scale-Out Engine: фіксація 50% об'єму на TP1)
            partial_tp_pct = getattr(settings, 'PARTIAL_TP_PCT', 0.015)
            if not getattr(pos, 'partial_tp_hit', False) and current_price >= pos.entry_price * (1 + partial_tp_pct):
                return "Take Profit 1 (50%) 🎯"
                
            if (time.time() - pos.entry_time) > settings.TRADE_TIMEOUT_SECONDS:
                return "Тайм-аут ⏳"
                
        return None
