import pandas_ta as ta
import pandas as pd
import logging
from typing import Optional, Literal

logger = logging.getLogger("Strategy")

class Strategy:
    def __init__(self):
        # RSI settings
        self.rsi_period = 14
        self.rsi_buy_limit = 45 
        self.rsi_sell_limit = 70 # Трохи підняли, щоб не виходити зарано

        # MACD settings
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Розрахунок індикаторів з гарантованим мапінгом колонок."""
        # Копіюємо, щоб не змінювати оригінальний DF поза функцією
        df = df.copy()
        
        # RSI
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)

        # MACD
        macd_df = ta.macd(df['close'], fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal)
        # Мапимо колонки незалежно від назв, які генерує бібліотека
        df['macd'] = macd_df.iloc[:, 0]        # MACD Line
        df['macd_signal'] = macd_df.iloc[:, 2] # Signal Line
        df['macd_hist'] = macd_df.iloc[:, 1]   # Histogram

        return df

    def get_signal(self, df: pd.DataFrame, in_position: bool = False) -> Optional[Literal["BUY", "SELL"]]:
        """
        Логіка генерації сигналів. 
        Ризик-менеджмент (SL/TP) тепер винесено в Main Loop (Risk Engine),
        тут тільки стратегічні сигнали.
        """
        if df.empty or len(df) < 35:
            return None

        # Беремо останні два рядки для аналізу перетинів
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        # --- ЛОГІКА КУПІВЛІ (BUY) ---
        if not in_position:
            # 1. MACD Golden Cross
            macd_cross_up = (prev['macd'] < prev['macd_signal']) and (curr['macd'] > curr['macd_signal'])
            
            # 2. Фільтр: MACD має бути нижче нуля (зона перепроданості)
            macd_low = curr['macd'] < 0
            
            # 3. RSI Filter
            rsi_ok = curr['rsi'] < self.rsi_buy_limit

            if macd_cross_up and macd_low and rsi_ok:
                return "BUY"

        # --- ЛОГІКА ПРОДАЖУ (SELL) ---
        else:
            # Вихід за технічними показниками (якщо AI або Risk Engine не спрацювали раніше)
            # MACD Death Cross
            macd_cross_down = (prev['macd'] > prev['macd_signal']) and (curr['macd'] < curr['macd_signal'])
            
            # RSI Overbought
            rsi_overbought = curr['rsi'] > self.rsi_sell_limit

            if macd_cross_down or rsi_overbought:
                return "SELL"

        return None