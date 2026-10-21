import pytest
import numpy as np
import pandas as pd
from src.infrastructure.ai.feature_engineer import get_feature_columns, calculate_features

def create_sample_ohlcv(n=80):
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    highs = closes + np.random.rand(n) * 0.8
    lows = closes - np.random.rand(n) * 0.8
    opens = closes + np.random.randn(n) * 0.1
    volumes = np.random.rand(n) * 1000 + 100
    timestamps = [1700000000000 + i * 300000 for i in range(n)]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    })

def test_feature_columns_contract():
    cols = get_feature_columns()
    assert isinstance(cols, list)
    assert len(cols) == 29
    assert 'RSI' in cols
    assert 'ADX' in cols
    assert 'ATR_PCT' in cols
    assert 'MACD_HIST' in cols
    assert 'RSI_lag_1' in cols

def test_calculate_features_empty_or_short():
    assert calculate_features(pd.DataFrame()).empty
    assert calculate_features(None).empty
    
    # Less than 60 candles
    short_df = create_sample_ohlcv(30)
    assert calculate_features(short_df).empty

def test_calculate_features_success():
    df = create_sample_ohlcv(100)
    df_feat = calculate_features(df)
    assert not df_feat.empty
    
    # All expected feature columns must be present
    feature_cols = get_feature_columns()
    assert set(feature_cols).issubset(df_feat.columns)
    
    # Assert values are numeric and finite
    latest_row = df_feat[feature_cols].iloc[-1]
    assert not latest_row.isna().any()
    assert np.isfinite(latest_row.values).all()
