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

# 2. Строга модель для метаданих сигналу (замість Dict)
class SignalMetadata(BaseModel):
    price: float = Field(..., gt=0)
    ai_conf: float = Field(..., ge=0.0, le=1.0)
    rsi: float = Field(..., ge=0.0, le=100.0)
    trend: TrendDirection
    reason: str = "No signal"
    
    model_config = ConfigDict(strict=True)

class HybridStrategy:
    # Припускаємо, що Settings вже є Pydantic-моделлю з дефолтними значеннями
    def __init__(self, settings: 'Settings'):
        self.settings = settings

    def get_signal(
        self, 
        df: pd.DataFrame, 
        ai_confidence: float, 
        in_position: bool = False
    ) -> Tuple[Optional[SignalAction], SignalMetadata]:
        
        # 1. Безпечна перевірка даних
        required_cols = {'RSI', 'EMA_DIST_50', 'MACD_HIST'}
        if df is None or df.empty or len(df) < 2:
            logger.warning("Недостатньо даних (менше 2 свічок) для аналізу.")
            return None, self._empty_meta()
            
        if not required_cols.issubset(df.columns):
            logger.error(f"Відсутні індикатори. Очікуються: {required_cols}")
            return None, self._empty_meta()

        # 2. Безпечне отримання поточних та попередніх значень
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Розрахунок базових метрик
        is_uptrend = curr['EMA_DIST_50'] > 0
        rsi_value = float(curr['RSI']) # Прибираємо множення на 100, якщо RSI вже 0-100
        current_price = float(curr['close'])
        
        # Формування базової мета-інформації
        meta = SignalMetadata(
            price=current_price,
            ai_conf=round(ai_confidence, 2),
            rsi=round(rsi_value, 2),
            trend=TrendDirection.UP if is_uptrend else TrendDirection.DOWN,
            reason="Evaluating..."
        )

        if in_position:
            meta.reason = "Already in position"
            return None, meta

        # 3. Каскад фільтрів (Risk Management)
        if ai_confidence < self.settings.CONFIDENCE_THRESHOLD:
            meta.reason = f"Low AI Confidence ({ai_confidence:.2f} < {self.settings.CONFIDENCE_THRESHOLD})"
            return None, meta

        if self.settings.TREND_FILTER and not is_uptrend:
            meta.reason = "Trend filter active (Not in Uptrend)"
            return None, meta

        if rsi_value >= self.settings.RSI_BUY_LIMIT:
            meta.reason = f"RSI Overbought ({rsi_value:.1f} >= {self.settings.RSI_BUY_LIMIT})"
            return None, meta

        # 4. Пошук тригера для входу
        macd_cross_up = prev['MACD_HIST'] <= 0 and curr['MACD_HIST'] > 0
        
        if macd_cross_up:
            meta.reason = "MACD_Bullish_Cross_AI_Confirmed"
            return SignalAction.BUY, meta

        # Вхід виключно за високою впевненістю AI (навіть без перетину MACD)
        meta.reason = f"AI_Sniper(Conf={ai_confidence:.2f})"
        return SignalAction.BUY, meta

    def _empty_meta(self) -> SignalMetadata:
        """Повертає пустий/нульовий стан для метаданих у разі помилки"""
        return SignalMetadata(
            price=0.01, # Мінімальне валідне значення
            ai_conf=0.0,
            rsi=50.0,
            trend=TrendDirection.DOWN,
            reason="Invalid DataFrame or missing data"
        )