import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import logging
from typing import Optional, Tuple, Dict, Literal

# Налаштування логера
logger = logging.getLogger("TradingAI")

class TradingAI:
    def __init__(self, model_dir: str = 'data/models/'):
        self.model_dir = model_dir
        # Поріг впевненості: 0.60 достатньо для Random Forest, 
        # бо він консервативніший за Gradient Boosting
        self.CONFIDENCE_THRESHOLD = 0.60 
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Кеш для моделей у пам'яті, щоб не читати диск щоразу
        self.loaded_models: Dict[str, RandomForestClassifier] = {}
        
        # Базові фічі
        self.base_features = [
            'RSI', 'BB_WIDTH', 'BB_POS', 'RVOL', 
            'ATR_PCT', 'EMA_DIST', 'ADX', 'LOG_RET'
        ]
        # Лаги для контексту (що було 1 та 2 свічки тому)
        self.lag_features = ['RSI', 'LOG_RET', 'RVOL']
        self.lags = [1, 2]

    def _get_feature_names(self) -> list:
        """Генерує повний список колонок для навчання."""
        cols = self.base_features.copy()
        for feature in self.lag_features:
            for lag in self.lags:
                cols.append(f"{feature}_lag_{lag}")
        return cols

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Векторизована підготовка даних. 
        Додає Log Returns та історичні лаги для контексту.
        """
        if len(df) < 50:
            return pd.DataFrame()

        data = df.copy().sort_values('timestamp')

        # --- 1. Basic Indicators ---
        # RSI
        data['RSI'] = ta.rsi(data['close'], length=14) / 100.0
        
        # Bollinger Bands (Width + Position)
        bb = ta.bbands(data['close'], length=20, std=2.0)
        if bb is not None:
            # data['BB_WIDTH'] = bb.iloc[:, 2] / data['close'] # Bandwidth (залежить від версії pandas_ta)
            # Часто простіше порахувати вручну: (Upper - Lower) / Middle
            data['BB_WIDTH'] = (bb.iloc[:, 0] - bb.iloc[:, 2]) / bb.iloc[:, 1]
            data['BB_POS'] = (data['close'] - bb.iloc[:, 2]) / (bb.iloc[:, 0] - bb.iloc[:, 2])
        else:
            data['BB_WIDTH'] = 0
            data['BB_POS'] = 0.5

        # ATR & Volatility
        data['ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)
        data['ATR_PCT'] = data['ATR'] / data['close']
        
        # ADX (Trend Strength)
        adx_df = ta.adx(data['high'], data['low'], data['close'], length=14)
        if adx_df is not None:
            data['ADX'] = adx_df.iloc[:, 0] / 100.0
        else:
            data['ADX'] = 0

        # Relative Volume (RVOL)
        vol_sma = data['volume'].rolling(window=20).mean()
        data['RVOL'] = data['volume'] / (vol_sma + 1e-9)

        # EMA Distance (Trend Direction)
        ema_period = 200 if len(data) > 300 else 50
        ema = ta.ema(data['close'], length=ema_period)
        data['EMA_DIST'] = (data['close'] - ema) / (ema + 1e-9)

        # --- 2. Advanced: Log Returns (Stationarity) ---
        data['LOG_RET'] = np.log(data['close'] / data['close'].shift(1))

        # --- 3. Lagged Features (Time Context) ---
        for feature in self.lag_features:
            for lag in self.lags:
                data[f"{feature}_lag_{lag}"] = data[feature].shift(lag)

        # Очищення від NaN
        data = data.replace([np.inf, -np.inf], np.nan).dropna()
        return data

    def _get_model_path(self, symbol: str) -> str:
        safe_symbol = symbol.replace('/', '_')
        return os.path.join(self.model_dir, f"{safe_symbol}.pkl")

    def train_model(self, df: pd.DataFrame, symbol: str):
        """Навчання Random Forest."""
        data = self.prepare_features(df)
        
        if len(data) < 100:
            logger.warning(f"⚠️ {symbol}: Замало даних ({len(data)}).")
            return

        feature_cols = self._get_feature_names()
        
        # Target: Price > Close + 1.5 ATR через 4 свічки
        future_max = data['high'].rolling(window=4).max().shift(-4)
        target_price = data['close'] + (data['ATR'] * 1.5)
        
        data['Target'] = (future_max > target_price).astype(int)

        valid_data = data.dropna(subset=['Target'])
        
        X = valid_data[feature_cols]
        y = valid_data['Target']

        if len(np.unique(y)) < 2:
            return

        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=12,
            min_samples_split=10,
            min_samples_leaf=5, 
            class_weight='balanced',
            n_jobs=-1,
            random_state=42
        )
        
        model.fit(X, y)
        
        joblib.dump(model, self._get_model_path(symbol))
        self.loaded_models[symbol] = model
        
        logger.info(f"✅ AI Brain: Модель {symbol} навчена. Features: {len(feature_cols)}")

    def predict(self, df: pd.DataFrame, symbol: str) -> Tuple[Literal["BUY", "HOLD"], float]:
        """Предикт з використанням кешу."""
        model = self.loaded_models.get(symbol)
        
        if model is None:
            path = self._get_model_path(symbol)
            if os.path.exists(path):
                try:
                    model = joblib.load(path)
                    self.loaded_models[symbol] = model
                except Exception as e:
                    logger.error(f"❌ Corrupted model {symbol}: {e}")
                    return "HOLD", 0.0
            else:
                return "HOLD", 0.0

        processed_df = self.prepare_features(df)
        if processed_df.empty:
            return "HOLD", 0.0

        try:
            feature_cols = self._get_feature_names()
            # Перевіряємо, чи всі колонки є (на випадок зміни логіки)
            if not all(col in processed_df.columns for col in feature_cols):
                return "HOLD", 0.0
                
            last_row = processed_df[feature_cols].iloc[[-1]]
            
            # [0] - ймовірність падіння/флету, [1] - ймовірність росту
            proba = model.predict_proba(last_row)[0][1]

            if proba >= self.CONFIDENCE_THRESHOLD:
                return "BUY", proba
            
            return "HOLD", proba
            
        except Exception as e:
            logger.error(f"❌ Predict Error {symbol}: {e}")
            return "HOLD", 0.0