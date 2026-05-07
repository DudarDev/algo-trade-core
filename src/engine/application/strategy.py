import pandas as pd
import logging
from typing import Optional, Literal, Tuple, Dict
from src.shared.config import Settings 

logger = logging.getLogger(__name__)

class HybridStrategy:
    """Гібридна стратегія: валідує сигнали AI за допомогою класичного Технічного Аналізу."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        # Виносимо магічні числа в конфігурацію класу
        self.rsi_buy_limit: int = 70  
        self.macd_conf_threshold: float = 0.45

    def get_signal(
        self, 
        df: pd.DataFrame, 
        ai_confidence: float, 
        in_position: bool = False
    ) -> Tuple[Optional[Literal["BUY", "SELL"]], Dict]:
        """
        Приймає DataFrame з ВЖЕ розрахованими індикаторами (від ai_brain) 
        та впевненість ШІ.
        """
        # Наш ai_brain.py генерує колонку 'RSI', 'MACD_HIST', 'EMA_DIST_50'
        # Адаптуємо логіку під ці нові назви колонок.
        required_cols = ['RSI', 'EMA_DIST_50', 'MACD_HIST']
        if df.empty or not all(col in df.columns for col in required_cols):
            logger.debug("Відсутні необхідні індикатори для стратегії.")
            return None, {}
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Якщо EMA_DIST_50 > 0, ціна вище за EMA50 (Висхідний тренд)
        is_uptrend = curr['EMA_DIST_50'] > 0
        
        meta = {
            "price": float(curr['close']),
            "ai_conf": round(ai_confidence, 2),
            "rsi": round(curr['RSI'] * 100, 1), # Повертаємо у формат 0-100
            "trend": "UP" if is_uptrend else "DOWN"
        }
        
        if in_position:
            return None, meta

        # 1. Снайперський вхід (Висока впевненість ШІ + Тренд + Не перекуплено)
        if ai_confidence >= self.settings.CONFIDENCE_THRESHOLD:
            if is_uptrend and (curr['RSI'] * 100) < self.rsi_buy_limit:
                meta['reason'] = f"AI_Sniper(Conf={ai_confidence:.2f})"
                return "BUY", meta

        # 2. Підтвердження через гістограму MACD (перетин нульової лінії)
        macd_cross_up = prev['MACD_HIST'] <= 0 and curr['MACD_HIST'] > 0
        if macd_cross_up and is_uptrend and ai_confidence > self.macd_conf_threshold:
            meta['reason'] = "MACD_Bullish_AI_Confirmed"
            return "BUY", meta
            
        return None, meta