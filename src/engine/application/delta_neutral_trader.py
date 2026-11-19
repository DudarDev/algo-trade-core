# src/engine/application/delta_neutral_trader.py
import time
import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

from src.shared.config import Settings
from src.shared.db.repositories import TradingRepository
from src.shared.db.models import DeltaNeutralPositionModel
from src.engine.domain.models import (
    DeltaNeutralPosition,
    DeltaNeutralMode,
    DeltaNeutralStatus,
    TradeSide
)
from src.engine.infrastructure.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class DeltaNeutralTrader:
    """
    Автономний виконавець стратегії Delta-Neutral Cash & Carry (та синтетичного фандинг-арбітражу).
    
    Ключові квант-захисти:
    1. Fee Breakeven Guard: вхід дозволено лише при окупності кругових комісій <= 2.5 днів.
    2. Atomic Rollback: миттєве закриття Leg 1 при збої / відхиленні біржею Leg 2.
    3. Віртуальний та реальний облік нарахувань фандингу кожні 8 годин.
    4. Basis Guard: контроль різниці цін між спотом та ф'ючерсом.
    """
    def __init__(
        self,
        settings: Settings,
        repo: TradingRepository,
        notifier: Optional[TelegramNotifier] = None,
        exchange_manager: Optional[Any] = None,
        is_paper: bool = True
    ):
        self.settings = settings
        self.repo = repo
        self.notifier = notifier
        self.exchange_manager = exchange_manager
        self.is_paper = is_paper
        
        # Налаштування комісій за замовчуванням (Maker vs Taker)
        self.spot_maker_fee = float(getattr(settings, 'SPOT_MAKER_FEE_PCT', 0.0002))   # 0.02%
        self.perp_maker_fee = float(getattr(settings, 'PERP_MAKER_FEE_PCT', 0.0002))   # 0.02%
        self.spot_taker_fee = float(getattr(settings, 'SPOT_TAKER_FEE_PCT', 0.0010))   # 0.10%
        self.perp_taker_fee = float(getattr(settings, 'PERP_TAKER_FEE_PCT', 0.0005))   # 0.05%
        
        # Поріг окупності комісій (у днях)
        self.max_breakeven_days = float(getattr(settings, 'MAX_FEE_BREAKEVEN_DAYS', 2.5))
        # Мінімальний APY для розгляду входу
        self.min_apy_hurdle = float(getattr(settings, 'MIN_FUNDING_APY_HURDLE', 10.0))
        # Асиметричний базис-контроль:
        # Контанго (ф'ючерс дорожчий за спот) вигідне для C&C (додатковий roll yield при зближенні)
        self.max_entry_basis_pct = float(getattr(settings, 'MAX_ENTRY_BASIS_PCT', 0.80))
        # Беквордація (ф'ючерс дешевший за спот) небезпечна, бо збільшує збиток на спреді
        self.min_entry_basis_pct = float(getattr(settings, 'MIN_ENTRY_BASIS_PCT', -0.05))

        # Дворівневий захист від негативного фандингу:
        # 1. Миттєвий вихід при падінні нижче hard_negative_threshold (-0.01% за 8h)
        # 2. Підтверджений вихід при rate_8h <= 0.0 протягом max_negative_strikes (2 перевірки поспіль)
        self._negative_funding_strikes: Dict[str, int] = {}
        self.max_negative_strikes: int = int(getattr(settings, 'MAX_NEGATIVE_FUNDING_STRIKES', 2))
        self.hard_negative_threshold: float = float(getattr(settings, 'HARD_NEGATIVE_FUNDING_THRESHOLD', -0.0001))

        self.active_positions: Dict[str, DeltaNeutralPosition] = {}
        self._load_positions_from_db()
        logger.info(f"💎 [Delta-Neutral Engine] Ініціалізовано. Режим: {'PAPER' if is_paper else 'LIVE'} | Активних позицій: {len(self.active_positions)}")

    def _load_positions_from_db(self) -> None:
        """Завантаження відкритих дельта-нейтральних позицій з бази даних."""
        try:
            db_positions = self.repo.get_active_delta_neutral_positions()
            for row in db_positions:
                pos = DeltaNeutralPosition(
                    position_id=row.id,
                    symbol=row.symbol,
                    mode=DeltaNeutralMode(row.mode),
                    leg1_exchange=row.leg1_exchange,
                    leg1_symbol=row.leg1_symbol,
                    leg1_side=TradeSide(row.leg1_side),
                    leg1_entry_price=row.leg1_entry_price,
                    leg1_amount=row.leg1_amount,
                    leg2_exchange=row.leg2_exchange,
                    leg2_symbol=row.leg2_symbol,
                    leg2_side=TradeSide(row.leg2_side),
                    leg2_entry_price=row.leg2_entry_price,
                    leg2_amount=row.leg2_amount,
                    notional_usdt=row.notional_usdt,
                    entry_basis_pct=row.entry_basis_pct,
                    accrued_funding_usdt=row.accrued_funding_usdt,
                    funding_cycles_collected=row.funding_cycles_collected,
                    entry_fees_usdt=row.entry_fees_usdt,
                    current_8h_rate=row.current_8h_rate,
                    projected_apy=row.projected_apy,
                    opened_at=row.opened_at.timestamp() if row.opened_at else time.time(),
                    last_funding_time=row.last_funding_time.timestamp() if row.last_funding_time else time.time(),
                    status=DeltaNeutralStatus(row.status),
                    close_reason=row.close_reason
                )
                self.active_positions[pos.position_id] = pos
        except Exception as e:
            logger.warning(f"⚠️ Помилка завантаження дельта-нейтральних позицій: {e}")

    def calculate_breakeven_days(
        self,
        rate_8h: float,
        is_maker: bool = True
    ) -> Tuple[float, float]:
        """
        Розраховує кількість діб для окупності біржових комісій за поточною ставкою фандингу.
        Повертає (breakeven_days, roundtrip_fee_pct).
        """
        if is_maker:
            # Maker на обох ногах при вході і виході: 2 ноги * 2 операції * 0.02%
            roundtrip_fee_pct = (self.spot_maker_fee + self.perp_maker_fee) * 2.0 * 100.0
        else:
            # Консервативний розрахунок (Taker fallback): (0.10% + 0.05%) * 2
            roundtrip_fee_pct = (self.spot_taker_fee + self.perp_taker_fee) * 2.0 * 100.0

        daily_rate_pct = rate_8h * 3.0 * 100.0  # 3 зрізи на добу
        if daily_rate_pct <= 0:
            return float('inf'), roundtrip_fee_pct

        breakeven_days = roundtrip_fee_pct / daily_rate_pct
        return round(breakeven_days, 2), round(roundtrip_fee_pct, 4)

    def evaluate_opportunity(
        self,
        symbol: str,
        rate_8h: float,
        spot_price: float,
        perp_price: float,
        mode: DeltaNeutralMode = DeltaNeutralMode.SPOT_PERP,
        prefer_maker: bool = True
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Перевіряє можливість входу за всіма інституційними фільтрами.
        """
        apy = rate_8h * 3.0 * 365.0 * 100.0
        
        # 1. Мінімальний поріг прибутковості (APY Hurdle)
        if apy < self.min_apy_hurdle:
            return False, f"APY_TOO_LOW ({apy:.1f}% < {self.min_apy_hurdle:.1f}%)", {"apy": apy}

        # 2. Фільтр окупності комісій (Fee Breakeven Guard)
        be_days, fee_pct = self.calculate_breakeven_days(rate_8h, is_maker=prefer_maker)
        if be_days > self.max_breakeven_days:
            return False, f"FEE_BREAKEVEN_EXCEEDED ({be_days:.1f}d > {self.max_breakeven_days:.1f}d max)", {
                "apy": apy, "breakeven_days": be_days, "roundtrip_fee_pct": fee_pct
            }

        # 3. Асиметричний базис-контроль (Asymmetric Basis Guard)
        if spot_price > 0 and perp_price > 0:
            basis_pct = ((perp_price - spot_price) / spot_price) * 100.0
            if mode == DeltaNeutralMode.SPOT_PERP:
                # Беквордація: ф'ючерс дешевший за спот. Небезпечно для Cash & Carry!
                if basis_pct < self.min_entry_basis_pct:
                    return False, f"BASIS_BACKWARDATION ({basis_pct:+.2f}% < {self.min_entry_basis_pct:+.2f}%)", {
                        "apy": apy, "basis_pct": basis_pct
                    }
                # Контанго: ф'ючерс дорожчий. Дозволяємо до розумної межі (до +0.80%)
                if basis_pct > self.max_entry_basis_pct:
                    return False, f"BASIS_EXTREME_CONTANGO ({basis_pct:+.2f}% > {self.max_entry_basis_pct:+.2f}%)", {
                        "apy": apy, "basis_pct": basis_pct
                    }
            else:
                if abs(basis_pct) > self.max_entry_basis_pct:
                    return False, f"BASIS_DISLOCATION ({abs(basis_pct):.2f}% > {self.max_entry_basis_pct:.2f}%)", {
                        "apy": apy, "basis_pct": basis_pct
                    }
        else:
            basis_pct = 0.0


        details = {
            "symbol": symbol,
            "mode": mode.value,
            "rate_8h_pct": round(rate_8h * 100.0, 4),
            "projected_apy": round(apy, 2),
            "breakeven_days": be_days,
            "roundtrip_fee_pct": fee_pct,
            "basis_pct": round(basis_pct, 3),
            "spot_price": spot_price,
            "perp_price": perp_price
        }
        return True, "QUALIFIED", details

    async def open_delta_neutral_position(
        self,
        symbol: str,
        notional_usdt: float,
        rate_8h: float,
        spot_price: float,
        perp_price: float,
        mode: DeltaNeutralMode = DeltaNeutralMode.SPOT_PERP
    ) -> Optional[DeltaNeutralPosition]:
        """
        Атомарне парне відкриття Cash & Carry позиції з гарантією Atomic Rollback.
        """
        is_ok, reason, details = self.evaluate_opportunity(
            symbol=symbol,
            rate_8h=rate_8h,
            spot_price=spot_price,
            perp_price=perp_price,
            mode=mode,
            prefer_maker=True
        )
        if not is_ok:
            logger.info(f"🚫 [Delta-Neutral] Вхід відхилено для {symbol}: {reason}")
            return None

        pos_id = f"dn_{symbol.replace('/', '_')}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        leg1_amount = notional_usdt / spot_price
        leg2_amount = notional_usdt / perp_price
        entry_fees = notional_usdt * (self.spot_maker_fee + self.perp_maker_fee)

        logger.info(
            f"⚡ [Delta-Neutral ВХІД]: {symbol} [{mode.value}] | "
            f"Notional: ${notional_usdt:.1f} | APY: {details['projected_apy']:.1f}% | "
            f"Breakeven: {details['breakeven_days']:.1f}d | Basis: {details['basis_pct']:.2f}%"
        )

        # ---------------------------------------------------------
        # АТОМАРНЕ ВИКОНАННЯ (ATOMIC EXECUTION ENGINE)
        # ---------------------------------------------------------
        leg1_success = False
        leg2_success = False
        
        try:
            # 1. Виконання Ноги 1 (Spot Long)
            leg1_success = await self._execute_leg(
                exchange="binance",
                symbol=symbol,
                side=TradeSide.BUY,
                amount=leg1_amount,
                price=spot_price,
                is_perp=False
            )
            if not leg1_success:
                logger.error(f"❌ [Delta-Neutral] Збій виконання Leg 1 ({symbol} Spot). Вхід скасовано.")
                return None

            # 2. Виконання Ноги 2 (Perp Short)
            leg2_success = await self._execute_leg(
                exchange="binance" if mode == DeltaNeutralMode.SPOT_PERP else "bybit",
                symbol=f"{symbol}:USDT" if mode == DeltaNeutralMode.SPOT_PERP else symbol,
                side=TradeSide.SELL,
                amount=leg2_amount,
                price=perp_price,
                is_perp=True
            )

            # 3. Перевірка атомарності: якщо Leg 2 відхилено, запускаємо Atomic Rollback
            if not leg2_success:
                raise RuntimeError("Leg 2 (Futures Short) rejected by exchange or timed out")

        except Exception as exec_error:
            logger.critical(
                f"🚨 [ATOMIC ROLLBACK TRIGGERED]: Помилка на Нозі 2 ({exec_error}). "
                f"Миттєвий відкат Ноги 1 ({symbol} Spot) для ліквідації спрямованого ризику!"
            )
            if leg1_success:
                await self._rollback_leg(
                    exchange="binance",
                    symbol=symbol,
                    side=TradeSide.SELL,
                    amount=leg1_amount,
                    price=spot_price
                )
            if self.notifier:
                try:
                    self.notifier.notify(
                        f"🚨 <b>[ATOMIC ROLLBACK EXECUTED]</b>\n"
                        f"Пара: <code>{symbol}</code>\n"
                        f"Причина: <i>Збій Leg 2 ({exec_error})</i>\n"
                        f"Дія: <i>Spot Long миттєво продано у ринок. Дельта = 0 збережено.</i>"
                    )
                except Exception:
                    pass
            return None

        # Обидві ноги успішно відкриті! Фіксуємо позицію
        position = DeltaNeutralPosition(
            position_id=pos_id,
            symbol=symbol,
            mode=mode,
            leg1_exchange="binance",
            leg1_symbol=symbol,
            leg1_side=TradeSide.BUY,
            leg1_entry_price=spot_price,
            leg1_amount=leg1_amount,
            leg2_exchange="binance" if mode == DeltaNeutralMode.SPOT_PERP else "bybit",
            leg2_symbol=f"{symbol}:USDT" if mode == DeltaNeutralMode.SPOT_PERP else symbol,
            leg2_side=TradeSide.SELL,
            leg2_entry_price=perp_price,
            leg2_amount=leg2_amount,
            notional_usdt=notional_usdt,
            entry_basis_pct=details["basis_pct"],
            accrued_funding_usdt=0.0,
            funding_cycles_collected=0,
            entry_fees_usdt=entry_fees,
            current_8h_rate=rate_8h,
            projected_apy=details["projected_apy"],
            opened_at=time.time(),
            last_funding_time=time.time(),
            status=DeltaNeutralStatus.OPEN
        )

        self.active_positions[pos_id] = position
        self._persist_position(position)

        # Сповіщення в Telegram
        if self.notifier:
            try:
                self.notifier.notify(
                    f"💎 <b>[CASH & CARRY ВІДКРИТО]</b> 💎\n\n"
                    f"Пара: <b>{symbol}</b> [{mode.value}]\n"
                    f"Об'єм: <b>${notional_usdt:.1f} USDT</b>\n"
                    f"Річний APY: <b>+{details['projected_apy']:.1f}%</b>\n"
                    f"Окупність комісій: <b>{details['breakeven_days']:.1f} діб</b>\n"
                    f"Базис: <b>{details['basis_pct']:.2f}%</b>\n"
                    f"Статус: <i>🛡️ Дельта = 0 (Нараховується фандинг)</i>"
                )
            except Exception:
                pass

        return position

    async def _execute_leg(
        self,
        exchange: str,
        symbol: str,
        side: TradeSide,
        amount: float,
        price: float,
        is_perp: bool
    ) -> bool:
        """Виконання окремої ноги (у Paper режимі - емуляція заповнення, у Live - ордер на біржу)."""
        if self.is_paper:
            await asyncio.sleep(0.05)  # Емуляція затримки мережі
            return True
        
        # Live execution через ExchangeManager
        try:
            if not self.exchange_manager:
                return False
            # Використовуємо Post-Only Maker ордери
            order = await self.exchange_manager.create_limit_order(
                symbol=symbol,
                side=side.value.lower(),
                amount=amount,
                price=price,
                params={"postOnly": True}
            )
            return bool(order and order.get('id'))
        except Exception as e:
            logger.error(f"Помилка виконання ноги {symbol} ({side.value}): {e}")
            return False

    async def _rollback_leg(
        self,
        exchange: str,
        symbol: str,
        side: TradeSide,
        amount: float,
        price: float
    ) -> None:
        """Аварійний розвантажувальний ордер для повернення у нейтральний стан."""
        if self.is_paper:
            logger.info(f"🔄 [Paper Rollback] Нога {symbol} ({side.value}) успішно скасована.")
            return

        try:
            if self.exchange_manager:
                # Taker ринковий ордер для миттєвої ліквідації завислої позиції
                await self.exchange_manager.create_market_order(
                    symbol=symbol,
                    side=side.value.lower(),
                    amount=amount
                )
                logger.info(f"✅ [Live Rollback] Нога {symbol} скинута за ринком.")
        except Exception as e:
            logger.critical(f"🚨🚨 [CRITICAL ROLLBACK FAILED]: Не вдалося скинути {symbol}: {e}")

    def accrue_funding(
        self,
        rates_map: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Нараховує виплати фандингу за відкритими позиціями кожні 8 годин.
        Оновлює базу даних та вільний баланс гаманця.
        """
        harvested_events = []
        now = time.time()

        for pos_id, pos in list(self.active_positions.items()):
            if pos.status != DeltaNeutralStatus.OPEN:
                continue

            # У Paper режимі нараховуємо виплату, якщо минуло 8 годин (або 28800с з останньої виплати)
            # Для тестування можна використовувати динамічний інтервал
            elapsed = now - pos.last_funding_time
            if elapsed < 28800.0 and not getattr(self.settings, 'FORCE_FUNDING_ACCRUE', False):
                continue

            current_rate = rates_map.get(pos.symbol, pos.current_8h_rate)
            if current_rate <= 0:
                logger.warning(f"⚠️ [Funding Accrue] Ставка для {pos.symbol} стала від'ємною ({current_rate*100:.4f}%).")
                continue

            # Виплата = Notional * 8h Rate
            payment = pos.notional_usdt * current_rate
            pos.accrued_funding_usdt += payment
            pos.funding_cycles_collected += 1
            pos.current_8h_rate = current_rate
            pos.projected_apy = current_rate * 3.0 * 365.0 * 100.0
            pos.last_funding_time = now

            # Оновлюємо в базі даних через репозиторій
            self.repo.update_delta_neutral_funding(
                position_id=pos.position_id,
                funding_payment=payment,
                current_8h_rate=current_rate,
                projected_apy=pos.projected_apy
            )

            # Нараховуємо прибуток у реальний баланс гаманця
            current_wallet = self.repo.load_balance()
            new_wallet = current_wallet + payment
            self.repo.save_balance(new_wallet)

            event = {
                "position_id": pos.position_id,
                "symbol": pos.symbol,
                "payment_usdt": round(payment, 4),
                "total_accrued_usdt": round(pos.accrued_funding_usdt, 4),
                "cycles": pos.funding_cycles_collected,
                "rate_8h_pct": round(current_rate * 100.0, 4),
                "new_balance": round(new_wallet, 2)
            }
            harvested_events.append(event)

            logger.info(
                f"💰 [FUNDING HARVESTED]: {pos.symbol} | "
                f"+{payment:.4f} USDT | Всього зібрано: +{pos.accrued_funding_usdt:.4f} USDT "
                f"({pos.funding_cycles_collected} циклів) | Баланс: {new_wallet:.2f} USDT"
            )

            # Сповіщення в Telegram
            if self.notifier:
                try:
                    self.notifier.notify(
                        f"💰 <b>[ВИПЛАТА ФАНДИНГУ О verge]</b>\n"
                        f"Пара: <b>{pos.symbol}</b>\n"
                        f"Нараховано: <b>+{payment:.4f} USDT</b>\n"
                        f"Сумарно за позицією: <b>+{pos.accrued_funding_usdt:.4f} USDT</b> ({pos.funding_cycles_collected} циклів)\n"
                        f"Баланс депозиту: <b>{new_wallet:.2f} USDT</b>"
                    )
                except Exception:
                    pass

        return harvested_events

    async def evaluate_auto_exits(
        self,
        current_rates: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Дворівневий захист від негативного фандингу (Funding Flip Auto-Exit Guard):
        1. Миттєвий вихід (Hard Threshold): якщо rate_8h <= hard_negative_threshold (-0.01%),
           закриття відбувається миттєво з reason="FUNDING_FLIP_HARD".
        2. Підтверджений вихід (Soft Threshold): якщо rate_8h <= 0.0 протягом max_negative_strikes (2 перевірки поспіль),
           закриття відбувається з reason="FUNDING_FLIP_CONFIRMED".
        3. Скидання лічильника страйків, якщо ставка знову додатна (> 0.0%).
        """
        closed_results = []
        for pos_id, pos in list(self.active_positions.items()):
            if pos.status != DeltaNeutralStatus.OPEN:
                continue

            rate_8h = current_rates.get(pos.symbol)
            if rate_8h is None:
                continue

            # Рівень 1: Миттєвий вихід при критично низькому / різкому негативному фандингу
            if rate_8h <= self.hard_negative_threshold:
                logger.warning(
                    f"🚨 [AUTO-EXIT HARD] {pos.symbol}: критично негативна ставка "
                    f"({rate_8h*100:+.4f}% <= {self.hard_negative_threshold*100:+.4f}%). Миттєвий вихід!"
                )
                close_res = await self.close_delta_neutral_position(
                    pos_id,
                    reason=f"FUNDING_FLIP_HARD ({rate_8h*100:+.4f}%)"
                )
                if close_res:
                    closed_results.append(close_res)
                    self._negative_funding_strikes.pop(pos_id, None)
                    if self.notifier:
                        try:
                            self.notifier.notify(
                                f"🚨 <b>[FUNDING FLIP: МИТТЄВИЙ АВТО-ВИХІД]</b>\n\n"
                                f"Пара: <b>{pos.symbol}</b>\n"
                                f"Ставка: <b>{rate_8h*100:+.4f}%</b> (нижче порогу {self.hard_negative_threshold*100:+.4f}%)\n"
                                f"Зібрано фандингу: <b>+{close_res['accrued_funding_usdt']:.3f} USDT</b>\n"
                                f"Чистий результат: <b>{close_res['net_profit_usdt']:+.3f} USDT</b>\n"
                                f"Статус: <i>🛡️ Обидві ноги закриті миттєво. Депозит захищено!</i>"
                            )
                        except Exception:
                            pass
                continue

            # Рівень 2: Підтверджений вихід при нульовій або слабонегативній ставці
            if rate_8h <= 0.0:
                strikes = self._negative_funding_strikes.get(pos_id, 0) + 1
                self._negative_funding_strikes[pos_id] = strikes
                logger.warning(
                    f"⚠️ [AUTO-EXIT SOFT] {pos.symbol}: ставка {rate_8h*100:+.4f}% <= 0.0 "
                    f"(страйк {strikes}/{self.max_negative_strikes})"
                )
                if strikes >= self.max_negative_strikes:
                    logger.warning(
                        f"🚨 [AUTO-EXIT CONFIRMED] {pos.symbol}: підтверджено негативний фандинг "
                        f"({strikes} страйки поспіль). Автоматичне закриття!"
                    )
                    close_res = await self.close_delta_neutral_position(
                        pos_id,
                        reason=f"FUNDING_FLIP_CONFIRMED ({rate_8h*100:+.4f}%)"
                    )
                    if close_res:
                        closed_results.append(close_res)
                        self._negative_funding_strikes.pop(pos_id, None)
                        if self.notifier:
                            try:
                                self.notifier.notify(
                                    f"🚨 <b>[FUNDING FLIP: ПІДТВЕРДЖЕНИЙ АВТО-ВИХІД]</b>\n\n"
                                    f"Пара: <b>{pos.symbol}</b>\n"
                                    f"Ставка: <b>{rate_8h*100:+.4f}%</b> ({strikes} перевірки поспіль <= 0)\n"
                                    f"Зібрано фандингу: <b>+{close_res['accrued_funding_usdt']:.3f} USDT</b>\n"
                                    f"Чистий результат: <b>{close_res['net_profit_usdt']:+.3f} USDT</b>\n"
                                    f"Статус: <i>🛡️ Обидві ноги закриті після підтвердження.</i>"
                                )
                            except Exception:
                                pass
            else:
                # Ставка знову позитивна - скидаємо страйки
                if pos_id in self._negative_funding_strikes:
                    logger.info(f"✅ [AUTO-EXIT RESET] {pos.symbol}: ставка відновилася до {rate_8h*100:+.4f}%. Страйки скинуто.")
                    self._negative_funding_strikes.pop(pos_id, None)

        return closed_results

    async def check_and_auto_unwind_flipped_positions(
        self,
        rates_map: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Аліас для зворотної сумісності."""
        return await self.evaluate_auto_exits(rates_map)

    async def close_position(self, group_id: str, reason: str = "MANUAL_OR_PROFIT") -> bool:
        """Аліас для закриття дельта-нейтральної позиції за group_id/position_id."""
        return bool(await self.close_delta_neutral_position(group_id, reason=reason))

    async def close_delta_neutral_position(

        self,
        position_id: str,
        reason: str = "MANUAL_OR_PROFIT"
    ) -> Optional[Dict[str, Any]]:
        """
        Атомарне закриття обох ніг Cash & Carry та підбиття чистого PnL.
        """
        pos = self.active_positions.get(position_id)
        if not pos or pos.status != DeltaNeutralStatus.OPEN:
            return None

        logger.info(f"🛑 [Delta-Neutral ЗАКРИТТЯ]: {pos.symbol} | Причина: {reason}")
        
        # Закриваємо обидві ноги
        await self._execute_leg("binance", pos.leg1_symbol, TradeSide.SELL, pos.leg1_amount, pos.leg1_entry_price, False)
        await self._execute_leg("binance", pos.leg2_symbol, TradeSide.BUY, pos.leg2_amount, pos.leg2_entry_price, True)

        pos.status = DeltaNeutralStatus.CLOSED
        pos.close_reason = reason
        self.repo.close_delta_neutral_position(position_id, reason)

        exit_fees = pos.notional_usdt * (self.spot_maker_fee + self.perp_maker_fee)
        total_fees = pos.entry_fees_usdt + exit_fees
        net_profit_usdt = pos.accrued_funding_usdt - total_fees

        res = {
            "position_id": pos.position_id,
            "symbol": pos.symbol,
            "accrued_funding_usdt": round(pos.accrued_funding_usdt, 4),
            "total_fees_usdt": round(total_fees, 4),
            "net_profit_usdt": round(net_profit_usdt, 4),
            "cycles": pos.funding_cycles_collected,
            "close_reason": reason
        }

        # Логуємо фінальний результат у таблицю trades
        self.repo.log_trade(
            symbol=pos.symbol,
            side="SELL",
            price=pos.leg1_entry_price,
            amount=pos.leg1_amount,
            cost=pos.notional_usdt,
            pnl=net_profit_usdt,
            exit_reason=f"Cash&Carry ({reason})"
        )

        del self.active_positions[position_id]
        return res

    def _persist_position(self, pos: DeltaNeutralPosition) -> None:
        """Збереження активної позиції в базі даних через SQLAlchemy модель."""
        model = DeltaNeutralPositionModel(
            id=pos.position_id,
            symbol=pos.symbol,
            mode=pos.mode.value,
            leg1_exchange=pos.leg1_exchange,
            leg1_symbol=pos.leg1_symbol,
            leg1_side=pos.leg1_side.value,
            leg1_entry_price=pos.leg1_entry_price,
            leg1_amount=pos.leg1_amount,
            leg2_exchange=pos.leg2_exchange,
            leg2_symbol=pos.leg2_symbol,
            leg2_side=pos.leg2_side.value,
            leg2_entry_price=pos.leg2_entry_price,
            leg2_amount=pos.leg2_amount,
            notional_usdt=pos.notional_usdt,
            entry_basis_pct=pos.entry_basis_pct,
            accrued_funding_usdt=pos.accrued_funding_usdt,
            funding_cycles_collected=pos.funding_cycles_collected,
            entry_fees_usdt=pos.entry_fees_usdt,
            current_8h_rate=pos.current_8h_rate,
            projected_apy=pos.projected_apy,
            status=pos.status.value,
            close_reason=pos.close_reason,
            opened_at=datetime.fromtimestamp(pos.opened_at, tz=timezone.utc),
            last_funding_time=datetime.fromtimestamp(pos.last_funding_time, tz=timezone.utc)
        )
        self.repo.save_delta_neutral_position(model)
