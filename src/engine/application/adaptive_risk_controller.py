"""
Модуль адаптивного ризик-менеджменту (Adaptive Risk Management & Thresholds).
Динамічно підлаштовує вимоги до торгових сигналів (Confidence, Min ADX)
та розмір ризику на угоду (Risk Sizing) залежно від поточної просадки та серії збитків.
"""

import logging
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger("AdaptiveRiskController")

class AdaptiveRiskState(BaseModel):
    consecutive_losses: int = Field(default=0, ge=0)
    consecutive_wins: int = Field(default=0, ge=0)
    rolling_trades_count: int = Field(default=0, ge=0)
    rolling_win_rate: float = Field(default=0.50, ge=0.0, le=1.0)
    current_drawdown_pct: float = Field(default=0.0, ge=0.0)
    peak_balance: float = Field(default=1000.0, gt=0.0)
    current_confidence_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    current_min_adx: float = Field(default=25.0, ge=0.0, le=100.0)
    current_risk_multiplier: float = Field(default=1.0, ge=0.1, le=1.5)
    status_message: str = Field(default="NORMAL")

    model_config = ConfigDict(strict=True)

class AdaptiveThresholds(BaseModel):
    confidence_threshold: float = Field(..., ge=0.0, le=1.0)
    min_adx: float = Field(..., ge=0.0, le=100.0)
    risk_per_trade_pct: float = Field(..., ge=0.001, le=0.20)

    model_config = ConfigDict(strict=True)

