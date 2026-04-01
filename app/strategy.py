import pandas as pd
import pandas_ta as ta
import logging
from typing import Optional, Literal, Tuple, Dict
from app.config import settings 

logger = logging.getLogger(__name__)

class Strategy:
    def __init__(self):
        self.rsi_period: int = 14
        self.rsi_buy_limit: int = 65  
        self.min_history: int = 200   
        self.adx_threshold: int = 20  

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < self.min_history:
            return pd.DataFrame()
        df = df.copy()
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        df['ema200'] = ta.ema(df['close'], length=200)
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df['macd'] = macd.iloc[:, 0]        
            df['macd_signal'] = macd.iloc[:, 2] 
        else:
            df['macd'], df['macd_signal'] = 0.0, 0.0
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx is not None and not adx.empty:
            df['adx'] = adx.iloc[:, 0]
        else:
            df['adx'] = 0.0
        df['obv'] = ta.obv(df['close'], df['volume'])
        df = df.fillna(0.0)
        return df

    def get_signal(self, df: pd.DataFrame, ai_confidence: float, in_position: bool = False) -> Tuple[Optional[Literal["BUY", "SELL"]], Dict]:
        required_cols = ['atr', 'ema200', 'adx', 'rsi', 'macd', 'obv']
        if df.empty or not all(col in df.columns for col in required_cols):
            return None, {}
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        is_uptrend = curr['close'] > curr['ema200']
        meta = {
            "price": float(curr['close']),
            "ai_conf": round(ai_confidence, 2),
            "rsi": round(curr['rsi'], 1),
            "atr": round(curr['atr'], 4),
            "adx": round(curr['adx'], 1),
            "trend": "UP" if is_uptrend else "DOWN"
        }
        if in_position:
            return None, meta
        has_momentum = curr['adx'] > self.adx_threshold 
        if ai_confidence >= settings.CONFIDENCE_THRESHOLD:
            if (is_uptrend or ai_confidence > 0.90) and curr['rsi'] < 70:
                meta['reason'] = f"AI_Sniper(Conf={ai_confidence:.2f})"
                return "BUY", meta
        macd_golden_cross = (prev['macd'] < prev['macd_signal']) and (curr['macd'] > curr['macd_signal'])
        if is_uptrend and has_momentum:
            if macd_golden_cross and curr['rsi'] < self.rsi_buy_limit:
                if ai_confidence > 0.40:
                    meta['reason'] = f"Trend_Pullback(ADX={meta['adx']})"
                    return "BUY", meta
        return None, meta
