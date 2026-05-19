import logging
import time
import asyncio
from typing import Dict, Optional

from src.shared.config import Settings
from src.engine.domain.models import Position, TradeSide
from src.engine.domain.services import OrderExecutionService
from src.engine.application.interfaces import NotifierProtocol, TradingRepositoryProtocol

logger = logging.getLogger(__name__)


class PaperTrader:
    def __init__(self, settings: Settings, repo: TradingRepositoryProtocol, notifier: NotifierProtocol):
        self.settings = settings
        self.repo = repo
        self.notifier = notifier

        self.positions: Dict[str, Position] = {}
        self.balance: float = 0.0
        self._is_initialized: bool = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Асинхронне відновлення стану балансу та позицій з бази даних при старті."""
        if self._is_initialized:
            return

        async with self._lock:
            self.balance = await asyncio.to_thread(self.repo.load_balance, self.settings.INITIAL_BALANCE)
            db_positions = await asyncio.to_thread(self.repo.get_all_positions)

            for db_pos in db_positions:
                self.positions[db_pos.symbol] = Position(
                    symbol=db_pos.symbol,
                    side=TradeSide.BUY,
                    entry_price=db_pos.entry_price,
                    amount_usdt=db_pos.cost,
                    amount_coins=db_pos.amount,
                    sl=db_pos.entry_price * (1 - self.settings.DEFAULT_SL_PCT),
                    tp=db_pos.entry_price * (1 + self.settings.DEFAULT_TP_PCT),
                    highest_price=db_pos.highest_price,
                    entry_time=db_pos.opened_at.timestamp()
                )

            self._is_initialized = True
            logger.info(f"💾 PaperTrader успішно ініціалізовано. Баланс: {self.balance:.2f} USDT | Активних позицій: {len(self.positions)}")

    async def open_position(self, symbol: str, side: TradeSide, price: float, sl: float, tp: float) -> None:
        """Відкриває позицію із суворим thread-safe контролем балансу."""
        if not self._is_initialized:
            logger.error("❌ Спроба відкрити позицію до ініціалізації PaperTrader.")
            return

        # Примусове перетворення у float, щоб уникнути np.float64
        price = float(price)
        sl = float(sl)
        tp = float(tp)

        pos_to_save: Optional[Position] = None
        current_balance: float = 0.0

        async with self._lock:
            if symbol in self.positions:
                return

            actual_amount = min(self.balance * self.settings.TRADE_FRACTION, self.balance * 0.98)
            if actual_amount < self.settings.MIN_TRADE_SIZE:
                logger.warning(f"⚠️ Пропуск {symbol}: недостатньо балансу ({self.balance:.2f} USDT).")
                return

            self.balance -= actual_amount
            current_balance = self.balance

            pos_to_save = Position(
                symbol=symbol, side=side, entry_price=price,
                amount_usdt=actual_amount, amount_coins=actual_amount / price,
                sl=sl, tp=tp, highest_price=price, entry_time=time.time()
            )
            self.positions[symbol] = pos_to_save

        # Усі дані для БД явно конвертуємо у float
        await asyncio.to_thread(
            self.repo.save_position,
            symbol=pos_to_save.symbol,
            amount=float(pos_to_save.amount_coins),
            entry_price=float(pos_to_save.entry_price),
            highest_price=float(pos_to_save.highest_price),
            cost=float(pos_to_save.amount_usdt)
        )
        await asyncio.to_thread(self.repo.save_balance, float(current_balance))

        logger.info(f"🚀 [ВХІД] {side.value} {symbol} | Ціна: {price:.4f} | Об'єм: {pos_to_save.amount_usdt:.2f} USDT")
        if self.settings.ENABLE_TELEGRAM:
            await self.notifier.send_message(f"🟢 Відкрито Paper Trade: {side.value} {symbol} по {price:.4f}")

    async def update_position(self, symbol: str, current_price: float) -> None:
        """Оновлює стан ордера, прораховує трейлінг та ініціює вихід за умов ринку."""
        current_price = float(current_price)

        pos: Optional[Position] = None
        async with self._lock:
            pos = self.positions.get(symbol)

        if not pos:
            return

        highest, new_sl = OrderExecutionService.calculate_trailing_stop(pos, current_price, self.settings)

        if highest > pos.highest_price:
            pos.highest_price = highest
            await asyncio.to_thread(self.repo.update_position_high, symbol, float(highest))
        pos.sl = new_sl

        exit_reason = OrderExecutionService.evaluate_exit_conditions(pos, current_price, self.settings)
        if exit_reason:
            await self._close_position(symbol, current_price, exit_reason)

    async def _close_position(self, symbol: str, close_price: float, reason: str) -> None:
        """Атомарно вилучає позицію та реєструє фінансовий результат у репозиторії."""
        close_price = float(close_price)

        pos: Optional[Position] = None
        current_balance: float = 0.0
        pnl: float = 0.0
        return_amount: float = 0.0

        async with self._lock:
            if symbol not in self.positions:
                return

            pos = self.positions.pop(symbol)
            pnl = (close_price - pos.entry_price) * pos.amount_coins
            return_amount = pos.amount_usdt + pnl

            self.balance += return_amount
            current_balance = self.balance

        # Усі дані для БД явно конвертуємо у float
        await asyncio.to_thread(self.repo.delete_position, symbol)
        await asyncio.to_thread(
            self.repo.log_trade,
            symbol=symbol,
            side=TradeSide.SELL.value,
            price=float(close_price),
            amount=float(pos.amount_coins),
            cost=float(return_amount),
            pnl=float(pnl)
        )
        await asyncio.to_thread(self.repo.save_balance, float(current_balance))

        msg = f"📉 [ВИХІД] {symbol} закрито через {reason} | Ціна: {close_price:.4f} | PnL: {pnl:+.2f} USDT"
        logger.info(msg)
        if self.settings.ENABLE_TELEGRAM:
            await self.notifier.send_message(msg)