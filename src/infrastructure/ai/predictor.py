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
        model_path = Path(self.settings.MODEL_PATH)
        if not model_path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            if (project_root / model_path).exists():
                model_path = project_root / model_path
        self.model_path = model_path
        self.feature_cols = get_feature_columns()
        self._last_mtime = 0.0
        self.model: Optional[MLModelProtocol] = self._load_model()

    def _load_model(self) -> Optional[MLModelProtocol]:
        if not self.model_path.exists():
            logger.critical(f"🚨 Модель не знайдено за шляхом: {self.model_path}")
            return None
        try:
            model = joblib.load(self.model_path)
            self._last_mtime = self.model_path.stat().st_mtime
            logger.info(f"✅ Модель успішно завантажена: {self.model_path.name}")
            return model
        except Exception as e:
            logger.critical(f"🚨 Помилка завантаження моделі: {e}", exc_info=True)
            return None

    def check_for_model_update(self) -> None:
        """Перевіряє, чи оновився файл моделі на диску, та перезавантажує його на льоту."""
        try:
            if self.model_path.exists():
                current_mtime = self.model_path.stat().st_mtime
                if current_mtime > self._last_mtime:
                    logger.info("🔄 [Model Hot-Reload] Виявлено нові ваги моделі на диску! Гаряче перезавантаження...")
                    self.model = self._load_model()
        except Exception as e:
            logger.warning(f"⚠️ Помилка перевірки оновлення моделі: {e}")

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Делегуємо розрахунок в єдиний модуль."""
        required_input_cols = {'high', 'low', 'close', 'volume', 'timestamp'}
        if not required_input_cols.issubset(df.columns):
            logger.error(f"❌ Вхідний DataFrame не містить базових колонок")
            return pd.DataFrame()
            
        return calculate_features(df)

    def predict(self, df: pd.DataFrame) -> Tuple[SignalAction, float]:
        self.check_for_model_update()
        if self.model is None:
            return SignalAction.HOLD, 0.0

        # Якщо датафрейм вже містить розраховані фічі, використовуємо його без повторного обчислення
        if set(self.feature_cols).issubset(df.columns):
            processed_df = df
        else:
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