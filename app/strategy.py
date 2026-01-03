import pandas_ta as ta
import pandas as pd


class Strategy:
    def __init__(self):
        # Налаштування RSI
        self.rsi_period = 14
        self.rsi_buy_limit = 45  # Трохи вище 30, бо ми чекаємо підтвердження MACD
        self.rsi_sell_limit = 65

        # Налаштування MACD
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

        # Ризик-менеджмент
        self.stop_loss_percent = 0.02  # 2% втрати
        self.take_profit_percent = 0.05  # 5% прибутку

    def calculate_indicators(self, df):
        """Розрахунок RSI та MACD через pandas_ta"""
        # RSI
        df.ta.rsi(length=self.rsi_period, append=True)

        # MACD (Додасть колонки MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9)
        df.ta.macd(
            fast=self.macd_fast,
            slow=self.macd_slow,
            signal=self.macd_signal,
            append=True,
        )

        # Перейменуємо для зручності (pandas_ta дає довгі назви)
        # Назви можуть змінюватися, тому беремо останні колонки
        df.rename(
            columns={
                f"RSI_{self.rsi_period}": "rsi",
                f"MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}": "macd",
                f"MACDs_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}": "macd_signal",
            },
            inplace=True,
        )

        return df

    def get_signal(self, df, in_position=False, entry_price=0):
        if df.empty or len(df) < 30:
            return None

        # Беремо останні дані
        current_rsi = df.iloc[-1]["rsi"]
        current_macd = df.iloc[-1]["macd"]
        current_signal = df.iloc[-1]["macd_signal"]

        # Попередні дані (щоб побачити перетин ліній)
        prev_macd = df.iloc[-2]["macd"]
        prev_signal = df.iloc[-2]["macd_signal"]

        current_price = df.iloc[-1]["close"]

        # --- ЛОГІКА ПРОДАЖУ (SELL) ---
        if in_position:
            # 1. Stop-Loss
            if current_price <= entry_price * (1 - self.stop_loss_percent):
                return "SELL"
            # 2. Take-Profit
            if current_price >= entry_price * (1 + self.take_profit_percent):
                return "SELL"
            # 3. RSI перегрітий (занадто дорого)
            if current_rsi > self.rsi_sell_limit:
                return "SELL"

        # --- ЛОГІКА КУПІВЛІ (BUY) ---
        else:
            # Умова 1: RSI не в космосі (ціна адекватна)
            # Умова 2: MACD перетинає Сигнальну лінію ЗНИЗУ ВГОРУ (Золотий хрест)
            # Тобто: вчора MACD був нижче сигналу, а сьогодні - вище
            macd_cross_up = (prev_macd < prev_signal) and (
                current_macd > current_signal
            )

            if current_rsi < self.rsi_buy_limit and macd_cross_up:
                return "BUY"

        return None
