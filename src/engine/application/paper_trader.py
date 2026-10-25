import logging
import time
import json
import asyncio
from typing import Dict, Optional

from src.shared.config import Settings
from src.engine.domain.models import Position, TradeSide
from src.engine.domain.services import OrderExecutionService
from src.engine.application.interfaces import NotifierProtocol, TradingRepositoryProtocol

logger = logging.getLogger(__name__)

class PaperTrader:
    def __init__(
        self,
        settings: Settings,
        repo: TradingRepositoryProtocol,
        notifier: NotifierProtocol,
        risk_controller: Optional[object] = None
    ):
        self.settings = settings
        self.repo = repo
        self.notifier = notifier
        self.risk_controller = risk_controller

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

            # Відновлення адаптивного ризик-контролера з історії закритих угод
            if self.risk_controller and hasattr(self.repo, 'get_closed_trades'):
                try:
                    closed_trades = await asyncio.to_thread(self.repo.get_closed_trades, 20)
                    self.risk_controller.initialize_from_history(closed_trades, self.balance)
                except Exception as e:
                    logger.warning(f"⚠️ Не вдалося ініціалізувати AdaptiveRiskController з історії: {e}")

            for db_pos in db_positions:
                feat_snapshot = {}
                raw_features = getattr(db_pos, 'features_json', '{}')
                if raw_features:
                    try:
                        feat_snapshot = json.loads(raw_features)
                    except Exception:
                        feat_snapshot = {}

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
                    entry_time=db_pos.opened_at.timestamp(),
                    regime=getattr(db_pos, 'regime', 'CHOPPY_FLAT'),
                    ai_confidence=getattr(db_pos, 'ai_confidence', 0.0),
                    features_snapshot=feat_snapshot,
                    partial_tp_hit=bool(getattr(db_pos, 'partial_tp_hit', 0))
                )

            self._is_initialized = True
            logger.info(f"💾 PaperTrader успішно ініціалізовано. Баланс: {self.balance:.2f} USDT | Активних позицій: {len(self.positions)}")

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
        """Відкриває позицію із динамічним ризик-менеджментом, збором зрізу фіч та обліком комісій."""
        if not self._is_initialized:
            logger.error("❌ Спроба відкрити позицію до ініціалізації PaperTrader.")
            return

        price, sl, tp = float(price), float(sl), float(tp)
        pos_to_save: Optional[Position] = None
        features_dict = dict(features_snapshot) if features_snapshot else {}

        # 1. Оновлюємо стан у пам'яті ПІД ЛОКОМ
        async with self._lock:
            if symbol in self.positions:
                return

            # 0. Перевірка аварійного рубильника (Circuit Breaker -3% Daily Loss Protection)
            if self.risk_controller and hasattr(self.risk_controller, 'is_circuit_breaker_triggered') and self.risk_controller.is_circuit_breaker_triggered():
                logger.warning(f"🛑 [CIRCUIT BREAKER ACTIVE] Вхід по {symbol} заблоковано: денний ліміт втрат (-3%) вичерпано!")
                return

            # Перевірка на ліміт одночасних угод (захист капіталу від корекції всього ринку)
            max_positions = getattr(self.settings, 'max_open_positions', getattr(self.settings, 'MAX_CONCURRENT_POSITIONS', 3))
            if len(self.positions) >= max_positions:
                logger.debug(f"⚠️ Пропуск {symbol}: досягнуто ліміт активних позицій ({max_positions}).")
                return

            # --- РОЗРАХУНОК ОБ'ЄМУ (POSITION SIZING ІЗ ДИНАМІЧНИМ РИЗИКОМ, ATR & KELLY) ---
            base_risk_pct = getattr(self.settings, 'risk_per_trade_pct', getattr(self.settings, 'TRADE_FRACTION', 0.02))
            if self.risk_controller and hasattr(self.risk_controller, 'get_effective_risk_pct'):
                risk_pct = self.risk_controller.get_effective_risk_pct(base_risk_pct)
            else:
                risk_pct = base_risk_pct

            # Dynamic Kelly Confidence Multiplier (масштабуємо ризик за впевненістю ШІ)
            conf_multiplier = 1.0
            if ai_confidence >= 0.70:
                conf_multiplier = 1.25  # висока ймовірність -> збільшуємо розмір
            elif ai_confidence >= 0.55:
                conf_multiplier = 1.00
            elif ai_confidence > 0.0:
                conf_multiplier = 0.85  # низька впевненість -> консервативний лот

            # Volatility Sizing (зменшення розміру при надмірній волатильності ATR для захисту від прослизань)
            atr_pct = float(features_dict.get('ATR_PCT', 0.01))
            vol_multiplier = 1.0
            if atr_pct > 0.020:
                vol_multiplier = 0.75   # високоволатильний шум -> ріжемо об'єм на 25%
            elif atr_pct < 0.003:
                vol_multiplier = 0.90   # занадто мертвий ринок

            effective_risk_pct = risk_pct * conf_multiplier * vol_multiplier
            risk_budget = self.balance * effective_risk_pct
            risk_per_coin = abs(price - sl)

            if risk_per_coin <= 0:
                logger.error(f"❌ Помилка розрахунку ризику для {symbol}: ціна входу дорівнює SL.")
                return

            ideal_coins = risk_budget / risk_per_coin
            ideal_usdt = ideal_coins * price

            # Hard Dollar Stop Cap: обмежуємо максимальний доларовий збиток за угоду ($3.50 max)
            max_loss_cap = getattr(self.settings, 'MAX_TRADE_LOSS_USDT', None)
            if max_loss_cap is not None and risk_per_coin > 0:
                capped_coins = max_loss_cap / risk_per_coin
                ideal_usdt = min(ideal_usdt, capped_coins * price)

            # Капаємо розмір позиції з урахуванням диверсифікації портфеля (не більше 1/max_positions на угоду)
            max_alloc_per_trade = (self.balance * 0.95) / max(max_positions, 1)
            actual_usdt = min(ideal_usdt, max_alloc_per_trade)
            actual_coins = actual_usdt / price

            if actual_usdt < 10.0:  # Hard limit для більшості бірж
                logger.warning(f"⚠️ Пропуск {symbol}: розрахований об'єм {actual_usdt:.2f} USDT занадто малий.")
                return

            # --- ОБЛІК КОМІСІЇ ---
            fee_pct = getattr(self.settings, 'exchange_fee_pct', 0.001)
            entry_fee_usdt = actual_usdt * fee_pct
            total_cost_from_balance = actual_usdt + entry_fee_usdt

            if total_cost_from_balance > self.balance:
                logger.warning(f"⚠️ Пропуск {symbol}: недостатньо балансу з урахуванням комісії.")
                return

            self.balance -= total_cost_from_balance
            current_balance = self.balance

            pos_to_save = Position(
                symbol=symbol, side=side, entry_price=price,
                amount_usdt=actual_usdt, amount_coins=actual_coins,
                sl=sl, tp=tp, highest_price=price, entry_time=time.time(),
                regime=regime, ai_confidence=float(ai_confidence),
                features_snapshot=features_dict
            )
            self.positions[symbol] = pos_to_save

        # 2. Виконуємо запит до БД ПОЗА локом (зберігаємо повний зріз фіч та режим)
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
            
            logger.info(
                f"🚀 [ВХІД] {side.value} {symbol} | Ціна: {price:.4f} | Об'єм: {actual_usdt:.2f} USDT | "
                f"Risk: {risk_pct*100:.2f}% | Regime: {regime} | Conf: {ai_confidence:.2f} | Комісія: {entry_fee_usdt:.4f}"
            )
            if getattr(self.settings, 'ENABLE_TELEGRAM', False) and self.notifier:
                await self.notifier.send_message(f"🟢 Відкрито: {side.value} {symbol} по {price:.4f} (Risk: {risk_pct*100:.1f}%, Conf: {ai_confidence:.2f})")

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

        # 3. Перевіряємо умови виходу (Scale-Out або повне закриття)
        exit_reason = OrderExecutionService.evaluate_exit_conditions(pos, current_price, self.settings)
        if exit_reason:
            if exit_reason.startswith("Take Profit 1"):
                await self._partial_close_position(symbol, current_price, exit_reason)
            else:
                await self._close_position(symbol, current_price, exit_reason)

    async def _partial_close_position(self, symbol: str, close_price: float, reason: str) -> None:
        """
        Scale-Out Engine: Часткове закриття 50% позиції на TP1.
        Фіксує реальний кеш на баланс, переводить залишок у безубиток, оновлює активну позицію в БД та логує трейд.
        """
        close_price = float(close_price)
        pos: Optional[Position] = None
        closed_coins = 0.0
        closed_cost = 0.0
        net_return_amount = 0.0
        net_pnl = 0.0
        current_balance = 0.0

        # 1. Фіксуємо частковий прибуток у пам'яті ПІД ЛОКОМ
        async with self._lock:
            pos = self.positions.get(symbol)
            if not pos or getattr(pos, 'partial_tp_hit', False):
                return

            ratio = getattr(self.settings, 'PARTIAL_TP_RATIO', 0.50)
            closed_coins = pos.amount_coins * ratio
            closed_cost = pos.amount_usdt * ratio

            fee_pct = getattr(self.settings, 'exchange_fee_pct', 0.001)
            gross_exit_value_usdt = close_price * closed_coins
            exit_fee_usdt = gross_exit_value_usdt * fee_pct
            net_return_amount = gross_exit_value_usdt - exit_fee_usdt

            # Початкова вартість половини з урахуванням вхідної комісії
            initial_cost_half_with_fee = closed_cost + (closed_cost * fee_pct)
            net_pnl = net_return_amount - initial_cost_half_with_fee

            # Нараховуємо прибуток на живий баланс
            self.balance += net_return_amount
            current_balance = self.balance

            # Модифікуємо позицію: зменшуємо об'єм, ставимо прапорець та переводимо SL у безубиток
            pos.amount_coins -= closed_coins
            pos.amount_usdt -= closed_cost
            pos.partial_tp_hit = True
            be_sl = pos.entry_price * 1.0025
            if be_sl > pos.sl:
                pos.sl = be_sl

        # 2. Оновлюємо базу даних ПОЗА ЛОКОМ
        try:
            target_label = 1 if net_pnl > 0 else 0
            features_json_str = json.dumps(pos.features_snapshot) if pos.features_snapshot else "{}"

            # Записуємо частковий закритий трейд у журнал
            await asyncio.to_thread(
                self.repo.log_trade,
                symbol=symbol,
                side=TradeSide.SELL.value,
                price=float(close_price),
                amount=float(closed_coins),
                cost=float(net_return_amount),
                pnl=float(net_pnl),
                exit_reason=str(reason),
                regime=getattr(pos, 'regime', 'CHOPPY_FLAT'),
                ai_confidence=float(getattr(pos, 'ai_confidence', 0.0)),
                target_label=target_label,
                features_json=features_json_str
            )

            # Оновлюємо параметри залишку позиції в таблиці активних позицій
            await asyncio.to_thread(
                self.repo.save_position,
                symbol=symbol,
                amount=float(pos.amount_coins),
                entry_price=float(pos.entry_price),
                highest_price=float(pos.highest_price),
                cost=float(pos.amount_usdt),
                regime=pos.regime,
                ai_confidence=float(pos.ai_confidence),
                features_json=features_json_str,
                partial_tp_hit=1
            )
            await asyncio.to_thread(self.repo.save_balance, float(current_balance))

            msg = (
                f"🎯 [ЧАСТКОВИЙ ТЕЙК (50%)] {symbol} | Ціна: {close_price:.4f} | "
                f"Зафіксовано PnL: {net_pnl:+.2f} USDT | Залишок {pos.amount_usdt:.2f} USDT захищено в безубитку 🔒"
            )
            logger.info(msg)
            if getattr(self.settings, 'ENABLE_TELEGRAM', False) and self.notifier:
                await self.notifier.send_message(msg)

        except Exception as e:
            logger.error(f"⚠️ Помилка оновлення БД при частковому закритті {symbol}: {e}")

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
            fee_pct = getattr(self.settings, 'exchange_fee_pct', 0.001)
            exit_fee_usdt = gross_exit_value_usdt * fee_pct
            net_return_amount = gross_exit_value_usdt - exit_fee_usdt

            # Чистий PnL: Скільки отримали мінус скільки витратили спочатку (чиста вартість позиції + комісія входу)
            initial_cost_with_fee = pos.amount_usdt + (pos.amount_usdt * fee_pct)
            net_pnl = net_return_amount - initial_cost_with_fee

            self.balance += net_return_amount
            current_balance = self.balance

        # 2. Зберігаємо історію в БД (Feature Store & Continuous Learning)
        try:
            target_label = 1 if net_pnl > 0 else 0
            features_json_str = json.dumps(pos.features_snapshot) if pos.features_snapshot else "{}"
            
            # Оновлюємо стан адаптивного ризик-контролера (Етап 3)
            if self.risk_controller and hasattr(self.risk_controller, 'record_trade_result'):
                try:
                    self.risk_controller.record_trade_result(
                        net_pnl=float(net_pnl),
                        target_label=target_label,
                        balance_after_trade=float(current_balance)
                    )
                except Exception as rc_err:
                    logger.debug(f"Помилка оновлення AdaptiveRiskController: {rc_err}")

            await asyncio.to_thread(self.repo.delete_position, symbol)
            await asyncio.to_thread(
                self.repo.log_trade,
                symbol=symbol,
                side=TradeSide.SELL.value,
                price=float(close_price),
                amount=float(pos.amount_coins),
                cost=float(net_return_amount),
                pnl=float(net_pnl),
                exit_reason=str(reason),
                regime=getattr(pos, 'regime', 'CHOPPY_FLAT'),
                ai_confidence=float(getattr(pos, 'ai_confidence', 0.0)),
                target_label=target_label,
                features_json=features_json_str
            )
            await asyncio.to_thread(self.repo.save_balance, float(current_balance))

            result_tag = "WIN" if target_label == 1 else "LOSS"
            msg = f"📉 [ВИХІД] {symbol} ({reason}) [{result_tag}] | Ціна: {close_price:.4f} | Чистий PnL: {net_pnl:+.2f} USDT"
            logger.info(msg)
            if getattr(self.settings, 'ENABLE_TELEGRAM', False) and self.notifier:
                await self.notifier.send_message(msg)

        except Exception as e:
            # 3. ROLLBACK: Відновлюємо позицію в пам'яті
            logger.critical(f"🛑 КРИТИЧНА ПОМИЛКА БД при закритті {symbol}: {e}. Відновлюю позицію в пам'яті!")
            async with self._lock:
                self.positions[symbol] = pos
                self.balance -= net_return_amount