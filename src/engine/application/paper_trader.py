import logging
import time
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass

from src.shared.config import Settings
from src.shared.db.repositories import TradingRepository

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """Суто бізнес-модель (Domain Model). Ніякої логіки БД тут немає."""
    symbol: str
    side: str
    entry_price: float
    amount_usdt: float
    amount_coins: float
    sl: float
    tp: float
    entry_time: float = 0.0
    highest_price: float = 0.0

class PaperTrader:
    def __init__(
        self, 
        settings: Settings, 
        repo: TradingRepository, 
        notifier # Можна типізувати як BaseNotifier або TelegramNotifier
    ):
        # 💉 Dependency Injection (Впровадження залежностей)
        self.settings = settings
        self.repo = repo
        self.notifier = notifier
        
        self.positions: Dict[str, Position] = {}
        self.balance: float = 0.0
        self._is_initialized: bool = False

    async def initialize(self):
        """Асинхронний конструктор. Відновлює стан через Репозиторій."""
        # Читаємо БД в окремому потоці, щоб не блокувати asyncio loop
        self.balance = await asyncio.to_thread(self.repo.load_balance, 1000.0)
        db_positions = await asyncio.to_thread(self.repo.get_all_positions)
        
        # Rehydration (Відновлення об'єктів пам'яті з об'єктів БД)
        for db_pos in db_positions:
            self.positions[db_pos.symbol] = Position(
                symbol=db_pos.symbol,
                side="BUY", # Уточнення: у твоїй моделі DB не було side для активних, додай якщо треба
                entry_price=db_pos.entry_price,
                amount_usdt=db_pos.cost,
                amount_coins=db_pos.amount,
                sl=db_pos.entry_price * 0.95, # В ідеалі теж зберігати в БД
                tp=db_pos.entry_price * 1.05,
                highest_price=db_pos.highest_price,
                entry_time=db_pos.opened_at.timestamp()
            )
            
        self._is_initialized = True
        logger.info(f"💾 PaperTrader Ready! Баланс: {self.balance:.2f} USDT | Відновлено: {len(self.positions)}")

    async def open_position(self, symbol: str, side: str, price: float, sl: float, tp: float):
        if not self._is_initialized or symbol in self.positions:
            return

        # Використовуємо налаштування з Pydantic Config
        trade_fraction = 0.20 # Або self.settings.TRADE_FRACTION
        actual_amount = min(self.balance * trade_fraction, self.balance * 0.98)

        if actual_amount < 10.0:
            logger.warning(f"⚠️ Недостатньо коштів для {symbol}.")
            return

        amount_coins = actual_amount / price
        self.balance -= actual_amount
        
        pos = Position(
            symbol=symbol, side=side, entry_price=price, 
            amount_usdt=actual_amount, amount_coins=amount_coins, 
            sl=sl, tp=tp, entry_time=time.time(), highest_price=price
        )
        self.positions[symbol] = pos
        
        # Зберігаємо через репозиторій безпечно
        await asyncio.to_thread(
            self.repo.save_position,
            symbol=pos.symbol, amount=pos.amount_coins, 
            entry_price=pos.entry_price, highest_price=pos.highest_price, cost=pos.amount_usdt
        )
        await asyncio.to_thread(self.repo.save_balance, self.balance)
        
        logger.info(f"✅ ВІДКРИТО {side} {symbol} | Ціна: {price:.4f} | Об'єм: {actual_amount:.2f}$")
        if self.settings.ENABLE_TELEGRAM:
            await self.notifier.send_message(f"🟢 Відкрито Paper Trade: {side} {symbol} по {price}")

    async def update_position(self, symbol: str, current_price: float):
        if symbol not in self.positions:
            return
            
        pos = self.positions[symbol]
        
        if pos.side == "BUY":
            # Логіка трейлінг стопа
            if current_price > pos.highest_price:
                pos.highest_price = current_price
                await asyncio.to_thread(self.repo.update_position_high, symbol, pos.highest_price)
                
            activation_price = pos.entry_price * 1.02
            if pos.highest_price >= activation_price:
                new_sl = pos.highest_price * 0.99
                if new_sl > pos.sl:
                    pos.sl = new_sl
                    # Знову ж таки, в БД треба додати поле sl, якщо хочеш його зберігати

            # Перевірка умов виходу
            if current_price <= pos.sl:
                reason = "Trailing Stop 🛡️" if pos.sl > pos.entry_price else "Stop Loss 🛑"
                await self._close_position(symbol, current_price, reason)
            elif current_price >= pos.tp:
                await self._close_position(symbol, current_price, "Take Profit 🎯")
            elif (time.time() - pos.entry_time) > 7200: # Тут теж краще self.settings.TRADE_TIMEOUT
                await self._close_position(symbol, current_price, "Тайм-аут (2 год) ⏳")

    async def _close_position(self, symbol: str, close_price: float, reason: str):
        pos = self.positions.pop(symbol)
        pnl = (close_price - pos.entry_price) * pos.amount_coins
        return_amount = pos.amount_usdt + pnl
        self.balance += return_amount
        
        # Використовуємо репозиторій для всіх операцій з БД
        await asyncio.to_thread(self.repo.delete_position, symbol)
        await asyncio.to_thread(
            self.repo.log_trade,
            symbol=symbol, side="SELL", price=close_price, 
            amount=pos.amount_coins, cost=return_amount, pnl=pnl
        )
        await asyncio.to_thread(self.repo.save_balance, self.balance)
        
        msg = f"🔴 ЗАКРИТО {pos.side} {symbol} ({reason}) | PnL: {pnl:.2f}$"
        logger.info(msg)
        if self.settings.ENABLE_TELEGRAM:
            await self.notifier.send_message(msg)