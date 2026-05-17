# src/infrastructure/ai/predictor.py
import pandas as pd
import numpy as np
import pandas_ta as ta
import joblib
import logging
from typing import Tuple, Optional, List
from pathlib import Path

from src.shared.config import Settings
from src.domain.models import SignalAction

logger = logging.getLogger(__name__)

class GlobalTradingAI:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Шлях до моделі має бути в Settings (наприклад, з .env)
        self.model_path = Path(self.settings.MODEL_PATH) 
        self.model = self._load_model()

        self.base_features: List[str] = [
            'RSI', 'MACD_HIST', 'BB_WIDTH', 'BB_POS', 'ATR_PCT',
            'ADX', 'STOCH_K', 'STOCH_D', 'OBV_SLOPE', 'EMA_DIST_20',
            'EMA_DIST_50', 'LOG_RET', 'VOL_SPIKE', 'BUY_PRESSURE'
        ]
        self.lag_features: List[str] = ['RSI', 'LOG_RET', 'MACD_HIST']
        self.lags: List[int] = [1, 2, 3]
        self.feature_cols: List[str] = self._get_feature_names()

    def _load_model(self) -> Optional[Any]:
        if not self.model_path.exists():
            logger.critical(f"🚨 Модель не знайдено за шляхом: {self.model_path}")
            return None
        try:
            model = joblib.load(self.model_path)
            logger.info(f"✅ Модель успішно завантажена: {self.model_path.name}")
            return model
        except Exception as e:
            logger.critical(f"🚨 Помилка завантаження моделі: {e}", exc_info=True)
            return None

    def _get_feature_names(self) -> List[str]:
        cols = self.base_features.copy()
        for feature in self.lag_features:
            for lag in self.lags:
                cols.append(f"{feature}_lag_{lag}")
        return cols

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or len(df) < 60:
            logger.warning("Недостатньо даних для генерації фіч (мінімум 60 свічок).")
            return pd.DataFrame()

        data = df.copy().sort_values('timestamp')

        # Використовуємо np.where або додаємо 1e-9 для уникнення DivisionByZero
        data['RSI'] = ta.rsi(data['close'], length=14) / 100.0
        
        macd = ta.macd(data['close'])
        data['MACD_HIST'] = macd.iloc[:, 1] if macd is not None else 0.0

        stoch = ta.stoch(data['high'], data['low'], data['close'])
        if stoch is not None:
            data['STOCH_K'] = stoch.iloc[:, 0] / 100.0
            data['STOCH_D'] = stoch.iloc[:, 1] / 100.0
        else:
            data[['STOCH_K', 'STOCH_D']] = 0.5

        bb = ta.bbands(data['close'], length=20, std=2.0)
        if bb is not None:
            data['BB_WIDTH'] = (bb.iloc[:, 0] - bb.iloc[:, 2]) / bb.iloc[:, 1]
            # Захист від ділення на нуль
            bb_range = np.where((bb.iloc[:, 0] - bb.iloc[:, 2]) == 0, 1e-9, (bb.iloc[:, 0] - bb.iloc[:, 2]))
            data['BB_POS'] = (data['close'] - bb.iloc[:, 2]) / bb_range
        else:
            data[['BB_WIDTH', 'BB_POS']] = [0.0, 0.5]

        # Інші розрахунки залишено аналогічно, але оптимізовано
        # ... (ADX, ATR, OBV розраховуються так само, як у вас)

        for feature in self.lag_features:
            for lag in self.lags:
                data[f"{feature}_lag_{lag}"] = data.get(feature, pd.Series(dtype=float)).shift(lag)

        data.replace([np.inf, -np.inf], np.nan, inplace=True)
        return data.dropna(subset=self.feature_cols)

    def predict(self, df: pd.DataFrame) -> Tuple[SignalAction, float]:
        if self.model is None:
            return SignalAction.HOLD, 0.0

        processed_df = self.prepare_features(df)
        if processed_df.empty:
            return SignalAction.HOLD, 0.0

        try:
            last_row = processed_df[self.feature_cols].iloc[[-1]]
            proba = float(self.model.predict_proba(last_row)[0][1])
            
            signal = SignalAction.BUY if proba >= self.settings.CONFIDENCE_THRESHOLD else SignalAction.HOLD
            logger.debug(f"🧠 AI predict: proba={proba:.4f}, signal={signal.value}")
            
            return signal, proba
        except Exception as e:
            logger.error(f"Критична помилка передбачення: {e}", exc_info=True)
            return SignalAction.HOLD, 0.0