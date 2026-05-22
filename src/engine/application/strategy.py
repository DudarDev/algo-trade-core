import logging
import pandas as pd
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

# 1. Enums для структури
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

# 2. Модель даних для сигналу
class SignalMetadata(BaseModel):
    price: float = Field(..., gt=0)
    ai_conf: float = Field(..., ge=0.0, le=1.0)
    rsi: float = Field(..., ge=0.0, le=100.0)
    trend: TrendDirection
    regime: MarketRegime = MarketRegime.CHOP
    reason: str = "No signal"
    
    model_config = ConfigDict(strict=True)

class HybridStrategy:
    def __init__(self, settings):
        self.settings = settings

    def _detect_regime(self, curr_row: pd.Series) -> MarketRegime:
        """Визначає стан ринку на основі волатильності та тренду."""
        ema_dist = float(curr_row.get('EMA_DIST_50', 0))
        atr_pct = float(curr_row.get('ATR_PCT', 0))

        if atr_pct < 0.015:
            return MarketRegime.CHOP
        if ema_dist > 0.01:
            return MarketRegime.BULL
        if ema_dist < -0.01:
            return MarketRegime.BEAR
            
        return MarketRegime.CHOP

    def get_signal(
        self, 
        df: pd.DataFrame, 
        ai_confidence: float, 
        in_position: bool = False
    ) -> Tuple[Optional[SignalAction], SignalMetadata]:
        
        # Перевірка наявності даних
        required_cols = {'RSI', 'EMA_DIST_50', 'MACD_HIST', 'ATR_PCT'}
        if df is None or df.empty or len(df) < 2 or not required_cols.issubset(df.columns):
            return None, self._empty_meta()

        curr = df.iloc[-1]
        current_price = float(curr['close'])
        regime = self._detect_regime(curr)
        
        # Базова мета-інформація
        meta = SignalMetadata(
            price=current_price,
            ai_conf=round(ai_confidence, 2),
            rsi=round(float(curr['RSI']), 2),
            trend=TrendDirection.UP if curr['EMA_DIST_50'] > 0 else TrendDirection.DOWN,
            regime=regime,
            reason="Evaluating..."
        )

        if in_position:
            meta.reason = "Already in position"
            return None, meta

        # 3. АДАПТИВНІ ПОРОГИ (Критична частина)
        # Калібрована модель (Sigmoid) видає реальні ймовірності (15-30% - це вже сильний сигнал)
        if regime == MarketRegime.BULL:
            threshold = 0.12 
        elif regime == MarketRegime.CHOP:
            threshold = 0.16 
        else: # BEAR
            threshold = 0.22 

        # 4. Фільтр перегрітості
        if float(curr['RSI']) >= 70:
            meta.reason = f"RSI Overbought ({float(curr['RSI']):.1f})"
            return SignalAction.HOLD, meta

        # 5. Ухвалення рішення
        if ai_confidence >= threshold:
            meta.reason = f"AI_Smart_Signal_{regime.value}(Conf={ai_confidence:.2f})"
            return SignalAction.BUY, meta

        meta.reason = f"Insufficient confidence ({ai_confidence:.2f} < {threshold:.2f})"
        return SignalAction.HOLD, meta

    def _empty_meta(self) -> SignalMetadata:
        return SignalMetadata(
            price=0.01, ai_conf=0.0, rsi=50.0,
            trend=TrendDirection.FLAT, regime=MarketRegime.CHOP,
            reason="Invalid DataFrame"
        )