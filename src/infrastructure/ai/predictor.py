import logging
from pathlib import Path
from typing import Tuple, Optional, Protocol

import joblib
import numpy as np
import pandas as pd

from src.engine.domain.models import SignalAction
from src.shared.config import Settings
# Імпортуємо наш єдиний механізм фіч!
from src.infrastructure.ai.feature_engineer import calculate_features, get_feature_columns

logger = logging.getLogger(__name__)

class MLModelProtocol(Protocol):
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        ...

class GlobalTradingAI:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_path = Path(self.settings.MODEL_PATH)
        self.feature_cols = get_feature_columns()
        self.model: Optional[MLModelProtocol] = self._load_model()

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

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Делегуємо розрахунок в єдиний модуль."""
        required_input_cols = {'high', 'low', 'close', 'volume', 'timestamp'}
        if not required_input_cols.issubset(df.columns):
            logger.error(f"❌ Вхідний DataFrame не містить базових колонок")
            return pd.DataFrame()
            
        return calculate_features(df)

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