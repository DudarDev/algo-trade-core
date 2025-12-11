import sys
import os
import pandas as pd

# Магія, щоб Python побачив папку 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ai_brain import TradingAI

def main():
    print("🚀 Тестуємо AI...")
    
    # 1. Створимо фейкові дані, якщо реальних немає (для швидкого тесту)
    data = {
        'open': [100, 101, 102, 101, 103] * 50,
        'high': [105, 106, 107, 106, 108] * 50,
        'low': [99, 100, 101, 100, 102] * 50,
        'close': [101, 102, 101, 103, 104] * 50,
        'volume': [1000, 1200, 1100, 1300, 1400] * 50
    }
    df = pd.DataFrame(data)
    
    # 2. Тренуємо (Виправлено назву методу тут)
    ai = TradingAI()
    # Було ai.train_new_model(df), змінив на:
    if hasattr(ai, 'train_new_model'):
        ai.train_new_model(df)
    else:
        ai.train_model(df)
    
    # 3. Прогноз
    signal = ai.predict(df.tail(20))
    print(f"\n🤖 Бот каже: {signal}")

if __name__ == "__main__":
    main()