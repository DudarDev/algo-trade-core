import pandas_ta as ta
import pandas as pd
import logging
from typing import Optional, Literal, Tuple, Dict
from app.config import Config

logger = logging.getLogger("Strategy")

class Strategy:
    def __init__(self):
        # Параметри індикаторів
        self.rsi_period = 14
        self.rsi_buy_limit = 65  
        self.rsi_sell_limit = 75
        self.min_history = 200   
        
        # Поріг сили тренду (ADX)
        self.adx_threshold = 20  

    def check_global_trend(self, exchange_client, symbol: str) -> bool:
        """
        Перевіряє глобальний тренд на 1H (годинному) таймфреймі.
        Повертає True, якщо тренд висхідний, і False - якщо спадний.
        """
        try:
            # Завантажуємо останні 50 годинних свічок
            ohlcv = exchange_client.fetch_ohlcv(symbol, timeframe='1h', limit=50)
            if not ohlcv or len(ohlcv) < 20:
                return False
                
            df_1h = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            
            # Рахуємо просту ковзну середню (SMA) за 20 годин
            df_1h['SMA_20'] = df_1h['close'].rolling(window=20).mean()
            
            # Якщо поточна ціна закриття вища за середню за 20 годин - тренд висхідний
            last_close = df_1h['close'].iloc[-1]
            last_sma = df_1h['SMA_20'].iloc[-1]
            
            return last_close > last_sma
            
        except Exception as e:
            logger.warning(f"Trend check failed for {symbol}: {e}")
            return False

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Розрахунок технічних індикаторів: RSI, MACD, ATR, ADX, EMA200.
        Використовує бібліотеку pandas_ta.
        """
        if df.empty or len(df) < self.min_history:
            return pd.DataFrame()

        df = df.copy()

        # 1. RSI
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)

        # 2. MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['macd'] = macd.iloc[:, 0]        
            df['macd_signal'] = macd.iloc[:, 2] 
        else:
            df['macd'] = 0
            df['macd_signal'] = 0

        # 3. ATR 
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # 4. ADX 
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx is not None:
            df['adx'] = adx.iloc[:, 0]
        else:
            df['adx'] = 0
            
        # 5. EMA 200 
        df['ema200'] = ta.ema(df['close'], length=200)

        return df

    def get_signal(
        self, 
        df: pd.DataFrame, 
        ai_confidence: float, 
        in_position: bool = False
    ) -> Tuple[Optional[Literal["BUY", "SELL"]], Dict]:
        """
        Головна логіка прийняття рішень.
        Повертає: ("BUY" або "SELL" або None, словник з причинами)
        """
        required_cols = ['atr', 'ema200', 'adx', 'rsi', 'macd']
        if df.empty or not all(col in df.columns for col in required_cols):
            return None, {}

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        meta = {
            "price": curr['close'],
            "ai_conf": round(ai_confidence, 2),
            "rsi": round(curr['rsi'], 1),
            "atr": curr['atr'],
            "adx": round(curr['adx'], 1),
            "trend": "UP" if curr['close'] > curr['ema200'] else "DOWN"
        }

        # ==========================================
        # 🔴 ЛОГІКА ВИХОДУ (SELL)
        # ==========================================
        if in_position:
            macd_death_cross = (prev['macd'] > prev['macd_signal']) and (curr['macd'] < curr['macd_signal'])
            rsi_extreme = curr['rsi'] > self.rsi_sell_limit
            trend_broken = (prev['close'] > prev['ema200']) and (curr['close'] < curr['ema200'])

            if rsi_extreme:
                meta['reason'] = f"RSI_Overbought({round(curr['rsi'],1)})"
                return "SELL", meta
            
            if macd_death_cross and curr['rsi'] > 50:
                meta['reason'] = "MACD_Cross_Down"
                return "SELL", meta
            
            if trend_broken:
                meta['reason'] = "Trend_Broken_EMA200"
                return "SELL", meta
            
            return None, meta

        # ==========================================
        # 🟢 ЛОГІКА ВХОДУ (BUY)
        # ==========================================
        else:
            is_uptrend = curr['close'] > curr['ema200'] 
            has_momentum = curr['adx'] > self.adx_threshold 
            
            # --- СЦЕНАРІЙ 1: AI Sniper ---
            if ai_confidence >= Config.AI_CONFIDENCE_THRESHOLD:
                if (is_uptrend or ai_confidence > 0.90) and curr['rsi'] < 70:
                    meta['reason'] = f"AI_Sniper(Conf={ai_confidence:.2f})"
                    return "BUY", meta

            # --- СЦЕНАРІЙ 2: Tech Reversion ---
            macd_golden_cross = (prev['macd'] < prev['macd_signal']) and (curr['macd'] > curr['macd_signal'])
            
            if is_uptrend and has_momentum:
                if macd_golden_cross and curr['rsi'] < self.rsi_buy_limit:
                    if ai_confidence > 0.40:
                        meta['reason'] = f"Trend_Pullback(ADX={meta['adx']})"
                        return "BUY", meta

        return None, meta