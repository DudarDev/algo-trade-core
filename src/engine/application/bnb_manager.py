# src/engine/application/bnb_manager.py
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Protocol, Optional, Any

logger = logging.getLogger(__name__)


class SpotBnbExchangePort(Protocol):
    async def get_spot_free_balance(self, asset: str) -> float: ...
    async def get_spot_price(self, symbol: str) -> float: ...
    async def buy_spot_market_quote(self, symbol: str, quote_usdt: float) -> dict: ...


class BNBAutoBalanceManager:
    """
    Автоматичний менеджер балансу BNB для оптимізації біржових комісій.
    - 25% знижка на спотову комісію Binance.
    - 10% знижка на USD-M Futures комісію Binance.
    
    Запобіжники:
    1. Поріг min_bnb_usdt ($3.0) — докуповує лише при реальному виснаженні залишку.
    2. Обсяг top_up_usdt ($10.0) — гарантовано вище MIN_NOTIONAL ліміту ($5.0).
    3. Cooldown (60 хв) — захист від повторних покупок при затримках кешу API біржі.
    4. Резерв min_free_usdt_reserve ($20.0) — не чіпає маржинальний резерв системи.
    5. Ізоляція режимів — у PAPER-режимі реальні транзакції не виконуються.
    """
    def __init__(
        self,
        exchange: SpotBnbExchangePort,
        trading_mode: str = "PAPER",
        min_bnb_usdt: float = 3.0,
        top_up_usdt: float = 10.0,
        min_free_usdt_reserve: float = 20.0,
        cooldown_minutes: int = 60,
    ):
        self.exchange = exchange
        self.trading_mode = trading_mode.upper()
        self.min_bnb_usdt = min_bnb_usdt
        self.top_up_usdt = top_up_usdt
        self.min_free_usdt_reserve = min_free_usdt_reserve
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self._last_top_up_at: Optional[datetime] = None

    async def check_and_refill(self, notify_callback=None) -> bool:
        """
        Перевіряє баланс BNB на споті та докуповує за потреби.
        Повертає True, якщо поповнення відбулося.
        """
        if self.trading_mode != "LIVE":
            return False

        now = datetime.now(timezone.utc)
        if self._last_top_up_at and (now - self._last_top_up_at) < self.cooldown:
            return False

        try:
            bnb_qty = await self.exchange.get_spot_free_balance("BNB")
            bnb_price = await self.exchange.get_spot_price("BNB/USDT")
            bnb_value_usdt = bnb_qty * bnb_price

            if bnb_value_usdt >= self.min_bnb_usdt:
                return False

            free_usdt = await self.exchange.get_spot_free_balance("USDT")
            if free_usdt < (self.top_up_usdt + self.min_free_usdt_reserve):
                logger.warning(
                    f"⚠️ [BNB Manager] Low BNB (${bnb_value_usdt:.2f} < ${self.min_bnb_usdt:.2f}), "
                    f"але недостатньо вільного USDT (${free_usdt:.2f} < ${self.top_up_usdt + self.min_free_usdt_reserve:.2f})"
                )
                return False

            logger.info(
                f"⛽ [BNB Manager] Баланс BNB=${bnb_value_usdt:.2f} < ${self.min_bnb_usdt:.2f}. "
                f"Докуповуємо BNB на ${self.top_up_usdt:.2f} USDT..."
            )
            order = await self.exchange.buy_spot_market_quote("BNB/USDT", self.top_up_usdt)
            self._last_top_up_at = now

            if notify_callback:
                msg = (
                    f"⛽ <b>[BNB AUTO-REFILL: ЗНИЖКА КОМІСІЙ]</b>\n\n"
                    f"Баланс BNB впав до: <b>${bnb_value_usdt:.2f}</b>\n"
                    f"Докуплено на: <b>${self.top_up_usdt:.2f} USDT</b>\n"
                    f"Order ID: <code>{order.get('id', 'N/A')}</code>\n"
                    f"Знижка біржі: <i>-25% Spot / -10% Futures активовано!</i>"
                )
                try:
                    res = notify_callback(msg)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as ne:
                    logger.warning(f"⚠️ [BNB Manager] Помилка відправки сповіщення: {ne}")

            return True
        except Exception as e:
            logger.error(f"❌ [BNB Manager] Помилка перевірки/докупівлі BNB: {e}", exc_info=True)
            return False
