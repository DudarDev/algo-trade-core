import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import GradientBoostingClassifier
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

    def fetch_deep_history(self, symbol):
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=1000)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df
        except: return pd.DataFrame()

    def prepare_features(self, df):
        data = df.copy()
        
        # --- ГОЛОВНІ ІНДИКАТОРИ ДЛЯ ЦІЄЇ СТРАТЕГІЇ ---
        
        # 1. RSI (Індекс відносної сили)
        # Якщо RSI < 30 -> Перепродано (ціна впала занадто сильно) -> Можливий ріст
        data['RSI'] = ta.rsi(data['close'], length=14)
        
        # 2. Bollinger Bands (Канал ціни)
        # Якщо ціна пробила нижню лінію -> Вона захоче повернутися до центру
        try:
            bb = ta.bbands(data['close'], length=20)
            if bb is not None:
                data['BB_LOWER'] = bb.iloc[:, 0]
                data['Dist_BB'] = (data['close'] - data['BB_LOWER']) / data['BB_LOWER']
            else: data['Dist_BB'] = 0
        except: data['Dist_BB'] = 0

        # 3. Об'єм (RVOL)
        # Чи є інтерес до монети?
        try:
            data['RVOL'] = data['volume'] / data['volume'].rolling(20).mean()
        except: data['RVOL'] = 1.0

        data.dropna(inplace=True)
        return data

    def train_new_model(self, short_df, symbol='BTC/USDT'):
        deep_df = self.fetch_deep_history(symbol)
        df = self.prepare_features(deep_df if not deep_df.empty else short_df)
        
        if len(df) < 50: return

        # TARGET: Вчимося знаходити моменти, коли ціна відскакує вгору на 0.3%
        future_return = df['close'].shift(-1) / df['close'] - 1
        df['Target'] = np.where(future_return > 0.003, 1, 0)
        df.dropna(inplace=True)

        if len(df['Target'].unique()) < 2: return

        # Вчимося на: RSI (наскільки дешево), Відстань до дна, Об'єм
        feature_cols = ['RSI', 'Dist_BB', 'RVOL']
        
        try:
            # Використовуємо RandomForest, він краще працює з шумом
            from sklearn.ensemble import RandomForestClassifier
            self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
            self.model.fit(df[feature_cols], df['Target'])
            self.is_trained = True
            joblib.dump(self.model, self.model_path)
            print(f"✅ [AI Reversion] Модель навчена ловити відскоки.")
        except Exception as e:
            print(f"❌ Error: {e}")

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

        feature_cols = ['RSI', 'Dist_BB', 'RVOL']
        try:
            last_features = df[feature_cols].iloc[[-1]]
            prediction = self.model.predict(last_features)[0]
            proba = self.model.predict_proba(last_features)[0]
            
            # --- АГРЕСИВНИЙ ВХІД ---
            # 1. AI каже "Так" з впевненістю > 55%
            # 2. АБО RSI дуже низький (< 30) - це "золотий сигнал"
            rsi_val = last_features['RSI'].values[0]
            
            if (prediction == 1 and proba[1] > 0.55) or (rsi_val < 30):
                return "BUY"
            
            # Продаємо, якщо AI каже падіння або RSI занадто високий (>70)
            elif (prediction == 0 and proba[0] > 0.55) or (rsi_val > 70):
                return "SELL"
                
        except: return "HOLD"
        
        return "HOLD"