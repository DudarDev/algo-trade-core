import pandas as pd
import logging
from typing import Optional, Literal, Tuple, Dict
from src.shared.config import Settings 

logger = logging.getLogger(__name__)

class HybridStrategy:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Тепер беремо з .env (якщо є), інакше за замовчуванням
        self.conf_threshold = getattr(settings, 'CONFIDENCE_THRESHOLD', 0.6)
        self.rsi_buy_limit = getattr(settings, 'RSI_BUY_LIMIT', 70)  
        self.use_trend_filter = getattr(settings, 'TREND_FILTER', True)

    def get_signal(
        self, 
        df: pd.DataFrame, 
        ai_confidence: float, 
        in_position: bool = False
    ) -> Tuple[Optional[Literal["BUY", "SELL"]], Dict]:
        required_cols = ['RSI', 'EMA_DIST_50', 'MACD_HIST']
        if df.empty or not all(col in df.columns for col in required_cols):
            logger.debug("Відсутні необхідні індикатори для стратегії.")
            return None, {}
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        is_uptrend = curr['EMA_DIST_50'] > 0
        meta = {
            "price": float(curr['close']),
            "ai_conf": round(ai_confidence, 2),
            "rsi": round(curr['RSI'] * 100, 1),
            "trend": "UP" if is_uptrend else "DOWN"
        }
        
        if in_position:
            return None, meta

        # 1. Жорсткий поріг впевненості AI
        if ai_confidence < self.conf_threshold:
            return None, meta

        # 2. Трендовий фільтр (якщо увімкнено)
        if self.use_trend_filter and not is_uptrend:
            return None, meta

        # 3. Перевірка RSI – не перекупленість
        if (curr['RSI'] * 100) >= self.rsi_buy_limit:
            return None, meta

        # 4. Гістограма MACD (перетин нульової лінії) – додатковий підтверджуючий фактор
        macd_cross_up = prev['MACD_HIST'] <= 0 and curr['MACD_HIST'] > 0
        if macd_cross_up:
            meta['reason'] = "MACD_Bullish_AI_Confirmed"
            return "BUY", meta

        # Якщо всі фільтри пройдено – вхід
        meta['reason'] = f"AI_Sniper(Conf={ai_confidence:.2f})"
        return "BUY", meta
