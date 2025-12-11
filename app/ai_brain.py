import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

class TradingAI:
    def __init__(self, model_path='data/ai_model.pkl'):
        self.model = None
        self.model_path = model_path
        self.is_trained = False
        # Створюємо папку data, якщо вона ще не існує
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

    def prepare_features(self, df):
        """
        Перетворює ринкові дані на зрозумілі для AI числа (індикатори).
        """
        data = df.copy()
        
        # 1. Додаємо технічні індикатори
        # RSI (Індекс відносної сили)
        data['RSI'] = ta.rsi(data['close'], length=14)
        
        # SMA (Ковзні середні)
        data['SMA_20'] = ta.sma(data['close'], length=20)
        data['SMA_50'] = ta.sma(data['close'], length=50)
        
        # ATR (Волатильність)
        data['ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)
        
        # 2. Видаляємо пусті рядки
        data.dropna(inplace=True)
        
        return data

    def train_new_model(self, historical_df):
        """
        Вчить бота на історії торгів.
        """
        print("🧠 [AI] Починаю навчання моделі...")
        
        df = self.prepare_features(historical_df)
        
        if len(df) < 50: # Зменшив ліміт для тестів
            print("⚠️ [AI] Замало даних!")
            return

        # Target: 1 (Ріст) або 0 (Падіння)
        df['Target'] = np.where(df['close'].shift(-1) > df['close'], 1, 0)
        df.dropna(inplace=True)

        feature_cols = ['RSI', 'SMA_20', 'SMA_50', 'ATR']
        
        X = df[feature_cols]
        y = df['Target']
        
        self.model = RandomForestClassifier(n_estimators=100, min_samples_split=10, random_state=42)
        self.model.fit(X, y)
        
        self.is_trained = True
        joblib.dump(self.model, self.model_path)
        print(f"✅ [AI] Модель успішно натренована та збережена.")

    def load_model(self):
        """Завантажує файл моделі з диска"""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                return True
            except Exception as e:
                print(f"⚠️ [AI] Помилка завантаження: {e}")
                return False
        return False

    def predict(self, current_candle_df):
        """
        Приймає поточні свічки та повертає сигнал.
        """
        # Спроба завантажити модель, якщо вона не в пам'яті
        if not self.is_trained:
            if not self.load_model():
                return "HOLD" 

        df = self.prepare_features(current_candle_df)
        
        if df.empty:
            return "HOLD"

        # Беремо останню свічку
        feature_cols = ['RSI', 'SMA_20', 'SMA_50', 'ATR']
        try:
            last_features = df[feature_cols].iloc[[-1]]
        except KeyError:
            return "HOLD"
        
        prediction = self.model.predict(last_features)[0]
        probability = self.model.predict_proba(last_features)[0]
        
        threshold = 0.60 
        
        if prediction == 1 and probability[1] > threshold:
            return "BUY"
        elif prediction == 0 and probability[0] > threshold:
            return "SELL"
        
        return "HOLD"