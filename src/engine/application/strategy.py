import logging
import pandas as pd
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# 1. Enums для уникнення магічних рядків
class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class TrendDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"

class MarketRegime(str, Enum):
    BULL = "BULL_MARKET"
    BEAR = "BEAR_MARKET"
    CHOP = "CHOPPY_FLAT"

# 2. Строга модель для метаданих сигналу
class SignalMetadata(BaseModel):
    price: float = Field(..., gt=0)
    ai_conf: float = Field(..., ge=0.0, le=1.0)
    rsi: float = Field(..., ge=0.0, le=100.0)
    trend: TrendDirection
    regime: MarketRegime = MarketRegime.CHOP  # Нове поле для режиму
    reason: str = "No signal"
    
    model_config = ConfigDict(strict=True)

class HybridStrategy:
    def __init__(self, settings: 'Settings'):
        self.settings = settings

    def _detect_regime(self, curr_row: pd.Series) -> MarketRegime:
        """
        Визначає глобальний стан ринку на основі тренду та волатильності.
        Використовує ATR (Average True Range) у відсотках та дистанцію до EMA50.
        """
        ema_dist = float(curr_row.get('EMA_DIST_50', 0))
        atr_pct = float(curr_row.get('ATR_PCT', 0))

        # Якщо волатильність низька (наприклад, свічки менше 1.5%) - це боковик
        if atr_pct < 0.015:
            return MarketRegime.CHOP
            
        # Якщо висока волатильність і ціна вище EMA50
        if ema_dist > 0.01:
            return MarketRegime.BULL
            
        # Якщо висока волатильність і ціна нижче EMA50
        if ema_dist < -0.01:
            return MarketRegime.BEAR
            
        return MarketRegime.CHOP

    def get_signal(
        self, 
        df: pd.DataFrame, 
        ai_confidence: float, 
        in_position: bool = False
    ) -> Tuple[Optional[SignalAction], SignalMetadata]:
        
        # 1. Безпечна перевірка даних
        required_cols = {'RSI', 'EMA_DIST_50', 'MACD_HIST', 'ATR_PCT'}
        if df is None or df.empty or len(df) < 2:
            return None, self._empty_meta()
            
        if not required_cols.issubset(df.columns):
            logger.warning(f"Відсутні індикатори. Очікуються: {required_cols}")
            return None, self._empty_meta()

        # 2. Отримання поточних значень
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        is_uptrend = curr['EMA_DIST_50'] > 0
        rsi_value = float(curr['RSI'])
        current_price = float(curr['close'])
        
        # Визначаємо режим ринку
        regime = self._detect_regime(curr)
        
        # Формування базової мета-інформації
        meta = SignalMetadata(
            price=current_price,
            ai_conf=round(ai_confidence, 2),
            rsi=round(rsi_value, 2),
            trend=TrendDirection.UP if is_uptrend else TrendDirection.DOWN,
            regime=regime,
            reason="Evaluating..."
        )

        if in_position:
            meta.reason = "Already in position"
            return None, meta

        # 3. АДАПТИВНІ ПОРОГИ ВПЕВНЕНОСТІ ШІ (Smart Logic)
        # Залежно від режиму ринку, ми вимагаємо різний рівень впевненості
        dynamic_threshold = 0.85 # Дефолтний жорсткий поріг
        
        if regime == MarketRegime.BULL:
            dynamic_threshold = 0.60  # У бичачому ринку можна ризикувати більше
        elif regime == MarketRegime.CHOP:
            dynamic_threshold = 0.75  # У боковику треба бути обережнішим
        elif regime == MarketRegime.BEAR:
            dynamic_threshold = 0.85  # Проти тренду торгуємо тільки ідеальні сетапи

        # Запобіжник: якщо в налаштуваннях стоїть ще вищий поріг, беремо його
        final_threshold = max(dynamic_threshold, getattr(self.settings, 'CONFIDENCE_THRESHOLD', 0.5))

        # 4. Каскад фільтрів (Risk Management)
        if ai_confidence < final_threshold:
            meta.reason = f"Low Conf for {regime.value} ({ai_confidence:.2f} < {final_threshold:.2f})"
            return SignalAction.HOLD, meta

        if rsi_value >= self.settings.RSI_BUY_LIMIT:
            meta.reason = f"RSI Overbought ({rsi_value:.1f} >= {self.settings.RSI_BUY_LIMIT})"
            return SignalAction.HOLD, meta

        # 5. Пошук тригера для входу
        macd_cross_up = prev['MACD_HIST'] <= 0 and curr['MACD_HIST'] > 0
        
        if macd_cross_up:
            meta.reason = f"SmartAI_{regime.value}(MACD+Conf={ai_confidence:.2f})"
            return SignalAction.BUY, meta

        # Якщо MACD не перетнувся, але впевненість ЕКСТРЕМАЛЬНО висока (> 90%)
        if ai_confidence >= 0.90:
            meta.reason = f"AI_Sniper_Extreme(Conf={ai_confidence:.2f})"
            return SignalAction.BUY, meta

        # ДЕФОЛТ: якщо нічого не підійшло - просто тримаємо гроші
        meta.reason = "Waiting for trigger"
        return SignalAction.HOLD, meta

    def _empty_meta(self) -> SignalMetadata:
        return SignalMetadata(
            price=0.01,
            ai_conf=0.0,
            rsi=50.0,
            trend=TrendDirection.FLAT,
            regime=MarketRegime.CHOP,
            reason="Invalid DataFrame"
        )