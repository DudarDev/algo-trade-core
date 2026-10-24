import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock
from pathlib import Path

from src.infrastructure.ai.predictor import GlobalTradingAI
from src.infrastructure.ai.feature_engineer import get_feature_columns


def test_predictor_initialization_and_prediction(tmp_path):
    mock_settings = MagicMock()
    mock_settings.MODEL_PATH = "data_storage/models/global_rf_v4.pkl"
    mock_settings.LIGHTGBM_MODEL_PATH = "data_storage/models/global_lgbm_v1.pkl"
    mock_settings.ENABLE_QUANT_DUAL_ENSEMBLE = True
    mock_settings.CONFIDENCE_THRESHOLD = 0.55

    ai = GlobalTradingAI(mock_settings)
    assert ai.model is not None
    assert isinstance(ai.feature_cols, list)

    # Synthetic features dataframe
    feature_cols = get_feature_columns()
    df_feat = pd.DataFrame([
        {col: 0.2 for col in feature_cols}
    ])

    signal, proba = ai.predict(df_feat)
    assert signal in ["BUY", "HOLD"]
    assert 0.0 <= proba <= 1.0


def test_predictor_dual_ensemble_blending():
    mock_settings = MagicMock()
    mock_settings.MODEL_PATH = "data_storage/models/global_rf_v4.pkl"
    mock_settings.LIGHTGBM_MODEL_PATH = "data_storage/models/global_lgbm_v1.pkl"
    mock_settings.ENABLE_QUANT_DUAL_ENSEMBLE = True
    mock_settings.CONFIDENCE_THRESHOLD = 0.50

    ai = GlobalTradingAI(mock_settings)
    # Mock both models predict_proba
    ai.model = MagicMock()
    ai.model.predict_proba.return_value = np.array([[0.20, 0.80]])  # RF proba = 0.80

    ai.lgbm_model = MagicMock()
    ai.lgbm_model.predict_proba.return_value = np.array([[0.40, 0.60]])  # LGBM proba = 0.60

    feature_cols = get_feature_columns()
    df_feat = pd.DataFrame([{col: 0.1 for col in feature_cols}])

    signal, proba, details = ai.predict_with_details(df_feat)

    # Expected: 0.55 * 0.80 + 0.45 * 0.60 = 0.44 + 0.27 = 0.71
    assert round(proba, 2) == 0.71
    assert details["is_ensemble"] is True
    assert details["rf_proba"] == 0.80
    assert details["lgbm_proba"] == 0.60
    assert signal.value == "BUY"


def test_predictor_fallback_when_ensemble_disabled():
    mock_settings = MagicMock()
    mock_settings.MODEL_PATH = "data_storage/models/global_rf_v4.pkl"
    mock_settings.LIGHTGBM_MODEL_PATH = "data_storage/models/global_lgbm_v1.pkl"
    mock_settings.ENABLE_QUANT_DUAL_ENSEMBLE = False
    mock_settings.CONFIDENCE_THRESHOLD = 0.50

    ai = GlobalTradingAI(mock_settings)
    ai.model = MagicMock()
    ai.model.predict_proba.return_value = np.array([[0.30, 0.70]])

    feature_cols = get_feature_columns()
    df_feat = pd.DataFrame([{col: 0.1 for col in feature_cols}])

    signal, proba, details = ai.predict_with_details(df_feat)

    assert round(proba, 2) == 0.70
    assert details["is_ensemble"] is False
    assert details["rf_proba"] == 0.70


def test_predictor_empty_features(tmp_path):
    mock_settings = MagicMock()
    mock_settings.MODEL_PATH = "data_storage/models/global_rf_v4.pkl"
    mock_settings.CONFIDENCE_THRESHOLD = 0.55

    ai = GlobalTradingAI(mock_settings)
    signal, proba = ai.predict(pd.DataFrame())
    assert signal == "HOLD"
    assert proba == 0.0
