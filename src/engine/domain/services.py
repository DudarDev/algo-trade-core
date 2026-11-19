import time
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional, Protocol, Any, Dict
from src.engine.domain.models import Position, TradeSide
from src.shared.config import Settings

logger = logging.getLogger(__name__)


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


# =====================================================================
# 1. АСИМЕТРИЧНИЙ BASIS GUARD (CASH & CARRY)
# =====================================================================

@dataclass(frozen=True)
class BasisCheckResult:
    is_valid: bool
    basis_pct: float
    reason: str


class AsymmetricBasisGuard:
    def __init__(
        self,
        max_backwardation_pct: float = -0.10,  # Жорсткий ліміт на мінусовий базис (-0.10%)
        max_contango_sanity_pct: float = 1.50  # Захист від аномалій/депегів (+1.50%)
    ):
        self.max_backwardation_pct = max_backwardation_pct
        self.max_contango_sanity_pct = max_contango_sanity_pct

    def evaluate(self, spot_price: float, perp_price: float) -> BasisCheckResult:
        if spot_price <= 0 or perp_price <= 0:
            return BasisCheckResult(False, 0.0, "INVALID_PRICES")

        basis_pct = ((perp_price - spot_price) / spot_price) * 100.0

        # 1. Блокуємо глибоку беквордацію (ф'ючерс дешевший за спот)
        if basis_pct < self.max_backwardation_pct:
            return BasisCheckResult(
                is_valid=False,
                basis_pct=round(basis_pct, 4),
                reason=f"BACKWARDATION_EXCEEDED ({basis_pct:.3f}% < {self.max_backwardation_pct}%)"
            )

        # 2. Блокуємо екстремальне контанго (ймовірний глітч або криза ліквідності)
        if basis_pct > self.max_contango_sanity_pct:
            return BasisCheckResult(
                is_valid=False,
                basis_pct=round(basis_pct, 4),
                reason=f"CONTANGO_ANOMALY ({basis_pct:.3f}% > {self.max_contango_sanity_pct}%)"
            )

        # Позитивний базис (контанго) або мікро-беквордація в межах допуску — дозволено
        status_note = "CONTANGO_TAILWIND" if basis_pct > 0 else "NEUTRAL_BASIS"
        return BasisCheckResult(True, round(basis_pct, 4), status_note)


# =====================================================================
# 2. МОНІТОРИНГ MARGIN RATIO (АНТИ-ЛІКВІДАТОР)
# =====================================================================

