import matplotlib.pyplot as plt
import pandas as pd

class ChartGenerator:
    def __init__(self):
        self.filename = "data/trading_chart.png"

    def create_chart(self, df, symbol, buy_signals, sell_signals):
        """
        df: Таблиця з цінами
        buy_signals: Список точок покупки [(time, price), ...]
        sell_signals: Список точок продажу [(time, price), ...]
        """
        plt.figure(figsize=(12, 6)) # Розмір картинки
        
        # 1. Малюємо графік ціни
        plt.plot(df['time'], df['close'], label='Price', color='skyblue', linewidth=1.5)

        # 2. Малюємо точки ПОКУПКИ (Зелені трикутники вгору)
        if buy_signals:
            times = [x[0] for x in buy_signals]
            prices = [x[1] for x in buy_signals]
            plt.scatter(times, prices, marker='^', color='green', s=100, label='BUY', zorder=5)

        # 3. Малюємо точки ПРОДАЖУ (Червоні трикутники вниз)
        if sell_signals:
            times = [x[0] for x in sell_signals]
            prices = [x[1] for x in sell_signals]
            plt.scatter(times, prices, marker='v', color='red', s=100, label='SELL', zorder=5)

        # Оформлення
        plt.title(f"Trading Bot Chart: {symbol}")
        plt.xlabel("Time")
        plt.ylabel("Price (USDT)")
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Збереження у файл
        plt.savefig(self.filename)
        plt.close()
        print(f"🖼️  Графік оновлено! Дивись файл: {self.filename}")