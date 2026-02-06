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
        self.rsi_buy_limit = 60  # Трохи підняли, бо в сильному тренді RSI рідко падає низько
        self.rsi_sell_limit = 75
        self.min_history = 200   # Збільшили до 200 для розрахунку EMA

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Розрахунок RSI, MACD, ATR, ADX та EMA."""
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

        # 3. ATR (Критично для стопів)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # 4. ADX (Сила тренду)
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx is not None:
            df['adx'] = adx.iloc[:, 0]
        else:
            df['adx'] = 0
            
        # 5. EMA 200 (Глобальний фільтр тренду) - NEW 🔥
        df['ema200'] = ta.ema(df['close'], length=200)

        return df

    def get_signal(
        self, 
        df: pd.DataFrame, 
        ai_confidence: float, 
        in_position: bool = False
    ) -> Tuple[Optional[Literal["BUY", "SELL"]], Dict]:
        
        # Перевірка наявності всіх індикаторів
        required_cols = ['atr', 'ema200', 'adx', 'rsi']
        if df.empty or not all(col in df.columns for col in required_cols):
            return None, {}

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Метадані для логів (щоб ти бачив, ЧОМУ він купив/продав)
        meta = {
            "price": curr['close'],
            "ai_conf": round(ai_confidence, 2),
            "rsi": round(curr['rsi'], 1),
            "atr": curr['atr'],
            "adx": round(curr['adx'], 1)
        }

        # --- ЛОГІКА ВИХОДУ (SELL) ---
        if in_position:
            # Жорсткий вихід, якщо індикатори кричать "Розворот!"
            macd_death_cross = (prev['macd'] > prev['macd_signal']) and (curr['macd'] < curr['macd_signal'])
            rsi_extreme = curr['rsi'] > self.rsi_sell_limit
            
            # Якщо ми пробили EMA 200 вниз - це поганий знак для лонга
            trend_broken = (prev['close'] > prev['ema200']) and (curr['close'] < curr['ema200'])

            if rsi_extreme:
                meta['reason'] = "RSI_Overbought"
                return "SELL", meta
            
            if macd_death_cross and curr['rsi'] > 50:
                meta['reason'] = "MACD_Cross_Down"
                return "SELL", meta
            
            if trend_broken:
                meta['reason'] = "Trend_Broken_EMA200"
                return "SELL", meta
            
            return None, meta

        # --- ЛОГІКА ВХОДУ (BUY) ---
        else:
            # 🔥 ФІЛЬТРИ (Щоб підняти Win Rate)
            is_uptrend = curr['close'] > curr['ema200'] # Ціна вище EMA 200 (Тільки лонг по тренду)
            has_momentum = curr['adx'] > 20             # Ринок не "мертвий" (флет)
            
            # Сценарій 1: AI Sniper (Розумний вхід)
            # Ми дозволяємо вхід, якщо AI дуже впевнений, 
            # АЛЕ тільки якщо ми не в даунтренді (або AI > 0.80 - супер впевнений контртренд)
            if ai_confidence >= Config.AI_CONFIDENCE_THRESHOLD:
                if (is_uptrend or ai_confidence > 0.80) and curr['rsi'] < 70:
                    meta['reason'] = f"AI_Sniper_Trend({is_uptrend})"
                    return "BUY", meta

            # Сценарій 2: Tech Reversion (Тільки по тренду!)
            # Купуємо відкат (Golden Cross) у висхідному тренді
            macd_golden_cross = (prev['macd'] < prev['macd_signal']) and (curr['macd'] > curr['macd_signal'])
            
            if is_uptrend and has_momentum:
                if macd_golden_cross and curr['rsi'] < self.rsi_buy_limit:
                    # Додатковий фільтр: AI не повинен бути категорично проти (хоча б > 0.4)
                    if ai_confidence > 0.40:
                        meta['reason'] = "Trend_Pullback+AI"
                        return "BUY", meta

        return None, meta