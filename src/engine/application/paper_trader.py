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
        self._lock = asyncio.Lock()  # Гарантія атомарності змін внутрішнього стану (balance, positions)

    async def initialize(self) -> None:
        """Асинхронне відновлення стану балансу та позицій з бази даних при старті."""
        if self._is_initialized:
            return

        async with self._lock:
            # Виконуємо I/O операції в окремих потоках, щоб не блокувати Event Loop
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

        # ВИПРАВЛЕНО: Примусово конвертуємо входи у float, щоб уникнути np.float64
        price = float(price)
        sl = float(sl)
        tp = float(tp)

        # Локальні змінні для збереження даних за межами блокування
        pos_to_save: Optional[Position] = None
        current_balance: float = 0.0

        async with self._lock:
            if symbol in self.positions:
                return  # Позиція вже відкрита, виходимо без помилки

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

        # ——— КРИТИЧНИЙ ФІКС: ТРАНЗАКЦІЙНИЙ I/O ВИКОНУЄТЬСЯ ЗА МЕЖАМИ ЛОКУ ———
        await asyncio.to_thread(
            self.repo.save_position,
            symbol=pos_to_save.symbol, 
            amount=float(pos_to_save.amount_coins), # ВИПРАВЛЕНО
            entry_price=float(pos_to_save.entry_price), # ВИПРАВЛЕНО
            highest_price=float(pos_to_save.highest_price), # ВИПРАВЛЕНО
            cost=float(pos_to_save.amount_usdt) # ВИПРАВЛЕНО
        )
        await asyncio.to_thread(self.repo.save_balance, float(current_balance)) # ВИПРАВЛЕНО

        logger.info(f"🚀 [ВХІД] {side.value} {symbol} | Ціна: {price:.4f} | Об'єм: {pos_to_save.amount_usdt:.2f} USDT")
        if self.settings.ENABLE_TELEGRAM:
            await self.notifier.send_message(f"🟢 Відкрито Paper Trade: {side.value} {symbol} по {price:.4f}")

    async def update_position(self, symbol: str, current_price: float) -> None:
        """Оновлює стан ордера, прораховує трейлінг та ініціює вихід за умов ринку."""
        pos: Optional[Position] = None
        
        # ВИПРАВЛЕНО: Примусово конвертуємо price у float
        current_price = float(current_price)
        
        # Швидка thread-safe копія посилання на об'єкт позиції
        async with self._lock:
            pos = self.positions.get(symbol)

        if not pos:
            return

        # 1. Розрахунок Trailing Stop через чистий Domain Service
        highest, new_sl = OrderExecutionService.calculate_trailing_stop(pos, current_price, self.settings)
        
        if highest > pos.highest_price:
            pos.highest_price = highest
            # ВИПРАВЛЕНО: Огортаємо highest у float
            await asyncio.to_thread(self.repo.update_position_high, symbol, float(highest)) 
        pos.sl = new_sl

        # 2. Перевірка умов виходу
        exit_reason = OrderExecutionService.evaluate_exit_conditions(pos, current_price, self.settings)
        if exit_reason:
            await self._close_position(symbol, current_price, exit_reason)

    async def _close_position(self, symbol: str, close_price: float, reason: str) -> None:
        """Атомарно вилучає позицію та реєструє фінансовий результат у репозиторії."""
        pos: Optional[Position] = None
        current_balance: float = 0.0
        pnl: float = 0.0
        return_amount: float = 0.0
        
        close_price = float(close_price) # ВИПРАВЛЕНО

        async with self._lock:
            # Захист від повторного виклику іншим асинхронним таском
            if symbol not in self.positions:
                return
                
            pos = self.positions.pop(symbol)
            pnl = (close_price - pos.entry_price) * pos.amount_coins
            return_amount = pos.amount_usdt + pnl
            
            self.balance += return_amount
            current_balance = self.balance

        # ——— I/O ОПЕРАЦІЇ ВИКОНУЮТЬСЯ ПОЗА ЛОКОМ (НЕ БЛОКУЮТЬ ІНШІ ПАРИ) ———
        await asyncio.to_thread(self.repo.delete_position, symbol)
        await asyncio.to_thread(
            self.repo.log_trade,
            symbol=symbol, side=TradeSide.SELL.value, 
            price=float(close_price), # ВИПРАВЛЕНО
            amount=float(pos.amount_coins), # ВИПРАВЛЕНО
            cost=float(return_amount), # ВИПРАВЛЕНО
            pnl=float(pnl) # ВИПРАВЛЕНО
        )
        await asyncio.to_thread(self.repo.save_balance, float(current_balance)) # ВИПРАВЛЕНО

        msg = f"📉 [ВИХІД] {symbol} закрито через {reason} | Ціна: {close_price:.4f} | PnL: {pnl:+.2f} USDT"
        logger.info(msg)
        if self.settings.ENABLE_TELEGRAM:
            await self.notifier.send_message(msg)