class MarginAction(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    REBALANCED = "REBALANCED"
    EMERGENCY_UNWIND = "EMERGENCY_UNWIND"


class MarginTransferPort(Protocol):
    async def get_futures_margin_ratio(self, symbol: str) -> Optional[float]:
        """Повертає Margin Ratio у відсотках (0.0 - 100.0) або None для Paper-розрахунку."""
        ...

    async def transfer_spot_to_futures(self, amount_usdt: float) -> bool:
        """Переказ USDT зі Spot на USD-M Futures для порятунку маржі."""
        ...


class MarginHealthMonitor:
    def __init__(
        self,
        warning_threshold: float = 60.0,
        rebalance_threshold: float = 75.0,
        unwind_threshold: float = 85.0,
        maintenance_margin_rate: float = 0.005  # 0.5% для базового рівня на Binance
    ):
        self.warning_threshold = warning_threshold
        self.rebalance_threshold = rebalance_threshold
        self.unwind_threshold = unwind_threshold
        self.mmr = maintenance_margin_rate

    def estimate_paper_margin_ratio(
        self,
        entry_price: float,
        current_price: float,
        allocated_margin_usdt: float,
        quantity: float
    ) -> float:
        """
        Симуляція Margin Ratio (%) для 1x шорту в Paper-режимі:
        Margin Ratio = Maintenance Margin / Margin Balance * 100
        """
        notional_now = current_price * quantity
        unrealized_pnl = (entry_price - current_price) * quantity
        margin_balance = allocated_margin_usdt + unrealized_pnl

        if margin_balance <= 0:
            return 100.0

        maint_margin = notional_now * self.mmr
        # Приводимо до інтуїтивної шкали навантаження на маржу (0%..100%)
        ratio = (maint_margin / margin_balance) * 100.0
        # Додаткова перевірка: якщо ціна зросла на >60%, шкала має агресивно реагувати
        drawdown_pct = max(0.0, ((current_price - entry_price) / entry_price) * 100.0) if entry_price > 0 else 0.0
        return round(max(ratio, drawdown_pct * 1.15), 2)

    async def check_position_health(
        self,
        position,
        current_perp_price: float,
        transfer_port: MarginTransferPort,
        close_callback,
        notify_callback
    ) -> MarginAction:
        async def _call(cb, *args, **kwargs):
            if not cb:
                return None
            res = cb(*args, **kwargs)
            if asyncio.iscoroutine(res):
                return await res
            return res

        # 1. Отримуємо реальний Margin Ratio з біржі або рахуємо для Paper
        margin_ratio = None
        if hasattr(transfer_port, 'get_futures_margin_ratio'):
            margin_ratio = await transfer_port.get_futures_margin_ratio(position.symbol)

        if margin_ratio is None:
            margin_ratio = self.estimate_paper_margin_ratio(
                entry_price=getattr(position, 'futures_entry_price', getattr(position, 'leg2_entry_price', 0.0)),
                current_price=current_perp_price,
                allocated_margin_usdt=getattr(position, 'notional_value_usdt', getattr(position, 'notional_usdt', 100.0)),
                quantity=getattr(position, 'quantity', getattr(position, 'leg2_amount', 0.0))
            )

        group_id = getattr(position, 'group_id', getattr(position, 'position_id', getattr(position, 'id', '')))

        # 2. Рівень 3: Критичний — негайний вихід із обох ніг до ліквідації
        if margin_ratio >= self.unwind_threshold:
            logger.critical(
                f"🚨 [MARGIN UNWIND] {position.symbol} Margin Ratio={margin_ratio}% >= {self.unwind_threshold}%. Closing both legs!"
            )
            await _call(close_callback, group_id, reason="MARGIN_PROTECTION_UNWIND")
            await _call(
                notify_callback,
                f"🚨 *EMERGENCY UNWIND*: `{position.symbol}` закрито через ризик ліквідації (Margin Ratio: `{margin_ratio}%`)."
            )
            return MarginAction.EMERGENCY_UNWIND

        # 3. Рівень 2: Спроба авто-ребалансу маржі
        if margin_ratio >= self.rebalance_threshold:
            notional = getattr(position, 'notional_value_usdt', getattr(position, 'notional_usdt', 100.0))
            top_up_amount = round(notional * 0.25, 2)  # +25% до маржі
            logger.warning(
                f"⚠️ [MARGIN REBALANCE] {position.symbol} Ratio={margin_ratio}%. Transferring {top_up_amount} USDT..."
            )
            success = False
            if hasattr(transfer_port, 'transfer_spot_to_futures'):
                success = await transfer_port.transfer_spot_to_futures(top_up_amount)

            if success:
                await _call(
                    notify_callback,
                    f"🔄 *MARGIN REBALANCED*: `{position.symbol}` (Ratio `{margin_ratio}%`). Додано `{top_up_amount} USDT` на ф'ючерси."
                )
                return MarginAction.REBALANCED
            else:
                # Якщо переказ не вдався (немає вільного USDT) — страхуємось закриттям
                logger.critical(f"🚨 [REBALANCE FAILED] {position.symbol}. Triggering Emergency Unwind!")
                await _call(close_callback, group_id, reason="MARGIN_REBALANCE_FAILED")
                return MarginAction.EMERGENCY_UNWIND

        # 4. Рівень 1: Попередження
        if margin_ratio >= self.warning_threshold:
            logger.warning(f"⚠️ [MARGIN WARNING] {position.symbol} Margin Ratio={margin_ratio}%")
            await _call(
                notify_callback,
                f"⚠️ *Margin Warning*: `{position.symbol}` наблизився до `{margin_ratio}%` навантаження маржі."
            )
            return MarginAction.WARNING

        return MarginAction.HEALTHY
