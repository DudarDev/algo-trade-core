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

def test_predictor_empty_features(tmp_path):
    mock_settings = MagicMock()
    mock_settings.MODEL_PATH = "data_storage/models/global_rf_v4.pkl"
    mock_settings.CONFIDENCE_THRESHOLD = 0.55

    ai = GlobalTradingAI(mock_settings)
    signal, proba = ai.predict(pd.DataFrame())
    assert signal == "HOLD"
    assert proba == 0.0
