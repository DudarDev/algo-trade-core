import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import logging
from typing import Optional, Tuple, Dict, Literal, Any

# Налаштування логера
logger = logging.getLogger("TradingAI")

class TradingAI:
    def __init__(self, model_dir: str = 'data/models/'):
        self.model_dir = model_dir
        self.CONFIDENCE_THRESHOLD = 0.60 
        os.makedirs(self.model_dir, exist_ok=True)
        
        self.loaded_models: Dict[str, RandomForestClassifier] = {}
        
        # Базові фічі
        # 🔥 НОВЕ: Додано фічу VOL_SPIKE для детекції аномальних об'ємів
        self.base_features = [
            'RSI', 'BB_WIDTH', 'BB_POS', 'RVOL', 
            'ATR_PCT', 'EMA_DIST', 'ADX', 'LOG_RET', 'VOL_SPIKE'
        ]
        self.lag_features = ['RSI', 'LOG_RET', 'RVOL']
        self.lags = [1, 2]

    def _get_feature_names(self) -> list:
        cols = self.base_features.copy()
        for feature in self.lag_features:
            for lag in self.lags:
                cols.append(f"{feature}_lag_{lag}")
        return cols

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 50:
            return pd.DataFrame()

        data = df.copy().sort_values('timestamp')

        # --- 1. Basic Indicators ---
        data['RSI'] = ta.rsi(data['close'], length=14) / 100.0
        
        bb = ta.bbands(data['close'], length=20, std=2.0)
        if bb is not None:
            data['BB_WIDTH'] = (bb.iloc[:, 0] - bb.iloc[:, 2]) / bb.iloc[:, 1]
            data['BB_POS'] = (data['close'] - bb.iloc[:, 2]) / (bb.iloc[:, 0] - bb.iloc[:, 2])
        else:
            data['BB_WIDTH'], data['BB_POS'] = 0, 0.5

        data['ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)
        data['ATR_PCT'] = data['ATR'] / data['close']
        
        adx_df = ta.adx(data['high'], data['low'], data['close'], length=14)
        data['ADX'] = adx_df.iloc[:, 0] / 100.0 if adx_df is not None else 0

        vol_sma = data['volume'].rolling(window=20).mean()
        data['RVOL'] = data['volume'] / (vol_sma + 1e-9)

        # 🔥 НОВЕ: Детекція сплеску об'єму (Volume Spike)
        # Визначаємо як відхилення поточного об'єму від 2-х стандартних відхилень
        vol_std = data['volume'].rolling(window=20).std()
        data['VOL_SPIKE'] = (data['volume'] > (vol_sma + 2 * vol_std)).astype(int)

        ema_period = 200 if len(data) > 300 else 50
        ema = ta.ema(data['close'], length=ema_period)
        data['EMA_DIST'] = (data['close'] - ema) / (ema + 1e-9)
        data['LOG_RET'] = np.log(data['close'] / data['close'].shift(1))

        for feature in self.lag_features:
            for lag in self.lags:
                data[f"{feature}_lag_{lag}"] = data[feature].shift(lag)

        return data.replace([np.inf, -np.inf], np.nan).dropna()

    def _get_model_path(self, symbol: str) -> str:
        safe_symbol = symbol.replace('/', '_')
        return os.path.join(self.model_dir, f"{safe_symbol}.pkl")

    def train_model(self, df: pd.DataFrame, symbol: str):
        data = self.prepare_features(df)
        if len(data) < 100: return

        feature_cols = self._get_feature_names()
        future_max = data['high'].rolling(window=4).max().shift(-4)
        target_price = data['close'] + (data['ATR'] * 1.5)
        data['Target'] = (future_max > target_price).astype(int)

        valid_data = data.dropna(subset=['Target'])
        X, y = valid_data[feature_cols], valid_data['Target']

        if len(np.unique(y)) < 2: return

        model = RandomForestClassifier(
            n_estimators=100, max_depth=12, min_samples_split=10,
            min_samples_leaf=5, class_weight='balanced', n_jobs=-1, random_state=42
        )
        model.fit(X, y)
        joblib.dump(model, self._get_model_path(symbol))
        self.loaded_models[symbol] = model
        logger.info(f"✅ AI Brain: {symbol} навчена з Volume Spike аналізом.")

    # 🔥 ОНОВЛЕНО: Тепер приймає або DataFrame, або автоматично визначає тип
    def predict(self, data_input: Any, symbol: str) -> Tuple[str, float]:
        """
        Універсальний предикт. 
        data_input може бути DataFrame (для входу) або symbol (якщо викликається з PaperTrader)
        """
        model = self.loaded_models.get(symbol)
        if model is None:
            path = self._get_model_path(symbol)
            if os.path.exists(path):
                model = joblib.load(path)
                self.loaded_models[symbol] = model
            else:
                return "HOLD", 0.0

        # Якщо на вхід прийшов DataFrame (з main.py)
        if isinstance(data_input, pd.DataFrame):
            processed_df = self.prepare_features(data_input)
        else:
            # Тут можна додати логіку отримання даних за символом, якщо потрібно
            return "HOLD", 0.0

        if processed_df.empty: return "HOLD", 0.0

        try:
            feature_cols = self._get_feature_names()
            last_row = processed_df[feature_cols].iloc[[-1]]
            proba = model.predict_proba(last_row)[0][1]

            # Логіка сигналу
            signal = "BUY" if proba >= self.CONFIDENCE_THRESHOLD else "HOLD"
            return signal, float(proba)
            
        except Exception as e:
            logger.error(f"❌ Predict Error {symbol}: {e}")
            return "HOLD", 0.0