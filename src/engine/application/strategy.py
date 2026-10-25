import logging
import pandas as pd
from enum import Enum
from typing import Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

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

class SignalMetadata(BaseModel):
    price: float = Field(..., gt=0)
    ai_conf: float = Field(..., ge=0.0, le=1.0)
    rsi: float = Field(..., ge=0.0, le=100.0)
    trend: TrendDirection
    regime: MarketRegime = MarketRegime.CHOP
    htf_trend: Optional[str] = "NEUTRAL"
    btc_pulse: Optional[str] = "HEALTHY"
    vol_spike: Optional[float] = 1.0
    quant_score: Optional[float] = 0.0
    ensemble_conf: Optional[float] = 0.0
    order_book_status: Optional[str] = "NEUTRAL"
    funding_sentiment: Optional[str] = "HEALTHY_BALANCED"
    reason: str = "No signal"
    
    model_config = ConfigDict(strict=True)

def _get_float_setting(settings, keys: list, default: float) -> float:
    for k in keys:
        try:
            val = getattr(settings, k, None)
            if isinstance(val, (int, float)):
                return float(val)
        except Exception:
            pass
    return default

class HybridStrategy:
    def __init__(self, settings, risk_controller=None):
        self.settings = settings
        self.risk_controller = risk_controller
        self.min_adx = _get_float_setting(settings, ['MIN_ADX_TREND', 'min_adx_trend'], 25.0)
        self.min_atr_pct = _get_float_setting(settings, ['MIN_ATR_PCT', 'min_atr_pct'], 0.0010)
        self.base_threshold = _get_float_setting(settings, ['CONFIDENCE_THRESHOLD', 'min_ai_confidence'], 0.55)

    def _detect_regime(self, curr_row: pd.Series, effective_min_adx: Optional[float] = None) -> MarketRegime:
        ema_dist = float(curr_row.get('EMA_DIST_50', 0))
        atr_pct = float(curr_row.get('ATR_PCT', 0))
        adx = float(curr_row.get('ADX', 0))
        min_adx_thresh = effective_min_adx if effective_min_adx is not None else self.min_adx

        # Перевіряємо ATR та ADX: якщо волатильність нижча за поріг або немає тренду - це ФЛЕТ
        if atr_pct < self.min_atr_pct or adx < (min_adx_thresh / 100.0):
            return MarketRegime.CHOP
        if ema_dist > 0.005:
            return MarketRegime.BULL
        if ema_dist < -0.005:
            return MarketRegime.BEAR
            
        return MarketRegime.CHOP

    def get_signal(
        self, 
        df: pd.DataFrame, 
        ai_confidence: float, 
        in_position: bool = False,
        htf_trend: Optional[str] = None,
        btc_pulse: Optional[str] = None,
        order_book_status: Optional[str] = None,
        funding_sentiment: Optional[str] = None
    ) -> Tuple[Optional[SignalAction], SignalMetadata]:
        
        required_cols = {'RSI', 'EMA_DIST_50', 'MACD_HIST', 'ATR_PCT', 'ADX'}
        if df is None or df.empty or len(df) < 2 or not required_cols.issubset(df.columns):
            return None, self._empty_meta()

        # Розрахунок адаптивних динамічних порогів (Етап 3)
        effective_min_adx = self.risk_controller.get_effective_min_adx(self.min_adx) if self.risk_controller else self.min_adx
        effective_base_threshold = self.risk_controller.get_effective_confidence_threshold(self.base_threshold) if self.risk_controller else self.base_threshold

        curr = df.iloc[-1]
        current_price = float(curr['close'])
        regime = self._detect_regime(curr, effective_min_adx=effective_min_adx)
        vol_spike_val = round(float(curr.get('VOL_SPIKE', 1.0)), 2)
        
        meta = SignalMetadata(
            price=current_price,
            ai_conf=round(ai_confidence, 2),
            rsi=round(float(curr['RSI']) * 100, 2), # Повертаємо RSI до формату 0-100
            trend=TrendDirection.UP if curr['EMA_DIST_50'] > 0 else TrendDirection.DOWN,
            regime=regime,
            htf_trend=htf_trend or "NEUTRAL",
            btc_pulse=btc_pulse or "HEALTHY",
            vol_spike=vol_spike_val,
            order_book_status=order_book_status or "NEUTRAL",
            funding_sentiment=funding_sentiment or "HEALTHY_BALANCED",
            reason="Evaluating..."
        )

        if in_position:
            meta.reason = "Already in position"
            return None, meta

        # БАЗОВІ ТЕХНІЧНІ ФІЛЬТРИ (Забороняємо торгівлю проти логіки)
        
        # 1. Жодних угод у мертвому ринку (з урахуванням адаптивного ADX)
        if regime == MarketRegime.CHOP:
            meta.reason = f"Market is CHOPPY (ADX < {effective_min_adx:.1f})"
            return SignalAction.HOLD, meta

        # 2. Фільтр перегрітості (RSI > 70)
        if meta.rsi >= 70:
            meta.reason = f"RSI Overbought ({meta.rsi:.1f})"
            return SignalAction.HOLD, meta
            
        # 3. Фільтр лову ножів (не купуємо падаючий ніж у ведмежому тренді, якщо MACD падає)
        if regime == MarketRegime.BEAR and float(curr['MACD_HIST']) <= 0:
            meta.reason = "Bearish MACD in Bear Market"
            return SignalAction.HOLD, meta

        # 4. МУЛЬТИ-ТАЙМФРЕЙМ ФІЛЬТР (MTF): Заборона покупок, якщо старший 1h тренд спадний
        if htf_trend == "BEARISH":
            meta.reason = "Higher TF (1h) Downtrend (Blocked)"
            return SignalAction.HOLD, meta

        # 5. BTC MARKET PULSE ФІЛЬТР: Заборона покупок, якщо Bitcoin під тиском скидання
        if btc_pulse == "BEARISH_DUMP":
            meta.reason = "BTC Market Pulse Bearish (Blocked)"
            return SignalAction.HOLD, meta

        # 6. VSA VOLUME CONFIRMATION: Фільтр аномально низького об'єму або слабкого тиску покупців
        if 'VOL_SPIKE' in curr:
            vol_spike = float(curr['VOL_SPIKE'])
            if vol_spike < 0.85:
                meta.reason = f"Low Volume Breakout ({vol_spike:.2f}x SMA) (Blocked)"
                return SignalAction.HOLD, meta

        if 'BUY_PRESSURE' in curr:
            buy_press = float(curr['BUY_PRESSURE'])
            if buy_press < 0.35:
                meta.reason = f"Weak Buyer Pressure ({buy_press:.2f}) (Blocked)"
                return SignalAction.HOLD, meta

        # 7. L2 ORDER BOOK DEPTH & FUNDING RATE GUARDS (Етап 1: Підвищення вінрейту до 70%+)
        if order_book_status == "HEAVY_ASK_RESISTANCE":
            meta.reason = "Order Book Ask Wall Resistance (Blocked)"
            return SignalAction.HOLD, meta

        if funding_sentiment == "OVERHEATED_LONGS":
            meta.reason = "Funding Rate Overheated Longs (>0.05%) (Blocked)"
            return SignalAction.HOLD, meta

        # 7. ENSEMBLE AI CONSENSUS (Дворівневе підтвердження: ML ймовірність + Квант-фактори)
        trend_score = 1.0 if float(curr.get('EMA_DIST_50', 0)) > 0 else 0.0
        mom_score = 1.0 if float(curr.get('MACD_HIST', 0)) > 0 else 0.0
        vol_score = 1.0 if vol_spike_val >= 1.0 and float(curr.get('BUY_PRESSURE', 0.5)) >= 0.45 else 0.5
        rsi_val = float(meta.rsi)
        rsi_score = 1.0 if (35.0 <= rsi_val <= 65.0) else 0.5

        quant_factor_score = round(0.30 * trend_score + 0.25 * mom_score + 0.25 * vol_score + 0.20 * rsi_score, 2)
        ensemble_conf = round(0.65 * float(ai_confidence) + 0.35 * quant_factor_score, 2)

        meta.quant_score = quant_factor_score
        meta.ensemble_conf = ensemble_conf

        # Фільтр дивергенції ансамблю (якщо квантові фактори різко суперечать сигналу)
        if quant_factor_score < 0.30:
            meta.reason = f"Ensemble Factor Divergence (Quant={quant_factor_score:.2f} < 0.30) (Blocked)"
            return SignalAction.HOLD, meta

        # Етап 3: Заборона спотових покупок у спадному тренді (BEAR_MARKET)
        if regime == MarketRegime.BEAR:
            meta.reason = "Spot BUY disallowed in BEAR_MARKET (Blocked)"
            return SignalAction.HOLD, meta

        # ШІ ПОРОГИ (Вимоги до дерев рішень для BULL ринку)
        threshold = effective_base_threshold
            
        # Ухвалення рішення
        if ai_confidence >= threshold:
            meta.reason = f"AI_Smart_Signal_{regime.value}(Conf={ai_confidence:.2f}>={threshold:.2f}, Ens={ensemble_conf:.2f})"
            return SignalAction.BUY, meta

        meta.reason = f"Insufficient confidence ({ai_confidence:.2f} < {threshold:.2f})"
        return SignalAction.HOLD, meta

    def _empty_meta(self) -> SignalMetadata:
        return SignalMetadata(
            price=0.01, ai_conf=0.0, rsi=50.0,
            trend=TrendDirection.FLAT, regime=MarketRegime.CHOP,
            htf_trend="NEUTRAL", btc_pulse="HEALTHY", vol_spike=1.0,
            quant_score=0.0, ensemble_conf=0.0,
            order_book_status="NEUTRAL", funding_sentiment="HEALTHY_BALANCED",
            reason="Invalid DataFrame"
        )