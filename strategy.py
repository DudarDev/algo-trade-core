import pandas as pd
import pandas as pd

class Strategy:
    def __init__(self, rsi_period=14, rsi_overbought=70, rsi_oversold=30):
        self.period = rsi_period
        self.overbought = rsi_overbought
        self.oversold = rsi_oversold

    def calculate_rsi(self, df):
        """Розрахунок індикатора RSI вручну за допомогою pandas"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()

        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        return df

    def check_signal(self, df):
        """Аналізує останню свічку і повертає сигнал"""
        # Розраховуємо RSI
        df = self.calculate_rsi(df)
        
        # Беремо останнє значення RSI
        last_rsi = df['rsi'].iloc[-1]
        
        print(f"   📊 RSI індикатор: {round(last_rsi, 2)}")

        if last_rsi < self.oversold:
            return "BUY", last_rsi
        elif last_rsi > self.overbought:
            return "SELL", last_rsi
        else:
            return "NEUTRAL", last_rsi