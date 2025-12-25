import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import GradientBoostingClassifier
import joblib
import os

class TradingAI:
    def __init__(self, model_path='data/ai_model_v3.pkl'):
        self.model = None
        self.model_path = model_path
        self.is_trained = False
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

    def prepare_features(self, df):
        data = df.copy()
        
        # 1. RSI
        data['RSI'] = ta.rsi(data['close'], length=14)
        
        # 2. MACD (Захищений метод)
        try:
            macd = ta.macd(data['close'])
            if macd is not None and not macd.empty:
                data['MACD'] = macd.iloc[:, 0]
                data['MACD_SIGNAL'] = macd.iloc[:, 2]
            else:
                data['MACD'] = 0
                data['MACD_SIGNAL'] = 0
        except:
             data['MACD'] = 0
             data['MACD_SIGNAL'] = 0
        
        # 3. Bollinger Bands (Захищений метод)
        try:
            bb = ta.bbands(data['close'], length=20)
            if bb is not None and not bb.empty:
                data['BB_LOWER'] = bb.iloc[:, 0] 
                data['BB_UPPER'] = bb.iloc[:, 2]
                # Ширина каналу
                data['BB_WIDTH'] = (data['BB_UPPER'] - data['BB_LOWER']) / data['BB_LOWER']
            else:
                data['BB_LOWER'] = data['close']
                data['BB_WIDTH'] = 0
        except:
            data['BB_LOWER'] = data['close']
            data['BB_WIDTH'] = 0
        
        # 4. Відстань до ліній
        data['Dist_BB'] = np.where(data['BB_LOWER'] != 0, (data['close'] - data['BB_LOWER']) / data['BB_LOWER'], 0)
        
        data.dropna(inplace=True)
        return data

    def train_new_model(self, historical_df):
        print("🧠 [AI v3.1] Аналіз ринку для навчання...")
        df = self.prepare_features(historical_df)
        
        if len(df) < 50:
            print("⚠️ Замало даних.")
            return

        # TARGET: Шукаємо рух > 0.4%
        future_return = df['close'].shift(-1) / df['close'] - 1
        df['Target'] = np.where(future_return > 0.004, 1, 0)
        df.dropna(inplace=True)

        # --- ГОЛОВНЕ ВИПРАВЛЕННЯ ---
        # Перевіряємо, чи є в історії хоч один приклад успішної угоди (1)
        # Якщо всі "0", то вчитися немає на чому -> пропускаємо
        if len(df['Target'].unique()) < 2:
            print("💤 Ринок надто спокійний (немає рухів > 0.4%). Тренування пропущено, чекаю волатильності.")
            return
        # ---------------------------

        feature_cols = ['RSI', 'MACD', 'MACD_SIGNAL', 'Dist_BB', 'BB_WIDTH']
        X = df[feature_cols]
        y = df['Target']
        
        try:
            self.model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.05, max_depth=3, random_state=42)
            self.model.fit(X, y)
            self.is_trained = True
            joblib.dump(self.model, self.model_path)
            print(f"✅ [AI v3.1] Модель успішно оновлена.")
        except Exception as e:
            print(f"❌ Помилка тренування: {e}")

    def load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                return True
            except: return False
        return False

    def predict(self, current_candle_df):
        if not self.is_trained:
            if not self.load_model(): return "HOLD"

        df = self.prepare_features(current_candle_df)
        if df.empty: return "HOLD"

        feature_cols = ['RSI', 'MACD', 'MACD_SIGNAL', 'Dist_BB', 'BB_WIDTH']
        try:
            last_features = df[feature_cols].iloc[[-1]]
            prediction = self.model.predict(last_features)[0]
            probability = self.model.predict_proba(last_features)[0]
            
            if prediction == 1 and probability[1] > 0.70:
                return "BUY"
            elif prediction == 0 and probability[0] > 0.70:
                return "SELL"
        except Exception as e:
            return "HOLD"
        
        return "HOLD"