import logging
from pathlib import Path
from typing import Tuple, Optional, List, Protocol

import joblib
import numpy as np
import pandas as pd
import pandas_ta as ta

from src.engine.domain.models import SignalAction
from src.shared.config import Settings

logger = logging.getLogger(__name__)


class MLModelProtocol(Protocol):
    """Протокол для ML-моделі замість Any, що гарантує наявність інтерфейсу scikit-learn."""
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        ...


class GlobalTradingAI:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_path = Path(self.settings.MODEL_PATH)
        self.model: Optional[MLModelProtocol] = self._load_model()

        self.base_features: List[str] = [
            'RSI', 'MACD_HIST', 'BB_WIDTH', 'BB_POS', 'ATR_PCT',
            'ADX', 'STOCH_K', 'STOCH_D', 'OBV_SLOPE', 'EMA_DIST_20',
            'EMA_DIST_50', 'LOG_RET', 'VOL_SPIKE', 'BUY_PRESSURE'
        ]
        self.lag_features: List[str] = ['RSI', 'LOG_RET', 'MACD_HIST']
        self.lags: List[int] = [1, 2, 3]
        self.feature_cols: List[str] = self._get_feature_names()

    def _load_model(self) -> Optional[MLModelProtocol]:
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
        """Валідує, розраховує всі необхідні 14 індикаторів та повертає чистий датасет."""
        if df is None or df.empty or len(df) < 60:
            pass
            return pd.DataFrame()

        # Валідація наявності базових OHLCV колонок
        required_input_cols = {'high', 'low', 'close', 'volume', 'timestamp'}
        if not required_input_cols.issubset(df.columns):
            logger.error(f"❌ Вхідний DataFrame не містить базових колонок: {required_input_cols - set(df.columns)}")
            return pd.DataFrame()

        data = df.copy().sort_values('timestamp').reset_index(drop=True)

        try:
            # 1. Базові індикатори
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
                data['BB_WIDTH'] = (bb.iloc[:, 0] - bb.iloc[:, 2]) / (bb.iloc[:, 1] + 1e-9)
                bb_range = np.where((bb.iloc[:, 0] - bb.iloc[:, 2]) == 0, 1e-9, (bb.iloc[:, 0] - bb.iloc[:, 2]))
                data['BB_POS'] = (data['close'] - bb.iloc[:, 2]) / bb_range
            else:
                data[['BB_WIDTH', 'BB_POS']] = [0.0, 0.5]

            # 2. Розрахунок відсутніх у вас індикаторів (Генерація Фіч)
            atr = ta.atr(data['high'], data['low'], data['close'], length=14)
            data['ATR_PCT'] = atr / data['close'] if atr is not None else 0.0

            adx = ta.adx(data['high'], data['low'], data['close'])
            data['ADX'] = adx.iloc[:, 0] / 100.0 if adx is not None else 0.0

            obv = ta.obv(data['close'], data['volume'])
            if obv is not None:
                data['OBV_SLOPE'] = obv.diff(periods=5) / (obv.rolling(window=20).std() + 1e-9)
            else:
                data['OBV_SLOPE'] = 0.0

            # 3. Ковзні середні та дистанції
            ema20 = ta.ema(data['close'], length=20)
            ema50 = ta.ema(data['close'], length=50)
            data['EMA_DIST_20'] = (data['close'] - ema20) / (ema20 + 1e-9) if ema20 is not None else 0.0
            data['EMA_DIST_50'] = (data['close'] - ema50) / (ema50 + 1e-9) if ema50 is not None else 0.0

            # 4. Ринковий тиск та об'ємні фічі
            data['LOG_RET'] = np.log(data['close'] / data['close'].shift(1))
            vol_ma = data['volume'].rolling(window=20).mean()
            data['VOL_SPIKE'] = data['volume'] / (vol_ma + 1e-9)
            
            price_spread = data['high'] - data['low']
            data['BUY_PRESSURE'] = (data['close'] - data['low']) / (price_spread + 1e-9)

            # 5. Генерація лагів (Lag Features)
            for feature in self.lag_features:
                for lag in self.lags:
                    data[f"{feature}_lag_{lag}"] = data[feature].shift(lag)

            # Очищення нескінченних значень та перевірка фінального набору колонок
            data.replace([np.inf, -np.inf], np.nan, inplace=True)
            
            missing_cols = [col for col in self.feature_cols if col not in data.columns]
            if missing_cols:
                logger.error(f"❌ Помилка Data Pipeline: відсутні розраховані колонки: {missing_cols}")
                return pd.DataFrame()

            return data.dropna(subset=self.feature_cols)

        except Exception as e:
            logger.error(f"❌ Критична помилка під час Feature Engineering: {e}", exc_info=True)
            return pd.DataFrame()

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
            logger.error(f"❌ Критична помилка інференсу моделі: {e}", exc_info=True)
            return SignalAction.HOLD, 0.0