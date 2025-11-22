import csv
import os
from datetime import datetime

class CSVLogger:
    def __init__(self, filename='trades_history.csv'):
        self.filename = filename
        
        # Якщо файлу немає — створюємо його і пишемо заголовки стовпців
        if not os.path.exists(self.filename):
            with open(self.filename, mode='w', newline='') as file:
                writer = csv.writer(file)
                # Заголовки нашої таблиці Excel
                writer.writerow(["Date", "Type", "Price", "Amount", "Balance", "RSI"])

    def log_trade(self, trade_type, price, amount, balance, rsi):
        """Записує нову угоду в кінець файлу"""
        try:
            with open(self.filename, mode='a', newline='') as file:
                writer = csv.writer(file)
                
                # Час зараз
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Запис рядка
                writer.writerow([now, trade_type, price, amount, balance, rsi])
                print(f"💾 Угоду записано у файл {self.filename}")
                
        except Exception as e:
            print(f"❌ Помилка запису у файл: {e}")
            