class AdaptiveRiskController:
    """
    Контролер адаптивного ризику інституційного рівня.
    При виявленні локального Drawdown або серії збитків:
    - Збільшує поріг впевненості моделі (Confidence Threshold), наприклад з 0.30/0.55 до 0.38/0.63.
    - Підвищує мінімальний поріг сили тренду (Min ADX) з 25 до 30+, щоб уникати збиткових флетів.
    - Знижує об'єм капіталу в нових угодах для захисту депозиту.
    - При відновленні та серії перемог поступово повертає параметри до базових.
    """

    def __init__(
        self,
        base_confidence: float = 0.55,
        base_min_adx: float = 25.0,
        base_risk_pct: float = 0.02,
        lookback_window: int = 15
    ):
        self.base_confidence = float(base_confidence)
        self.base_min_adx = float(base_min_adx)
        self.base_risk_pct = float(base_risk_pct)
        self.lookback_window = lookback_window

        self.consecutive_losses: int = 0
        self.consecutive_wins: int = 0
        self.recent_results: List[int] = []  # 1 = win, 0 = loss
        self.peak_balance: float = 1000.0
        self.current_balance: float = 1000.0

    def initialize_from_history(self, closed_trades: list, current_balance: float) -> None:
        """
        Відновлює стан ризик-контролера з історії закритих угод у БД при старті.
        """
        self.current_balance = max(10.0, float(current_balance))
        self.peak_balance = max(self.peak_balance, self.current_balance)

        if not closed_trades:
            logger.info("🛡️ [Adaptive Risk] Історія угод порожня. Встановлено базові параметри.")
            return

        # Угоди відсортовані від найновішої до найстарішої
        trades_chronological = list(reversed(closed_trades[-self.lookback_window:]))
        self.recent_results = []
        for t in trades_chronological:
            pnl = getattr(t, "pnl", 0.0)
            target = getattr(t, "target_label", 1 if pnl > 0 else 0)
            self.recent_results.append(1 if target == 1 else 0)

        # Рахуємо поточну серію (з кінця списку)
        streak_loss = 0
        streak_win = 0
        for res in reversed(self.recent_results):
            if res == 0 and streak_win == 0:
                streak_loss += 1
            elif res == 1 and streak_loss == 0:
                streak_win += 1
            else:
                break

        self.consecutive_losses = streak_loss
        self.consecutive_wins = streak_win

        state = self.get_state()
        logger.info(
            f"🛡️ [Adaptive Risk] Ініціалізовано: Streak = -{self.consecutive_losses}/+{self.consecutive_wins} | "
            f"WinRate = {state.rolling_win_rate * 100:.1f}% | Conf = {state.current_confidence_threshold:.2f} | "
            f"MinADX = {state.current_min_adx:.1f} | RiskMult = {state.current_risk_multiplier:.2f}"
        )

    def record_trade_result(self, net_pnl: float, target_label: int, balance_after_trade: float) -> AdaptiveRiskState:
        """
        Реєстрація результату закритої угоди та миттєвий перерахунок адаптивних порогів.
        """
        self.current_balance = float(balance_after_trade)
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance

        is_win = (target_label == 1 or net_pnl > 0)
        self.recent_results.append(1 if is_win else 0)
        if len(self.recent_results) > self.lookback_window:
            self.recent_results.pop(0)

        if is_win:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            logger.info(f"🟢 [Adaptive Risk] Фіксація прибутку (+{net_pnl:.2f} USDT). Серія перемог: {self.consecutive_wins}.")
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            logger.warning(f"🔴 [Adaptive Risk] Фіксація збитку ({net_pnl:.2f} USDT). Серія збитків: {self.consecutive_losses}.")

        state = self.get_state()
        if self.consecutive_losses >= 2:
            logger.warning(
                f"⚠️ [Adaptive Risk] Увімкнено захисний режим (Streak: -{self.consecutive_losses})! "
                f"Вимоги посилено: Conf {self.base_confidence:.2f} -> {state.current_confidence_threshold:.2f}, "
                f"Min ADX {self.base_min_adx:.1f} -> {state.current_min_adx:.1f}, "
                f"Risk {self.base_risk_pct*100:.1f}% -> {self.get_effective_risk_pct()*100:.2f}%"
            )
        elif self.consecutive_wins >= 2 and state.rolling_win_rate >= 0.65:
            logger.info(
                f"✨ [Adaptive Risk] Ринок стабільний (WinRate: {state.rolling_win_rate*100:.1f}%). "
                f"Пороги нормалізовано: Conf {state.current_confidence_threshold:.2f}, Min ADX {state.current_min_adx:.1f}."
            )

        return state

    def get_effective_confidence_threshold(self, override_base: Optional[float] = None) -> float:
        """
        Розрахунок динамічного порогу впевненості моделі.
        Під час серії збитків поріг підвищується: +0.03 за кожну збиткову угоду (макс +0.08).
        """
        base = float(override_base) if override_base is not None else self.base_confidence

        if self.consecutive_losses >= 1:
            penalty = min(0.08, self.consecutive_losses * 0.03)
            return min(0.70, round(base + penalty, 2))
        
        # Якщо серія перемог і вінрейт високий, можна злегка пом'якшити поріг (-0.02)
        win_rate = self._compute_win_rate()
        if self.consecutive_wins >= 3 and win_rate >= 0.65:
            return max(0.28, round(base - 0.02, 2))

        return round(base, 2)

    def get_effective_min_adx(self, override_base: Optional[float] = None) -> float:
        """
        Розрахунок динамічного мінімального ADX для входу в угоду.
        При просадці вимагає значно сильнішого тренду (наприклад 25.0 -> 29.0..31.0),
        щоб уникати розпилювання у флеті (CHOPPY_FLAT).
        """
        base = float(override_base) if override_base is not None else self.base_min_adx

        if self.consecutive_losses >= 1:
            penalty = min(6.0, self.consecutive_losses * 2.0)
            return min(32.0, round(base + penalty, 1))

        return round(base, 1)

    def get_effective_risk_pct(self, override_base: Optional[float] = None) -> float:
        """
        Динамічне керування розміром позиції (Capital Preservation).
        При накопиченні збитків розмір ризику знижується (на 20% за кожний збиток, до макс -60%).
        """
        base = float(override_base) if override_base is not None else self.base_risk_pct

        if self.consecutive_losses >= 1:
            multiplier = max(0.40, (0.80 ** min(self.consecutive_losses, 4)))
            return round(base * multiplier, 4)

        return round(base, 4)

    def get_effective_thresholds(
        self,
        base_confidence: Optional[float] = None,
        base_min_adx: Optional[float] = None,
        base_risk_pct: Optional[float] = None
    ) -> AdaptiveThresholds:
        """
        Повертає повний набір актуальних адаптивних параметрів.
        """
        return AdaptiveThresholds(
            confidence_threshold=self.get_effective_confidence_threshold(base_confidence),
            min_adx=self.get_effective_min_adx(base_min_adx),
            risk_per_trade_pct=self.get_effective_risk_pct(base_risk_pct)
        )

    def _compute_win_rate(self) -> float:
        if not self.recent_results:
            return 0.50
        return sum(self.recent_results) / len(self.recent_results)

    def get_state(self) -> AdaptiveRiskState:
        """Повертає поточний статус системи адаптивного ризику."""
        win_rate = self._compute_win_rate()
        dd_pct = 0.0
        if self.peak_balance > 0:
            dd_pct = max(0.0, (self.peak_balance - self.current_balance) / self.peak_balance)

        status_msg = "NORMAL"
        if self.consecutive_losses >= 3 or dd_pct > 0.05:
            status_msg = "HIGH_DEFENSE"
        elif self.consecutive_losses >= 1:
            status_msg = "DEFENSIVE"
        elif self.consecutive_wins >= 2 and win_rate >= 0.65:
            status_msg = "OPTIMAL_EXPANSION"

        risk_mult = self.get_effective_risk_pct() / self.base_risk_pct if self.base_risk_pct > 0 else 1.0

        return AdaptiveRiskState(
            consecutive_losses=self.consecutive_losses,
            consecutive_wins=self.consecutive_wins,
            rolling_trades_count=len(self.recent_results),
            rolling_win_rate=round(win_rate, 4),
            current_drawdown_pct=round(dd_pct, 4),
            peak_balance=round(self.peak_balance, 2),
            current_confidence_threshold=self.get_effective_confidence_threshold(),
            current_min_adx=self.get_effective_min_adx(),
            current_risk_multiplier=round(risk_mult, 4),
            status_message=status_msg
        )
