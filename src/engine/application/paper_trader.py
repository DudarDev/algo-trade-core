# src/application/paper_trader.py
import logging
import time
import asyncio
from typing import Dict

from src.shared.config import Settings
from src.shared.db.repositories import TradingRepository
from src.engine.domain.models import Position, TradeSide

logger = logging.getLogger(__name__)

class PaperTrader:
    def __init__(self, settings: Settings, repo: TradingRepository, notifier: Any):
        self.settings = settings
        self.repo = repo
        self.notifier = notifier
        
        self.positions: Dict[str, Position] = {}
        self.balance: float = 0.0
        self._is_initialized: bool = False
        self._lock = asyncio.Lock() # Захист від Race Conditions при зміні балансу

    async def initialize(self) -> None:
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
            logger.info(f"💾 PaperTrader Ready! Баланс: {self.balance:.2f} USDT | Відновлено: {len(self.positions)}")

    async def open_position(self, symbol: str, side: TradeSide, price: float, sl: float, tp: float) -> None:
        if not self._is_initialized or symbol in self.positions:
            return

        async with self._lock:
            actual_amount = min(self.balance * self.settings.TRADE_FRACTION, self.balance * 0.98)

            if actual_amount < self.settings.MIN_TRADE_SIZE:
                logger.warning(f"⚠️ Недостатньо коштів для {symbol}.")
                return

            self.balance -= actual_amount
            
            pos = Position(
                symbol=symbol, side=side, entry_price=price, 
                amount_usdt=actual_amount, amount_coins=actual_amount / price, 
                sl=sl, tp=tp, highest_price=price
            )
            self.positions[symbol] = pos

            # Транзакційне збереження (в ідеалі має бути один метод репозиторію)
            await asyncio.to_thread(
                self.repo.save_position,
                symbol=pos.symbol, amount=pos.amount_coins, 
                entry_price=pos.entry_price, highest_price=pos.highest_price, cost=pos.amount_usdt
            )
            await asyncio.to_thread(self.repo.save_balance, self.balance)
        
        logger.info(f"✅ ВІДКРИТО {side.value} {symbol} | Ціна: {price:.4f} | Об'єм: {actual_amount:.2f}$")
        if self.settings.ENABLE_TELEGRAM:
            await self.notifier.send_message(f"🟢 Відкрито Paper Trade: {side.value} {symbol} по {price}")

    async def update_position(self, symbol: str, current_price: float) -> None:
        if symbol not in self.positions:
            return
            
        pos = self.positions[symbol]
        
        if pos.side == TradeSide.BUY:
            if current_price > pos.highest_price:
                pos.highest_price = current_price
                await asyncio.to_thread(self.repo.update_position_high, symbol, pos.highest_price)
                
            # Trailing Stop Logic (винесено магічні числа в налаштування)
            activation_price = pos.entry_price * (1 + self.settings.TRAILING_ACTIVATION_PCT)
            if pos.highest_price >= activation_price:
                new_sl = pos.highest_price * (1 - self.settings.TRAILING_OFFSET_PCT)
                if new_sl > pos.sl:
                    pos.sl = new_sl

            # Перевірка умов виходу
            if current_price <= pos.sl:
                reason = "Trailing Stop 🛡️" if pos.sl > pos.entry_price else "Stop Loss 🛑"
                await self._close_position(symbol, current_price, reason)
            elif current_price >= pos.tp:
                await self._close_position(symbol, current_price, "Take Profit 🎯")
            elif (time.time() - pos.entry_time) > self.settings.TRADE_TIMEOUT_SECONDS:
                await self._close_position(symbol, current_price, "Тайм-аут ⏳")

    async def _close_position(self, symbol: str, close_price: float, reason: str) -> None:
        async with self._lock:
            pos = self.positions.pop(symbol)
            pnl = (close_price - pos.entry_price) * pos.amount_coins
            return_amount = pos.amount_usdt + pnl
            self.balance += return_amount
            
            await asyncio.to_thread(self.repo.delete_position, symbol)
            await asyncio.to_thread(
                self.repo.log_trade,
                symbol=symbol, side=TradeSide.SELL.value, price=close_price, 
                amount=pos.amount_coins, cost=return_amount, pnl=pnl
            )
            await asyncio.to_thread(self.repo.save_balance, self.balance)
        
        msg = f"🔴 ЗАКРИТО {pos.side.value} {symbol} ({reason}) | PnL: {pnl:.2f}$"
        logger.info(msg)
        if self.settings.ENABLE_TELEGRAM:
            await self.notifier.send_message(msg)