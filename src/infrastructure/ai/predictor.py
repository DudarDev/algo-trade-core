import logging
from pathlib import Path
from typing import Tuple, Optional, Protocol, Dict, Any

import joblib
import numpy as np
import pandas as pd

from src.engine.domain.models import SignalAction
from src.shared.config import Settings
from src.infrastructure.ai.feature_engineer import calculate_features, get_feature_columns

logger = logging.getLogger(__name__)


class MLModelProtocol(Protocol):
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        ...


class GlobalTradingAI:
    """
    Institutional Dual Quantitative Ensemble AI Engine.
    Combines Random Forest (Bagging noise filter) with LightGBM (Gradient-boosted trend-following)
    with probabilistic blending, dynamic hot-reload, and sub-millisecond inference.
    """
    def __init__(self, settings: Settings):
        self.settings = settings
        project_root = Path(__file__).resolve().parent.parent.parent.parent

        # 1. Random Forest Base Path
        model_path = Path(self.settings.MODEL_PATH)
        if not model_path.is_absolute() and (project_root / model_path).exists():
            model_path = project_root / model_path
        self.model_path = model_path

        # 2. LightGBM Ensemble Path
        lgbm_rel_path = getattr(self.settings, "LIGHTGBM_MODEL_PATH", "data_storage/models/global_lgbm_v1.pkl")
        lgbm_path = Path(lgbm_rel_path)
        if not lgbm_path.is_absolute() and (project_root / lgbm_path).exists():
            lgbm_path = project_root / lgbm_path
        self.lgbm_path = lgbm_path

        self.feature_cols = get_feature_columns()
        self._last_mtime = 0.0
        self._last_lgbm_mtime = 0.0

        # Load models
        self.model: Optional[MLModelProtocol] = self._load_model()
        self.lgbm_model: Optional[MLModelProtocol] = self._load_lgbm_model()

    def _load_model(self) -> Optional[MLModelProtocol]:
        if not self.model_path.exists():
            logger.critical(f"🚨 RF модель не знайдено за шляхом: {self.model_path}")
            return None
        try:
            model = joblib.load(self.model_path)
            self._last_mtime = self.model_path.stat().st_mtime
            logger.info(f"✅ RF модель успішно завантажена: {self.model_path.name}")
            return model
        except Exception as e:
            logger.critical(f"🚨 Помилка завантаження RF моделі: {e}", exc_info=True)
            return None

    def _load_lgbm_model(self) -> Optional[MLModelProtocol]:
        enable_ensemble = getattr(self.settings, "ENABLE_QUANT_DUAL_ENSEMBLE", True)
        if not enable_ensemble:
            return None
        if not self.lgbm_path.exists():
            logger.debug(f"ℹ️ LightGBM модель не знайдено: {self.lgbm_path}")
            return None
        try:
            lgbm = joblib.load(self.lgbm_path)
            self._last_lgbm_mtime = self.lgbm_path.stat().st_mtime
            logger.info(f"⚡ [Dual Ensemble] LightGBM модель успішно завантажена: {self.lgbm_path.name}")
            return lgbm
        except Exception as e:
            logger.warning(f"⚠️ Помилка завантаження LightGBM моделі: {e}")
            return None

    def check_for_model_update(self) -> None:
        """Перевіряє, чи оновились файли моделей на диску, та перезавантажує їх на льоту."""
        try:
            if self.model_path.exists():
                current_mtime = self.model_path.stat().st_mtime
                if current_mtime > self._last_mtime:
                    logger.info("🔄 [Model Hot-Reload] Виявлено нові ваги RF моделі! Перезавантаження...")
                    self.model = self._load_model()

            if self.lgbm_path.exists():
                current_lgbm_mtime = self.lgbm_path.stat().st_mtime
                if current_lgbm_mtime > self._last_lgbm_mtime:
                    logger.info("🔄 [Model Hot-Reload] Виявлено нові ваги LightGBM моделі! Перезавантаження...")
                    self.lgbm_model = self._load_lgbm_model()
        except Exception as e:
            logger.warning(f"⚠️ Помилка перевірки оновлення моделей: {e}")

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Делегуємо розрахунок в єдиний модуль."""
        required_input_cols = {'high', 'low', 'close', 'volume', 'timestamp'}
        if not required_input_cols.issubset(df.columns):
            logger.error(f"❌ Вхідний DataFrame не містить базових колонок")
            return pd.DataFrame()
        return calculate_features(df)

    def predict(self, df: pd.DataFrame) -> Tuple[SignalAction, float]:
        signal, proba, _ = self.predict_with_details(df)
        return signal, proba

    def predict_with_details(self, df: pd.DataFrame) -> Tuple[SignalAction, float, Dict[str, Any]]:
        self.check_for_model_update()
        if self.model is None:
            return SignalAction.HOLD, 0.0, {"error": "no_model"}

        # Якщо датафрейм вже містить розраховані фічі, використовуємо його без повторного обчислення
        if set(self.feature_cols).issubset(df.columns):
            processed_df = df
        else:
            processed_df = self.prepare_features(df)
            if processed_df.empty:
                return SignalAction.HOLD, 0.0, {"error": "empty_features"}

        try:
            last_row = processed_df[self.feature_cols].iloc[[-1]]
            rf_proba = float(self.model.predict_proba(last_row)[0][1])

            enable_ensemble = getattr(self.settings, "ENABLE_QUANT_DUAL_ENSEMBLE", True)
            if self.lgbm_model is not None and enable_ensemble:
                try:
                    lgbm_proba = float(self.lgbm_model.predict_proba(last_row)[0][1])
                    # Institutional Quantitative Blending:
                    # 55% Random Forest (Noise Reduction) + 45% LightGBM (Momentum Boosting)
                    blended_proba = 0.55 * rf_proba + 0.45 * lgbm_proba
                    proba = float(np.clip(blended_proba, 0.0, 1.0))
                    ensemble_active = True
                except Exception as ex:
                    logger.warning(f"⚠️ LightGBM inference error, fallback to RF: {ex}")
                    proba = rf_proba
                    lgbm_proba = 0.0
                    ensemble_active = False
            else:
                proba = rf_proba
                lgbm_proba = 0.0
                ensemble_active = False

            signal = SignalAction.BUY if proba >= self.settings.CONFIDENCE_THRESHOLD else SignalAction.HOLD
            logger.debug(
                f"🧠 AI Predict: proba={proba:.4f} (RF={rf_proba:.4f}, LGBM={lgbm_proba:.4f}), "
                f"signal={signal.value}"
            )

            details = {
                "rf_proba": round(rf_proba, 4),
                "lgbm_proba": round(lgbm_proba, 4) if ensemble_active else None,
                "blended_proba": round(proba, 4),
                "is_ensemble": ensemble_active,
                "signal": signal.value
            }

            return signal, proba, details

        except Exception as e:
            logger.error(f"❌ Критична помилка інференсу моделі: {e}", exc_info=True)
            return SignalAction.HOLD, 0.0, {"error": str(e)}
