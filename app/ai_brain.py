import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import logging
from typing import Optional, List, Literal

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TradingAI")

class TradingAI:
    def __init__(self, model_path: str = 'data/ai_model_reversion.pkl'):
        self.model: Optional[RandomForestClassifier] = None
        self.model_path = model_path
        self.is_trained = False
        self.feature_cols: List[str] = ['RSI', 'BB_POS', 'RVOL', 'ATR_PCT', 'EMA_DIST']
        
        # Гіперпараметри
        self.CONFIDENCE_THRESHOLD = 0.65 
        self.MIN_TRAINING_SAMPLES = 200 # Збільшено для стабільності
        
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Векторизована генерація ознак."""
        if len(df) < 200: 
            return pd.DataFrame()

        data = df.copy().sort_values('timestamp')
        
        # 1. RSI
        data['RSI'] = ta.rsi(data['close'], length=14) / 100.0 # Нормалізація 0-1
        
        # 2. Bollinger Bands
        bb = ta.bbands(data['close'], length=20, std=2.0)
        lower_band = bb[f'BBL_20_2.0']
        upper_band = bb[f'BBU_20_2.0']
        data['BB_POS'] = (data['close'] - lower_band) / (upper_band - lower_band).replace(0, 1e-9)

        # 3. Волатильність та Об'єм
        data['ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)
        data['ATR_PCT'] = data['ATR'] / data['close']
        
        vol_sma = data['volume'].rolling(window=20).mean()
        data['RVOL'] = data['volume'] / vol_sma.replace(0, 1e-9)

        # 4. Тренд (Відстань до EMA 200)
        ema200 = ta.ema(data['close'], length=200)
        data['EMA_DIST'] = (data['close'] - ema200) / ema200

        # Очистка
        data = data.replace([np.inf, -np.inf], np.nan).dropna()
        return data

    def train_model(self, df: pd.DataFrame, symbol: str = "Unknown"):
        """Навчання моделі з валідацією."""
        processed_df = self.prepare_features(df)
        
        if len(processed_df) < self.MIN_TRAINING_SAMPLES:
            logger.warning(f"⚠️ {symbol}: Недостатньо даних для навчання ({len(processed_df)})")
            return

        # TARGET: рух +0.5% за наступну свічку
        future_return = processed_df['close'].shift(-1) / processed_df['close'] - 1
        processed_df['Target'] = (future_return > 0.005).astype(int)
        
        # Видаляємо останній рядок (де немає Target)
        train_data = processed_df.iloc[:-1].copy()

        if len(train_data['Target'].unique()) < 2:
            return

        try:
            self.model = RandomForestClassifier(
                n_estimators=150, 
                max_depth=7,     
                min_samples_leaf=10,
                random_state=42,
                class_weight='balanced_subsample'
            )
            self.model.fit(train_data[self.feature_cols], train_data['Target'])
            
            joblib.dump(self.model, self.model_path)
            self.is_trained = True
            logger.info(f"✅ Модель успішно навчена на {len(train_data)} зразках для {symbol}")
        except Exception as e:
            logger.error(f"❌ Помилка ML: {e}")

    def predict(self, df: pd.DataFrame, symbol: str = "N/A") -> Literal["BUY", "HOLD"]:
        """Предикт з використанням ймовірності."""
        if not self.is_trained and not self.load_model():
            return "HOLD"

        processed_df = self.prepare_features(df)
        if processed_df.empty:
            return "HOLD"

        try:
            last_row = processed_df[self.feature_cols].iloc[[-1]]
            proba = self.model.predict_proba(last_row)[0][1]

            if proba >= self.CONFIDENCE_THRESHOLD:
                logger.info(f"🚀 SIGNAL BUY | {symbol} | Confidence: {proba:.2%}")
                return "BUY"
            
            return "HOLD"
        except Exception as e:
            logger.error(f"❌ Prediction error: {e}")
            return "HOLD"

    def load_model(self) -> bool:
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                return True
            except Exception as e:
                logger.error(f"❌ Load error: {e}")
        return False