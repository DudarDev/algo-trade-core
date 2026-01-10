import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import ccxt

class TradingAI:
    def __init__(self, model_path='data/ai_model_reversion.pkl'):
        self.model = None
        self.model_path = model_path
        self.is_trained = False
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.exchange = ccxt.binanceus() 

        # --- FULL POWER SETTINGS (e2-medium) ---
        self.CONFIDENCE_THRESHOLD = 0.75  # Тільки впевнені входи
        self.MIN_TRAINING_SAMPLES = 50    # Мінімальна кількість даних

    def fetch_deep_history(self, symbol):
        """Завантажує глибоку історію (3.5 днів по 5хв)"""
        try:
            # FULL POWER: limit=1000
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
            return pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        except: 
            return pd.DataFrame()

    def prepare_features(self, df):
        """Генерація фіч + ЗАХИСТ ВІД INFINITY"""
        data = df.copy()
        
        if len(data) < 30: return pd.DataFrame()

        # 1. RSI
        data['RSI'] = ta.rsi(data['close'], length=14)
        
        # 2. Bollinger Bands
        try:
            bb = ta.bbands(data['close'], length=20, std=2.0)
            if bb is not None:
                # Захист від ділення на нуль
                bandwidth = (bb.iloc[:, 2] - bb.iloc[:, 0]).replace(0, 0.0000001)
                data['BB_POS'] = (data['close'] - bb.iloc[:, 0]) / bandwidth
            else: 
                data['BB_POS'] = 0.5
        except: 
            data['BB_POS'] = 0.5

        # 3. ATR (Волатильність)
        try:
            data['ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)
            data['ATR_PCT'] = data['ATR'] / data['close']
        except:
            data['ATR_PCT'] = 0.0

        # 4. Relative Volume (RVOL)
        try:
            vol_mean = data['volume'].replace(0, 1).rolling(20).mean()
            data['RVOL'] = data['volume'] / vol_mean
        except: 
            data['RVOL'] = 1.0

        # --- SAFETY SANITIZER ---
        # Це рятує бота від падіння!
        data = data.replace([np.inf, -np.inf], np.nan)
        data.dropna(inplace=True)
        
        return data

    def train_new_model(self, short_df, symbol='BTC/USDT'):
        """Тренування потужної моделі"""
        deep_df = self.fetch_deep_history(symbol)
        df = self.prepare_features(deep_df if not deep_df.empty else short_df)
        
        if len(df) < self.MIN_TRAINING_SAMPLES: return

        # TARGET: Шукаємо рух +0.4%
        future_return = df['close'].shift(-1) / df['close'] - 1
        df['Target'] = np.where(future_return > 0.004, 1, 0)
        df.dropna(inplace=True)

        if len(df['Target'].unique()) < 2: return 

        feature_cols = ['RSI', 'BB_POS', 'RVOL', 'ATR_PCT']
        
        try:
            # FULL POWER: 100 дерев, глибина 5
            self.model = RandomForestClassifier(
                n_estimators=100, 
                max_depth=5,     
                min_samples_leaf=5,
                random_state=42,
                class_weight='balanced'
            )
            self.model.fit(df[feature_cols], df['Target'])
            self.is_trained = True
            joblib.dump(self.model, self.model_path)
        except Exception as e:
            print(f"❌ ML Error: {e}")

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

        feature_cols = ['RSI', 'BB_POS', 'RVOL', 'ATR_PCT']
        
        try:
            last_features = df[feature_cols].iloc[[-1]]
            
            prediction = self.model.predict(last_features)[0]
            proba = self.model.predict_proba(last_features)[0]
            
            # Впевненість > 75%
            if prediction == 1 and proba[1] >= self.CONFIDENCE_THRESHOLD:
                return "BUY"
            
            return "HOLD"
                
        except Exception as e:
            return "HOLD"