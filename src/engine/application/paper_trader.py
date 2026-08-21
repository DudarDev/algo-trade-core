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
        
        # Lock для захисту пам'яті від race conditions при паралельних асинхронних запитах
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
                    # Використовуємо getattr для сумісності, якщо старі налаштування ще є в базі
                    sl=db_pos.entry_price * (1 - getattr(self.settings, 'DEFAULT_SL_PCT', 0.02)),
                    tp=db_pos.entry_price * (1 + getattr(self.settings, 'DEFAULT_TP_PCT', 0.05)),
                    highest_price=db_pos.highest_price,
                    entry_time=db_pos.opened_at.timestamp()
                )

            self._is_initialized = True
            logger.info(f"💾 PaperTrader успішно ініціалізовано. Баланс: {self.balance:.2f} USDT | Активних позицій: {len(self.positions)}")

    async def open_position(self, symbol: str, side: TradeSide, price: float, sl: float, tp: float) -> None:
        """Відкриває позицію із динамічним ризик-менеджментом та обліком комісій."""
        if not self._is_initialized:
            logger.error("❌ Спроба відкрити позицію до ініціалізації PaperTrader.")
            return

        price, sl, tp = float(price), float(sl), float(tp)
        pos_to_save: Optional[Position] = None

        # 1. Оновлюємо стан у пам'яті ПІД ЛОКОМ
        async with self._lock:
            if symbol in self.positions:
                return

            # Перевірка на ліміт одночасних угод (захист капіталу від корекції всього ринку)
            if len(self.positions) >= self.settings.max_open_positions:
                logger.debug(f"⚠️ Пропуск {symbol}: досягнуто ліміт активних позицій ({self.settings.max_open_positions}).")
                return

            # --- РОЗРАХУНОК ОБ'ЄМУ (POSITION SIZING) ---
            risk_budget = self.balance * self.settings.risk_per_trade_pct
            risk_per_coin = abs(price - sl)

            if risk_per_coin <= 0:
                logger.error(f"❌ Помилка розрахунку ризику для {symbol}: ціна входу дорівнює SL.")
                return

            ideal_coins = risk_budget / risk_per_coin
            ideal_usdt = ideal_coins * price

            # Капаємо розмір позиції до доступного балансу (залишаємо запас 2%)
            actual_usdt = min(ideal_usdt, self.balance * 0.98)
            actual_coins = actual_usdt / price

            if actual_usdt < 10.0:  # Hard limit для більшості бірж
                logger.warning(f"⚠️ Пропуск {symbol}: розрахований об'єм {actual_usdt:.2f} USDT занадто малий.")
                return

            # --- ОБЛІК КОМІСІЇ ---
            entry_fee_usdt = actual_usdt * self.settings.exchange_fee_pct
            total_cost_from_balance = actual_usdt + entry_fee_usdt

            if total_cost_from_balance > self.balance:
                logger.warning(f"⚠️ Пропуск {symbol}: недостатньо балансу з урахуванням комісії.")
                return

            self.balance -= total_cost_from_balance
            current_balance = self.balance

            pos_to_save = Position(
                symbol=symbol, side=side, entry_price=price,
                amount_usdt=actual_usdt, amount_coins=actual_coins,
                sl=sl, tp=tp, highest_price=price, entry_time=time.time()
            )
            self.positions[symbol] = pos_to_save

        # 2. Виконуємо запит до БД ПОЗА локом
        try:
            await asyncio.to_thread(
                self.repo.save_position,
                symbol=pos_to_save.symbol,
                amount=float(pos_to_save.amount_coins),
                entry_price=float(pos_to_save.entry_price),
                highest_price=float(pos_to_save.highest_price),
                cost=float(pos_to_save.amount_usdt)
            )
            await asyncio.to_thread(self.repo.save_balance, float(current_balance))
            
            logger.info(f"🚀 [ВХІД] {side.value} {symbol} | Ціна: {price:.4f} | Об'єм: {actual_usdt:.2f} USDT | Комісія: {entry_fee_usdt:.4f}")
            if getattr(self.settings, 'ENABLE_TELEGRAM', False):
                await self.notifier.send_message(f"🟢 Відкрито: {side.value} {symbol} по {price:.4f} (Risk: {self.settings.risk_per_trade_pct*100}%)")

        except Exception as e:
            # 3. ROLLBACK: Якщо БД впала
            logger.error(f"🛑 Помилка БД при відкритті {symbol}: {e}. Здійснюю ROLLBACK.")
            async with self._lock:
                if symbol in self.positions:
                    del self.positions[symbol]
                self.balance += total_cost_from_balance
            return

    async def update_position(self, symbol: str, current_price: float) -> None:
        """Оновлює стан ордера та ініціює вихід (Race-condition safe)."""
        current_price = float(current_price)
        needs_db_update = False
        highest_to_save = 0.0
        pos: Optional[Position] = None

        # 1. Змінюємо стан об'єкта ТІЛЬКИ під локом
        async with self._lock:
            pos = self.positions.get(symbol)
            if not pos:
                return

            highest, new_sl = OrderExecutionService.calculate_trailing_stop(pos, current_price, self.settings)

            if highest > pos.highest_price:
                pos.highest_price = highest
                highest_to_save = highest
                needs_db_update = True
            
            pos.sl = new_sl

        # 2. Оновлюємо БД поза локом (якщо запізниться - не страшно, головне що в пам'яті актуально)
        if needs_db_update:
            try:
                await asyncio.to_thread(self.repo.update_position_high, symbol, float(highest_to_save))
            except Exception as e:
                logger.warning(f"⚠️ Не вдалося оновити highest_price для {symbol} у БД: {e}")

        # 3. Перевіряємо умови виходу
        exit_reason = OrderExecutionService.evaluate_exit_conditions(pos, current_price, self.settings)
        if exit_reason:
            await self._close_position(symbol, current_price, exit_reason)

    async def _close_position(self, symbol: str, close_price: float, reason: str) -> None:
        """Атомарно закриває позицію з відрахуванням комісії тейкера та зберігає історію."""
        close_price = float(close_price)
        pos: Optional[Position] = None

        # 1. Фіксуємо прибуток у пам'яті
        async with self._lock:
            if symbol not in self.positions:
                return

            pos = self.positions.pop(symbol)
            
            # --- ОБЛІК КОМІСІЇ ПРИ ВИХОДІ ---
            gross_exit_value_usdt = close_price * pos.amount_coins
            exit_fee_usdt = gross_exit_value_usdt * self.settings.exchange_fee_pct
            net_return_amount = gross_exit_value_usdt - exit_fee_usdt

            # Чистий PnL: Скільки отримали мінус скільки витратили спочатку (чиста вартість позиції + комісія входу)
            initial_cost_with_fee = pos.amount_usdt + (pos.amount_usdt * self.settings.exchange_fee_pct)
            net_pnl = net_return_amount - initial_cost_with_fee

            self.balance += net_return_amount
            current_balance = self.balance

        # 2. Зберігаємо історію в БД
        try:
            await asyncio.to_thread(self.repo.delete_position, symbol)
            await asyncio.to_thread(
                self.repo.log_trade,
                symbol=symbol,
                side=TradeSide.SELL.value,
                price=float(close_price),
                amount=float(pos.amount_coins),
                cost=float(net_return_amount),
                pnl=float(net_pnl)
            )
            await asyncio.to_thread(self.repo.save_balance, float(current_balance))

            msg = f"📉 [ВИХІД] {symbol} ({reason}) | Ціна: {close_price:.4f} | Чистий PnL: {net_pnl:+.2f} USDT"
            logger.info(msg)
            if getattr(self.settings, 'ENABLE_TELEGRAM', False):
                await self.notifier.send_message(msg)

        except Exception as e:
            # 3. ROLLBACK: Відновлюємо позицію в пам'яті
            logger.critical(f"🛑 КРИТИЧНА ПОМИЛКА БД при закритті {symbol}: {e}. Відновлюю позицію в пам'яті!")
            async with self._lock:
                self.positions[symbol] = pos
                self.balance -= net_return_amount