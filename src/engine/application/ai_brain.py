import pandas as pd
import numpy as np
import pandas_ta as ta
import joblib
import logging
from typing import Tuple, Optional, List
from sklearn.calibration import CalibratedClassifierCV
from pathlib import Path

from src.shared.config import Settings

logger = logging.getLogger(__name__)

class GlobalTradingAI:
    """Модуль штучного інтелекту виключно для Інференсу (передбачення)."""

    def __init__(self, settings: Settings):
        self.settings = settings

        # 🛡️ БЕЗПЕЧНИЙ АБСОЛЮТНИЙ ШЛЯХ
        BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
        self.model_path = BASE_DIR / "data_storage" / "models" / "global_rf_v4.pkl"

        self.confidence_threshold = getattr(settings, 'CONFIDENCE_THRESHOLD', 0.7)

        self.model: Optional[CalibratedClassifierCV] = self._load_model()

        self.base_features: List[str] = [
            'RSI', 'MACD_HIST', 'BB_WIDTH', 'BB_POS', 'ATR_PCT',
            'ADX', 'STOCH_K', 'STOCH_D', 'OBV_SLOPE', 'EMA_DIST_20',
            'EMA_DIST_50', 'LOG_RET', 'VOL_SPIKE', 'BUY_PRESSURE'
        ]
        self.lag_features: List[str] = ['RSI', 'LOG_RET', 'MACD_HIST']
        self.lags: List[int] = [1, 2, 3]
        self.feature_cols: List[str] = self._get_feature_names()

    def _load_model(self) -> Optional[CalibratedClassifierCV]:
        try:
            if not self.model_path.exists():
                logger.critical(f"🚨 Модель не знайдено за шляхом: {self.model_path}")
                return None
            model = joblib.load(self.model_path)
            logger.info(f"✅ Модель успішно завантажена з {self.model_path}")
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
        """Генерує ознаки для передбачення. Вимагає наявності OHLCV колонок."""
        if df.empty or len(df) < 60:
            logger.warning("Недостатньо даних для генерації фіч (потрібно мінімум 60 свічок).")
            return pd.DataFrame()

        data = df.copy().sort_values('timestamp')

        # RSI (нормалізований 0..1)
        data.loc[:, 'RSI'] = ta.rsi(data['close'], length=14) / 100.0

        # MACD hist
        macd = ta.macd(data['close'])
        data.loc[:, 'MACD_HIST'] = macd.iloc[:, 1] if macd is not None else 0.0

        # Stochastic
        stoch = ta.stoch(data['high'], data['low'], data['close'])
        if stoch is not None:
            data.loc[:, 'STOCH_K'] = stoch.iloc[:, 0] / 100.0
            data.loc[:, 'STOCH_D'] = stoch.iloc[:, 1] / 100.0
        else:
            data.loc[:, ['STOCH_K', 'STOCH_D']] = 0.5

        # Bollinger Bands
        bb = ta.bbands(data['close'], length=20, std=2.0)
        if bb is not None:
            data.loc[:, 'BB_WIDTH'] = (bb.iloc[:, 0] - bb.iloc[:, 2]) / bb.iloc[:, 1]
            data.loc[:, 'BB_POS'] = (data['close'] - bb.iloc[:, 2]) / (bb.iloc[:, 0] - bb.iloc[:, 2] + 1e-9)
        else:
            data.loc[:, ['BB_WIDTH', 'BB_POS']] = [0.0, 0.5]

        # ATR%
        data.loc[:, 'ATR'] = ta.atr(data['high'], data['low'], data['close'], length=14)
        data.loc[:, 'ATR_PCT'] = data['ATR'] / (data['close'] + 1e-9)

        # ADX
        adx_df = ta.adx(data['high'], data['low'], data['close'], length=14)
        data.loc[:, 'ADX'] = adx_df.iloc[:, 0] / 100.0 if adx_df is not None else 0.0

        # EMA distances
        ema20 = ta.ema(data['close'], length=20)
        ema50 = ta.ema(data['close'], length=50)
        data.loc[:, 'EMA_DIST_20'] = (data['close'] - ema20) / (ema20 + 1e-9)
        data.loc[:, 'EMA_DIST_50'] = (data['close'] - ema50) / (ema50 + 1e-9)

        # OBV slope
        data.loc[:, 'OBV'] = ta.obv(data['close'], data['volume'])
        data.loc[:, 'OBV_SLOPE'] = data['OBV'].diff(3) / (data['OBV'].abs() + 1e-9)

        # Volume spike (2 std)
        vol_sma = data['volume'].rolling(window=20).mean()
        vol_std = data['volume'].rolling(window=20).std()
        data.loc[:, 'VOL_SPIKE'] = (data['volume'] > (vol_sma + 2 * vol_std)).astype(int)

        # Buy pressure
        data.loc[:, 'BUY_PRESSURE'] = (data['close'] - data['low']) / (data['high'] - data['low'] + 1e-9)

        # Log return
        data.loc[:, 'LOG_RET'] = np.log(data['close'] / data['close'].shift(1))

        # Лаги
        for feature in self.lag_features:
            for lag in self.lags:
                data.loc[:, f"{feature}_lag_{lag}"] = data[feature].shift(lag)

        # Очищення від нескінченностей
        data.replace([np.inf, -np.inf], np.nan, inplace=True)
        return data.dropna(subset=self.feature_cols)

    def predict(self, df: pd.DataFrame) -> Tuple[str, float]:
        """Повертає торговий сигнал та впевненість моделі (0.0 - 1.0)."""
        if self.model is None:
            logger.warning("Модель не завантажена → HOLD")
            return "HOLD", 0.0

        processed_df = self.prepare_features(df)
        if processed_df.empty:
            logger.warning("Підготовка фіч повернула пустий DataFrame → HOLD")
            return "HOLD", 0.0

        try:
            last_row = processed_df[self.feature_cols].iloc[[-1]]
            proba = float(self.model.predict_proba(last_row)[0][1])   # ймовірність класу BUY
            signal = "BUY" if proba >= self.confidence_threshold else "HOLD"

            # Додаткова діагностика – буде видно в логах
            logger.debug(
                f"🧠 AI предсказание: proba={proba:.4f}, threshold={self.confidence_threshold}, "
                f"signal={signal}, активных пар в данных={len(df)}"
            )

            return signal, proba

        except KeyError as e:
            logger.error(f"Відсутня необхідна колонка фіч під час передбачення: {e}")
            return "HOLD", 0.0
        except Exception as e:
            logger.error(f"Критична помилка передбачення: {e}", exc_info=True)
            return "HOLD", 0.0