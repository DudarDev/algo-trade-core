import time
from typing import Tuple, Optional
from src.engine.domain.models import Position, TradeSide
from src.shared.config import Settings


class OrderExecutionService:
    @staticmethod
    def calculate_trailing_stop(pos: Position, current_price: float, settings: Settings) -> Tuple[float, float]:
        """
        Багаторівневий адаптивний розрахунок Stop Loss (Breakeven + Trailing Stop Ladder).
        1. Рівень 1 (Breakeven Lock): при русі +1.30%+ переносимо SL у беззбиток (+0.30% net з урахуванням комісій).
        2. Рівень 2 (Trailing Profit): при досягненні +1.80% вмикається активний трейлінг (відступ 0.60%).
        3. Рівень 3 (Mega-Runner): при русі +2.50%+ відступ звужується до 0.45% для максимізації профіту.
        """
        highest_price = pos.highest_price
        sl = pos.sl

        if pos.side == TradeSide.BUY:
            if current_price > highest_price:
                highest_price = current_price

            is_mean_rev = getattr(pos, 'regime', '') in ['MEAN_REVERSION', 'BEAR_MARKET', 'CHOPPY_FLAT']
            
            # 1. Рівень 1: Захист беззбитковості (Breakeven Stop Lock)
            # Піднято поріг активації з 0.65% до 1.30% (для усунення передчасного вибивання ринковим шумом)
            default_be = 0.0120 if is_mean_rev else 0.0135
            be_trigger = getattr(settings, 'BREAK_EVEN_TRIGGER_PCT', default_be)
            if getattr(pos, 'partial_tp_hit', False) or highest_price >= pos.entry_price * (1 + be_trigger):
                be_sl = pos.entry_price * 1.0030
                if be_sl > sl:
                    sl = be_sl

            # 2. Рівень 2 та 3: Динамічний Chandelier ATR Трейлінг-прибуток
            default_activation = 0.0150 if is_mean_rev else 0.0180
            activation_pct = getattr(settings, 'TRAILING_STOP_ACTIVATION_PCT', default_activation)
            if highest_price >= pos.entry_price * (1 + activation_pct):
                base_offset = getattr(settings, 'TRAILING_OFFSET_PCT', 0.0060)
                
                # Розрахунок Chandelier ATR-динамічного відступу на базі поточної волатильності пари
                atr_pct = 0.0
                if hasattr(pos, 'features_snapshot') and isinstance(pos.features_snapshot, dict):
                    atr_pct = float(pos.features_snapshot.get('ATR_PCT', 0.0) or 0.0)
                
                if atr_pct > 0.001:
                    # Адаптуємо відступ як 1.5 * ATR_PCT (клемп від 0.40% до 1.20% для безпеки)
                    offset_pct = max(0.0040, min(0.0120, atr_pct * 1.5))
                else:
                    offset_pct = base_offset

                # Якщо тренд дуже сильний (+2.5%+), звужуємо відступ на 25% для фіксації накопиченого прибутку
                if highest_price >= pos.entry_price * 1.025:
                    offset_pct = max(0.0035, offset_pct * 0.75)

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
                
            # 4. Тайм-аут позиції (Захист від сліпого скидання у збиток)
            holding_time = time.time() - pos.entry_time
            timeout_limit = getattr(settings, 'TRADE_TIMEOUT_SECONDS', 14400)
            enable_structural = getattr(settings, 'ENABLE_STRUCTURAL_TIMEOUT', True)
            if holding_time > timeout_limit:
                if not enable_structural:
                    return "Тайм-аут ⏳"
                # Структурний вихід:
                # 1) Якщо позиція в плюсі (+0.50%+), фіксуємо прибуток і звільняємо слот
                if current_price >= pos.entry_price * 1.005:
                    return "Тайм-аут (Профіт) 🎯"
                # 2) Якщо позиція у стагнаційному просіданні нижче -0.70%, закриваємо через злам структури
                elif current_price < pos.entry_price * 0.993:
                    return "Структурний Тайм-аут ⏳"
                # 3) Якщо ціна консолідується у вузькому діапазоні (-0.7% ... +0.5%), НЕ панікуємо,
                # даємо позиції дихати та відпрацювати до планового TP або SL.
                
        return None
