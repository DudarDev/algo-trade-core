import pandas as pd
import pandas_ta as ta  # Використовуємо pandas-ta для зручності, або ручний розрахунок

class Strategy:
    def __init__(self, rsi_period=14, rsi_oversold=30, rsi_overbought=70):
        self.period = rsi_period
        self.oversold = rsi_oversold
        self.overbought = rsi_overbought
        
        # --- НОВІ НАЛАШТУВАННЯ ---
        self.stop_loss_percent = 0.02   # 2% втрати - продаємо
        self.take_profit_percent = 0.05 # 5% прибутку - продаємо

    def calculate_indicators(self, df):
        """
        Розраховує RSI для всього датафрейму
        """
        # Класичний розрахунок RSI вручну (щоб не залежати від зайвих бібліотек)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df

    def get_signal(self, df, in_position=False, entry_price=0):
        """
        Повертає 'BUY', 'SELL' або None
        
        in_position: Чи купили ми вже крипту?
        entry_price: За якою ціною купили? (Потрібно для Stop-Loss)
        """
        if df.empty:
            return None

        current_rsi = df.iloc[-1]['rsi']
        current_price = df.iloc[-1]['close']
        
        # 1. Логіка КУПІВЛІ (Тільки якщо ми не в позиції)
        if not in_position:
            if current_rsi < self.oversold:
                return "BUY"

        # 2. Логіка ПРОДАЖУ (Якщо ми в позиції)
        else:
            # А. Перевірка Stop-Loss (Чи не впали ми занадто низько?)
            if current_price <= entry_price * (1 - self.stop_loss_percent):
                print(f"🛑 STOP-LOSS спрацював! Вхід: {entry_price}, Зараз: {current_price}")
                return "SELL"

            # Б. Перевірка Take-Profit (Чи не заробили ми вже достатньо?)
            if current_price >= entry_price * (1 + self.take_profit_percent):
                print(f"💰 TAKE-PROFIT спрацював! Вхід: {entry_price}, Зараз: {current_price}")
                return "SELL"

            # В. Стандартний вихід по RSI
            if current_rsi > self.overbought:
                return "SELL"
                
        return None