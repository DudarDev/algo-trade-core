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
        self.min_history: int = 50    # Залишаємо 50, щоб працювало зі стандартним лімітом Binance
        self.adx_threshold: int = 20  

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < self.min_history:
            return pd.DataFrame()
        
        df = df.copy()
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        # Використовуємо 50 періодів, щоб відповідати min_history
        df['ema_fast'] = ta.ema(df['close'], length=50) 
        
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df['macd'] = macd.iloc[:, 0]        
            df['macd_signal'] = macd.iloc[:, 2] 
        else:
            df['macd'], df['macd_signal'] = 0.0, 0.0
            
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx.iloc[:, 0] if adx is not None else 0.0
        df['obv'] = ta.obv(df['close'], df['volume'])
        
        return df.fillna(0.0)

    def get_signal(self, df: pd.DataFrame, ai_confidence: float, in_position: bool = False) -> Tuple[Optional[Literal["BUY", "SELL"]], Dict]:
        required_cols = ['atr', 'ema_fast', 'adx', 'rsi', 'macd']
        if df.empty or not all(col in df.columns for col in required_cols):
            return None, {}
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Логіка тренду: ціна вище середньої
        is_uptrend = curr['close'] > curr['ema_fast']
        
        meta = {
            "price": float(curr['close']),
            "ai_conf": round(ai_confidence, 2),
            "rsi": round(curr['rsi'], 1),
            "trend": "UP" if is_uptrend else "DOWN"
        }
        
        if in_position:
            return None, meta

        # --- ТИМЧАСОВИЙ ТЕСТ ДЛЯ ДАШБОРДУ (КАМІКАДЗЕ) ---
        # Купуємо абсолютно все, де ШІ видає хоча б 10% впевненості
        if ai_confidence >= 0.10:
            meta['reason'] = f"TEST_DASHBOARD(Conf={ai_confidence:.2f})"
            return "BUY", meta
            
        return None, meta