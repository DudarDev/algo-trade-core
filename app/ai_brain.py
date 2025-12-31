import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import GradientBoostingClassifier
import joblib
import os
import ccxt # Додаємо бібліотеку для самостійного скачування

class TradingAI:
    def __init__(self, model_path='data/ai_model_v6.pkl'):
        self.model = None
        self.model_path = model_path
        self.is_trained = False
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        # Власний клієнт для скачування глибокої історії
        self.exchange = ccxt.binanceus() 

    def fetch_deep_history(self, symbol):
        """
        Скачує 1500 свічок (5 днів) для глибокого аналізу тренду.
        Це дозволяє боту бачити 'велику картину'.
        """
        try:
            # print(f"📥 [AI] Завантажую глибоку історію для {symbol}...")
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=1500)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return df
        except:
            return pd.DataFrame()

    def prepare_features(self, df):
        data = df.copy()
        
        # 1. RSI
        data['RSI'] = ta.rsi(data['close'], length=14)
        
        # 2. MACD
        try:
            macd = ta.macd(data['close'])
            if macd is not None:
                data['MACD'] = macd.iloc[:, 0]
                data['MACD_SIGNAL'] = macd.iloc[:, 2]
            else:
                data['MACD'] = 0
                data['MACD_SIGNAL'] = 0
        except:
             data['MACD'] = 0; data['MACD_SIGNAL'] = 0
        
        # 3. Bollinger Bands (Ширина каналу важлива!)
        try:
            bb = ta.bbands(data['close'], length=20)
            if bb is not None:
                data['BB_LOWER'] = bb.iloc[:, 0]
                data['BB_UPPER'] = bb.iloc[:, 2]
                # Відносна ширина каналу (показує волатильність)
                data['BB_WIDTH'] = (data['BB_UPPER'] - data['BB_LOWER']) / data['BB_LOWER']
            else:
                data['BB_LOWER'] = data['close']; data['BB_WIDTH'] = 0
        except:
            data['BB_LOWER'] = data['close']; data['BB_WIDTH'] = 0
        
        # Відстань до низу Боллінджера
        data['Dist_BB'] = np.where(data['BB_LOWER'] != 0, (data['close'] - data['BB_LOWER']) / data['BB_LOWER'], 0)

        # 4. SMA 200 (Глобальний тренд) - тепер це можливо, бо у нас багато даних!
        data['SMA_200'] = ta.sma(data['close'], length=200)
        data['Trend_Global'] = np.where(data['close'] > data['SMA_200'], 1, -1) # 1 = Бичачий, -1 = Ведмежий

        data.dropna(inplace=True)
        return data

    def train_new_model(self, short_df, symbol='BTC/USDT'):
        """
        Тепер метод приймає symbol, щоб скачати собі більше даних.
        """
        # 1. Скачуємо глибоку історію замість короткої
        deep_df = self.fetch_deep_history(symbol)
        
        if len(deep_df) < 500:
            # Якщо не вийшло скачати, використовуємо те, що дали
            df = self.prepare_features(short_df)
        else:
            df = self.prepare_features(deep_df)
            print(f"🧠 [AI v6.0] Навчання на {len(df)} свічках (Глибокий контекст).")

        # TARGET: Шукаємо рух > 0.45% (підняли планку для надійності)
        future_return = df['close'].shift(-1) / df['close'] - 1
        df['Target'] = np.where(future_return > 0.0045, 1, 0)
        df.dropna(inplace=True)

        if len(df['Target'].unique()) < 2:
            print("💤 Ринок спить. Немає на чому вчитись.")
            return

        feature_cols = ['RSI', 'MACD', 'MACD_SIGNAL', 'Dist_BB', 'BB_WIDTH', 'Trend_Global']
        X = df[feature_cols]
        y = df['Target']
        
        try:
            # Збільшили кількість дерев (estimators) бо даних стало більше
            self.model = GradientBoostingClassifier(n_estimators=200, learning_rate=0.05, max_depth=5, random_state=42)
            self.model.fit(X, y)
            self.is_trained = True
            joblib.dump(self.model, self.model_path)
            print(f"✅ [AI v6.0] Модель успішно оновлена.")
        except Exception as e:
            print(f"❌ Помилка AI: {e}")

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

        feature_cols = ['RSI', 'MACD', 'MACD_SIGNAL', 'Dist_BB', 'BB_WIDTH', 'Trend_Global']
        try:
            last_features = df[feature_cols].iloc[[-1]]
            prediction = self.model.predict(last_features)[0]
            probability = self.model.predict_proba(last_features)[0]
            
            # Якщо впевненість > 75% (підняли поріг)
            if prediction == 1 and probability[1] > 0.75:
                return "BUY"
            elif prediction == 0 and probability[0] > 0.75:
                return "SELL"
        except:
            return "HOLD"
        
        return "HOLD"