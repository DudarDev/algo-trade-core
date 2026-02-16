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
        self.rsi_buy_limit = 65  # Підняли поріг (було 60), щоб ловити сильніші рухи
        self.rsi_sell_limit = 75
        self.min_history = 200   # Потрібно мінімум 200 свічок для EMA 200
        
        # Поріг сили тренду (ADX)
        self.adx_threshold = 20  # Якщо менше 20 - це флет (боковик)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Розрахунок технічних індикаторів: RSI, MACD, ATR, ADX, EMA200.
        Використовує бібліотеку pandas_ta.
        """
        if df.empty or len(df) < self.min_history:
            return pd.DataFrame()

        df = df.copy()

        # 1. RSI (Індекс відносної сили)
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)

        # 2. MACD (Сходження/розходження ковзних середніх)
        # macd повертає 3 колонки: MACD, Histogram, Signal
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['macd'] = macd.iloc[:, 0]        # Лінія MACD
            df['macd_signal'] = macd.iloc[:, 2] # Сигнальна лінія
        else:
            df['macd'] = 0
            df['macd_signal'] = 0

        # 3. ATR (Середній істинний діапазон) - для розрахунку Стоп-Лоссів
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        # 4. ADX (Середній індекс спрямованості) - Сила тренду
        # adx повертає 3 колонки: ADX, DMP, DMN. Нам треба тільки ADX (індекс 0)
        adx = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx is not None:
            df['adx'] = adx.iloc[:, 0]
        else:
            df['adx'] = 0
            
        # 5. EMA 200 (Експоненційна ковзна середня) - Глобальний тренд
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
        
        # Перевірка наявності всіх необхідних колонок
        required_cols = ['atr', 'ema200', 'adx', 'rsi', 'macd']
        if df.empty or not all(col in df.columns for col in required_cols):
            return None, {}

        # Беремо останню свічку (curr) і передостанню (prev)
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Збираємо метадані для логів (щоб розуміти, чому бот прийняв рішення)
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
            # 1. MACD Death Cross (Перетин вниз) - класичний сигнал на продаж
            macd_death_cross = (prev['macd'] > prev['macd_signal']) and (curr['macd'] < curr['macd_signal'])
            
            # 2. RSI перекуплений (ціна занадто висока)
            rsi_extreme = curr['rsi'] > self.rsi_sell_limit
            
            # 3. Злам тренду (Ціна впала нижче EMA 200)
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
            # --- ФІЛЬТРИ (Щоб відсіяти шум) ---
            
            # 1. Глобальний тренд: Тільки якщо ціна вище EMA 200
            is_uptrend = curr['close'] > curr['ema200'] 
            
            # 2. Імпульс ринку: Тільки якщо ADX > 20 (є сила руху)
            has_momentum = curr['adx'] > self.adx_threshold 
            
            # --- СЦЕНАРІЙ 1: AI Sniper (Розумний вхід) ---
            # Якщо AI дуже впевнений (>= 0.85), ми можемо ігнорувати слабкий ADX,
            # але RSI все одно має бути адекватним (< 70).
            if ai_confidence >= Config.AI_CONFIDENCE_THRESHOLD:
                # Дозволяємо вхід, якщо ми в аптренді АБО якщо AI супер впевнений у відскоку
                if (is_uptrend or ai_confidence > 0.90) and curr['rsi'] < 70:
                    meta['reason'] = f"AI_Sniper(Conf={ai_confidence:.2f})"
                    return "BUY", meta

            # --- СЦЕНАРІЙ 2: Tech Reversion (Технічний відкат) ---
            # Класична стратегія: Купуємо на "Золотому перетині" MACD, 
            # АЛЕ тільки якщо є тренд (is_uptrend) і сила (has_momentum).
            macd_golden_cross = (prev['macd'] < prev['macd_signal']) and (curr['macd'] > curr['macd_signal'])
            
            if is_uptrend and has_momentum:
                if macd_golden_cross and curr['rsi'] < self.rsi_buy_limit:
                    # Додатковий фільтр: AI не повинен бути категорично проти (> 0.40)
                    if ai_confidence > 0.40:
                        meta['reason'] = f"Trend_Pullback(ADX={meta['adx']})"
                        return "BUY", meta

        return None, meta