import pandas as pd
import numpy as np
import pandas_ta as ta
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
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
        
        self.loaded_models: Dict[str, CalibratedClassifierCV] = {}
        
        # 🔥 Додано нові фічі: ADX_SLOPE (Фаза ринку) та BUY_PRESSURE (Замінник Order Book)
        self.base_features = [
            'RSI', 'BB_WIDTH', 'BB_POS', 'RVOL', 
            'ATR_PCT', 'EMA_DIST', 'ADX', 'ADX_SLOPE', 
            'BUY_PRESSURE', 'LOG_RET', 'VOL_SPIKE'
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
        
        # 🔥 НОВЕ: Нахил ADX (Чи наростає сила тренду?)
        data['ADX_SLOPE'] = data['ADX'].diff()

        vol_sma = data['volume'].rolling(window=20).mean()
        data['RVOL'] = data['volume'] / (vol_sma + 1e-9)

        # Детекція сплеску об'єму (Volume Spike)
        vol_std = data['volume'].rolling(window=20).std()
        data['VOL_SPIKE'] = (data['volume'] > (vol_sma + 2 * vol_std)).astype(int)

        # 🔥 НОВЕ: Buying Pressure (Форма свічки: чи закриваємось ми під хай?)
        data['BUY_PRESSURE'] = (data['close'] - data['low']) / (data['high'] - data['low'] + 1e-9)

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
        # 🔥 ЗМІНЕНО НА _v3: Щоб бот скинув старі моделі і перенавчився з калібруванням
        return os.path.join(self.model_dir, f"{safe_symbol}_v3.pkl")

    def train_model(self, df: pd.DataFrame, symbol: str):
        data = self.prepare_features(df)
        if len(data) < 100: 
            return

        feature_cols = self._get_feature_names()
        # Таргет: чи досягнемо ми 1.5 ATR протягом наступних 4 свічок
        future_max = data['high'].rolling(window=4).max().shift(-4)
        target_price = data['close'] + (data['ATR'] * 1.5)
        data['Target'] = (future_max > target_price).astype(int)

        valid_data = data.dropna(subset=['Target'])
        X, y = valid_data[feature_cols], valid_data['Target']

        if len(np.unique(y)) < 2: 
            return

        # 🔥 НОВЕ: Обгортаємо RF у CalibratedClassifierCV
        rf_base = RandomForestClassifier(
            n_estimators=100, max_depth=12, min_samples_split=10,
            min_samples_leaf=5, class_weight='balanced', n_jobs=-1, random_state=42
        )
        
        # Використовуємо Sigmoid (Platt Scaling) для калібрування ймовірностей
        calibrated_model = CalibratedClassifierCV(estimator=rf_base, method='sigmoid', cv=5)
        calibrated_model.fit(X, y)
        
        joblib.dump(calibrated_model, self._get_model_path(symbol))
        self.loaded_models[symbol] = calibrated_model
        logger.info(f"✅ AI Brain: {symbol} (v3) успішно навчена з Probability Calibration та Buy Pressure.")

    def predict(self, data_input: Any, symbol: str) -> Tuple[str, float]:
        model = self.loaded_models.get(symbol)
        
        if model is None:
            path = self._get_model_path(symbol)
            if os.path