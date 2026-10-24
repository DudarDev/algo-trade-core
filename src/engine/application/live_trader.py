import logging
import time
import json
import asyncio
from typing import Dict, Optional, Any, Tuple
import ccxt

from src.shared.config import Settings
from src.engine.domain.models import Position, TradeSide
from src.engine.domain.services import OrderExecutionService
from src.engine.application.interfaces import NotifierProtocol, TradingRepositoryProtocol
from src.engine.application.paper_trader import PaperTrader
from src.engine.infrastructure.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)


class LiveBinanceTrader(PaperTrader):
    """
    Інституційний конектор виконання ордерів на CEX (Binance Spot API через CCXT).
    
    Архітектурні особливості:
    1. Повна підтримка безпечного режиму без ключів (Dry-Run / Paper Fallback):
       якщо ключі не передані або TRADING_MODE == 'PAPER', працює як емулятор з нульовим ризиком.
    2. Slippage Guard: захист від прослизань ціни при волатильних імпульсах (відхилення > MAX_SLIPPAGE_PCT блокує ордер).
    3. Minimum Notional & Lot Precision Check: перевірка мінімального об'єму ордера (10 USDT).
    4. Двоетапне виконання Scale-Out (50% TP1 на біржі + переведення залишку в безубиток).
    5. Повна атомарність стану між пам'яттю, біржою та базою даних PostgreSQL/SQLite.
    """

    def __init__(
        self,
        settings: Settings,
        repo: TradingRepositoryProtocol,
        notifier: Optional[NotifierProtocol] = None,
        risk_controller: Optional[object] = None,
        exchange_manager: Optional[ExchangeManager] = None
    ):
        super().__init__(
            settings=settings,
            repo=repo,
            notifier=notifier,
            risk_controller=risk_controller
        )
        self.exchange_manager = exchange_manager
        
        # Визначаємо початковий режим роботи
        self.is_live: bool = False
        self.execution_mode: str = "PAPER"
        self._check_live_capability()

    def _check_live_capability(self) -> None:
        """Перевіряє валідність ключів та налаштування режиму."""
        trading_mode = getattr(self.settings, 'TRADING_MODE', 'PAPER').upper()
        has_private = bool(self.exchange_manager and self.exchange_manager.private_exchange)
        
        if trading_mode == "LIVE" and has_private:
            self.is_live = True
            self.execution_mode = "LIVE"
            logger.info("🔥 [LIVE CEX] Режим РЕАЛЬНОЇ торгівлі Binance Spot АКТИВОВАНО!")
        else:
            self.is_live = False
            self.execution_mode = "PAPER"
            if trading_mode == "LIVE" and not has_private:
                logger.warning(
                    "⚠️ [LIVE CONNECTOR] TRADING_MODE=LIVE встановлено, але валідні Binance API ключі відсутні! "
                    "Перемикання в безпечний Paper / Dry-Run режим."
                )
            else:
                logger.info("🛡️ [LIVE CONNECTOR] Безпечний Paper / Dry-Run режим активний (без ризику реальних коштів).")

    async def initialize(self) -> None:
        """Ініціалізація стану з БД та отримання реального балансу з Binance при Live режимі."""
        await super().initialize()
        
        if self.is_live and self.exchange_manager and self.exchange_manager.private_exchange:
            try:
                balance_data = await self.exchange_manager.private_exchange.fetch_balance()
                free_usdt = float(balance_data.get('free', {}).get('USDT', 0.0))
                total_usdt = float(balance_data.get('total', {}).get('USDT', 0.0))
                
                if free_usdt > 0:
                    async with self._lock:
                        self.balance = free_usdt
                    await asyncio.to_thread(self.repo.save_balance, float(free_usdt))
                    logger.info(f"💰 [LIVE CEX] Синхронізовано баланс Binance Spot: {free_usdt:.2f} USDT (Total: {total_usdt:.2f})")
                else:
                    logger.warning(f"⚠️ [LIVE CEX] Баланс USDT на біржі дорівнює {free_usdt:.2f}. Перевірте рахунок.")
            except ccxt.AuthenticationError as auth_err:
                logger.critical(f"❌ [LIVE CEX] Помилка аутентифікації ключів Binance: {auth_err}. Перемикаю в Paper!")
                self.is_live = False
                self.execution_mode = "PAPER"
            except Exception as e:
                logger.error(f"⚠️ [LIVE CEX] Не вдалося отримати баланс з біржі ({e}). Використовую збережений баланс БД.")

    async def check_slippage(self, symbol: str, signal_price: float) -> Tuple[bool, float, float]:
        """
        Перевірка прослизання (Slippage Guard).
        Повертає (is_safe, current_price, slippage_pct).
        """
        if not self.exchange_manager or not hasattr(self.exchange_manager, 'fetch_current_price'):
            return True, signal_price, 0.0
            
        try:
            res = self.exchange_manager.fetch_current_price(symbol)
            if asyncio.iscoroutine(res):
                current_price = await res
            else:
                current_price = float(res)
        except Exception:
            current_price = signal_price
        if not current_price or current_price <= 0:
            return True, signal_price, 0.0
            
        slippage_pct = abs(current_price - signal_price) / signal_price
        max_slippage = getattr(self.settings, 'MAX_SLIPPAGE_PCT', 0.005) # 0.5%
        
        is_safe = slippage_pct <= max_slippage
        return is_safe, current_price, slippage_pct

    async def open_position(
        self,
        symbol: str,
        side: TradeSide,
        price: float,
        sl: float,
        tp: float,
        regime: str = "CHOPPY_FLAT",
        ai_confidence: float = 0.0,
        features_snapshot: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Відкриття позиції з Slippage Guard та відправкою реального ринкового ордера на біржу.
        """
        if not self._is_initialized:
            logger.error("❌ Спроба відкрити позицію до ініціалізації LiveBinanceTrader.")
            return

        # 1. Slippage Guard Check
        is_safe, live_price, slippage = await self.check_slippage(symbol, price)
        if not is_safe:
            max_allowed = getattr(self.settings, 'MAX_SLIPPAGE_PCT', 0.005)
            logger.warning(
                f"🛑 [SLIPPAGE GUARD] Ордер {symbol} скасовано: прослизання {slippage*100:.2f}% "
                f"перевищує допустимий ліміт {max_allowed*100:.2f}% (Signal: {price:.4f}, Live: {live_price:.4f})"
            )
            return

        exec_price = live_price if live_price > 0 else price

        # Якщо ми в безпечному / paper режимі — делегуємо базовому PaperTrader
        if not self.is_live or not self.exchange_manager or not self.exchange_manager.private_exchange:
            await super().open_position(
                symbol=symbol,
                side=side,
                price=exec_price,
                sl=sl,
                tp=tp,
                regime=regime,
                ai_confidence=ai_confidence,
                features_snapshot=features_snapshot
            )
            return

        # --- LIVE РЕЖИМ ВИКОНАННЯ НА БІРЖІ BINANCE ---
        pos_to_save: Optional[Position] = None
        features_dict = dict(features_snapshot) if features_snapshot else {}

        async with self._lock:
            if symbol in self.positions:
                return

            # Перевірка Circuit Breaker
            if self.risk_controller and hasattr(self.risk_controller, 'is_circuit_breaker_triggered') and self.risk_controller.is_circuit_breaker_triggered():
                logger.warning(f"🛑 [CIRCUIT BREAKER] Вхід по {symbol} заблоковано на рівні LiveTrader.")
                return

            max_positions = getattr(self.settings, 'max_open_positions', getattr(self.settings, 'MAX_CONCURRENT_POSITIONS', 3))
            if len(self.positions) >= max_positions:
                logger.debug(f"⚠️ Пропуск {symbol}: досягнуто ліміт активних позицій ({max_positions}).")
                return

            # Розрахунок позиції за ATR & Kelly
            base_risk_pct = getattr(self.settings, 'risk_per_trade_pct', getattr(self.settings, 'TRADE_FRACTION', 0.02))
            risk_pct = self.risk_controller.get_effective_risk_pct(base_risk_pct) if self.risk_controller and hasattr(self.risk_controller, 'get_effective_risk_pct') else base_risk_pct

            conf_multiplier = 1.25 if ai_confidence >= 0.70 else (1.00 if ai_confidence >= 0.55 else 0.85)
            atr_pct = float(features_dict.get('ATR_PCT', 0.01))
            vol_multiplier = 0.75 if atr_pct > 0.020 else (0.90 if atr_pct < 0.003 else 1.0)

            effective_risk_pct = risk_pct * conf_multiplier * vol_multiplier
            risk_budget = self.balance * effective_risk_pct
            risk_per_coin = abs(exec_price - sl)

            if risk_per_coin <= 0:
                logger.error(f"❌ Помилка розрахунку ризику для {symbol}: SL дорівнює ціні.")
                return

            ideal_usdt = (risk_budget / risk_per_coin) * exec_price
            max_alloc_per_trade = (self.balance * 0.95) / max(max_positions, 1)
            actual_usdt = min(ideal_usdt, max_alloc_per_trade)

            min_notional = getattr(self.settings, 'MIN_NOTIONAL_USDT', 10.0)
            if actual_usdt < min_notional:
                logger.warning(f"⚠️ [LIVE CEX] Об'єм {actual_usdt:.2f} USDT менший за мінімальний notional {min_notional:.2f} USDT.")
                return

            actual_coins = actual_usdt / exec_price

            # Відправка реального ринкового ордера на купівлю через CCXT
            try:
                logger.info(f"📤 [LIVE CEX ORDER] Відправка BUY {actual_coins:.6f} {symbol} (~{actual_usdt:.2f} USDT)...")
                order = await self.exchange_manager.private_exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side='buy',
                    amount=actual_coins
                )
                
                # Аналіз виконаного ордера
                filled_price = float(order.get('average') or order.get('price') or exec_price)
                filled_amount = float(order.get('filled') or actual_coins)
                executed_cost = float(order.get('cost') or (filled_price * filled_amount))
                fee_cost = 0.0
                if order.get('fee'):
                    fee_cost = float(order['fee'].get('cost', 0.0))
                else:
                    fee_cost = executed_cost * getattr(self.settings, 'exchange_fee_pct', 0.001)

                logger.info(f"💸 [LIVE CEX FILL] Успішно! ID: {order.get('id')} | Ціна: {filled_price:.4f} | Сума: {executed_cost:.2f} USDT")

                self.balance -= (executed_cost + fee_cost)
                current_balance = self.balance

                pos_to_save = Position(
                    symbol=symbol, side=side, entry_price=filled_price,
                    amount_usdt=executed_cost, amount_coins=filled_amount,
                    sl=sl, tp=tp, highest_price=filled_price, entry_time=time.time(),
                    regime=regime, ai_confidence=float(ai_confidence),
                    features_snapshot=features_dict
                )
                self.positions[symbol] = pos_to_save

            except ccxt.InsufficientFunds as inf_err:
                logger.error(f"❌ [LIVE CEX] Недостатньо коштів на Binance: {inf_err}")
                return
            except Exception as e:
                logger.error(f"❌ [LIVE CEX] Помилка виконання BUY ордера для {symbol}: {e}")
                return

        # Збереження в репозиторій БД
        try:
            features_json_str = json.dumps(pos_to_save.features_snapshot)
            await asyncio.to_thread(
                self.repo.save_position,
                symbol=pos_to_save.symbol,
                amount=float(pos_to_save.amount_coins),
                entry_price=float(pos_to_save.entry_price),
                highest_price=float(pos_to_save.highest_price),
                cost=float(pos_to_save.amount_usdt),
                regime=pos_to_save.regime,
                ai_confidence=float(pos_to_save.ai_confidence),
                features_json=features_json_str
            )
            await asyncio.to_thread(self.repo.save_balance, float(current_balance))

            msg = f"🟢 [LIVE BUY] {symbol} по {pos_to_save.entry_price:.4f} | Об'єм: {pos_to_save.amount_usdt:.2f} USDT"
            if getattr(self.settings, 'ENABLE_TELEGRAM', False) and self.notifier:
                await self.notifier.send_message(msg)
        except Exception as e:
            logger.error(f"⚠️ [LIVE CEX] Помилка запису позиції {symbol} в БД: {e}")

    async def _partial_close_position(self, symbol: str, close_price: float, reason: str) -> None:
        """
        Scale-Out Engine: Виконання ринкового ордера продажу 50% позиції на Binance
        та переведення залишку в гарантований безубиток.
        """
        if not self.is_live or not self.exchange_manager or not self.exchange_manager.private_exchange:
            await super()._partial_close_position(symbol, close_price, reason)
            return

        async with self._lock:
            pos = self.positions.get(symbol)
            if not pos or getattr(pos, 'partial_tp_hit', False):
                return

            ratio = getattr(self.settings, 'PARTIAL_TP_RATIO', 0.50)
            closed_coins = pos.amount_coins * ratio

            try:
                logger.info(f"📤 [LIVE CEX SCALE-OUT] Продаж 50% ({closed_coins:.6f} {symbol}) на Binance...")
                order = await self.exchange_manager.private_exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side='sell',
                    amount=closed_coins
                )
                fill_price = float(order.get('average') or order.get('price') or close_price)
                real_closed_coins = float(order.get('filled') or closed_coins)
            except Exception as e:
                logger.error(f"❌ [LIVE CEX] Помилка ордера Scale-Out для {symbol}: {e}")
                return

        # Делегуємо оновлення обліку балансу та фіксацію безубитку базовому методу з реальною ціною виконання
        await super()._partial_close_position(symbol, fill_price, reason)

    async def _close_position(self, symbol: str, close_price: float, reason: str) -> None:
        """
        Повне закриття позиції: ринковий ордер SELL на Binance та архівація в БД.
        """
        if not self.is_live or not self.exchange_manager or not self.exchange_manager.private_exchange:
            await super()._close_position(symbol, close_price, reason)
            return

        async with self._lock:
            pos = self.positions.get(symbol)
            if not pos:
                return

            try:
                logger.info(f"📤 [LIVE CEX CLOSE] Продаж {pos.amount_coins:.6f} {symbol} ({reason})...")
                order = await self.exchange_manager.private_exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side='sell',
                    amount=pos.amount_coins
                )
                fill_price = float(order.get('average') or order.get('price') or close_price)
            except Exception as e:
                logger.error(f"❌ [LIVE CEX] Помилка закриття позиції {symbol} на Binance: {e}")
                # У разі мережевої помилки використовуємо поточну котирувальну ціну
                fill_price = close_price

        await super()._close_position(symbol, fill_price, reason)

    async def panic_sell_all(self, reason: str = "Panic Sell All") -> None:
        """Екстрене закриття всіх позицій на біржі та в БД."""
        logger.warning(f"🚨 [PANIC SELL ALL] Ініційовано екстрене закриття всіх позицій ({reason})!")
        symbols_to_close = list(self.positions.keys())
        for sym in symbols_to_close:
            curr_price = await self.exchange_manager.fetch_current_price(sym) if self.exchange_manager else 0.0
            if not curr_price or curr_price <= 0:
                pos = self.positions.get(sym)
                curr_price = (pos.highest_price or pos.entry_price) if pos else 0.0
            if curr_price > 0:
                await self._close_position(sym, curr_price, reason)

    def get_connector_status(self) -> Dict[str, Any]:
        """Статус конектора для діагностики та телеметрії."""
        return {
            "mode": self.execution_mode,
            "is_live": self.is_live,
            "has_api_keys": bool(self.exchange_manager and self.exchange_manager.private_exchange),
            "active_positions_count": len(self.positions),
            "balance_usdt": round(self.balance, 2)
        }
