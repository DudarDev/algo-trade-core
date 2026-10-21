import json
import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock
from pathlib import Path

from src.infrastructure.ai.feedback_loop import (
    FeedbackLoopService,
    ErrorPatternReport,
    FeedbackRetrainResult
)
from src.infrastructure.ai.feature_engineer import get_feature_columns

class MockTrade:
    def __init__(self, pnl, target_label, regime, confidence, features_dict):
        self.side = "SELL"
        self.pnl = pnl
        self.target_label = target_label
        self.regime = regime
        self.ai_confidence = confidence
        self.features_json = json.dumps(features_dict)

def test_error_pattern_diagnosis(tmp_path):
    feature_cols = get_feature_columns()
    service = FeedbackLoopService(data_dir=tmp_path)

    # 4 trades in CHOPPY_FLAT with low ADX (3 losses, 1 win)
    trades = [
        MockTrade(
            pnl=-10.0, target_label=0, regime="CHOPPY_FLAT", confidence=0.32,
            features_dict={col: 0.1 for col in feature_cols} | {"ADX": 0.18, "RSI": 0.45}
        ),
        MockTrade(
            pnl=-8.0, target_label=0, regime="CHOPPY_FLAT", confidence=0.31,
            features_dict={col: 0.1 for col in feature_cols} | {"ADX": 0.20, "RSI": 0.48}
        ),
        MockTrade(
            pnl=-12.0, target_label=0, regime="CHOPPY_FLAT", confidence=0.34,
            features_dict={col: 0.1 for col in feature_cols} | {"ADX": 0.22, "RSI": 0.50}
        ),
        MockTrade(
            pnl=15.0, target_label=1, regime="BULL_MARKET", confidence=0.65,
            features_dict={col: 0.1 for col in feature_cols} | {"ADX": 0.35, "RSI": 0.55}
        ),
    ]

    mock_session = MagicMock()
    mock_query = mock_session.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order = mock_filter.order_by.return_value
    mock_order.limit.return_value.all.return_value = trades

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__enter__.return_value = mock_session

    service.session_factory = mock_session_factory

    report = service.analyze_error_patterns(lookback_trades=10)
    assert isinstance(report, ErrorPatternReport)
    assert report.total_trades_analyzed == 4
    assert report.total_losses == 3
    assert report.total_wins == 1
    assert report.overall_win_rate_pct == 25.0

    # Verify regime breakdown
    chop_stats = report.regime_breakdown.get("CHOPPY_FLAT")
    assert chop_stats is not None
    assert chop_stats.losses == 3
    assert chop_stats.total == 3
    assert chop_stats.loss_rate_pct == 100.0

    # Verify automated findings
    assert any("CHOPPY_FLAT" in f for f in report.key_findings)

def test_extract_experience_dataset(tmp_path):
    feature_cols = get_feature_columns()
    service = FeedbackLoopService(data_dir=tmp_path)

    # Create 6 valid trades
    trades = []
    for i in range(6):
        target = 1 if i % 2 == 0 else 0
        pnl = 15.0 if target == 1 else -10.0
        trades.append(
            MockTrade(
                pnl=pnl,
                target_label=target,
                regime="BULL_MARKET",
                confidence=0.55,
                features_dict={col: 0.5 for col in feature_cols}
            )
        )

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = trades
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__enter__.return_value = mock_session
    service.session_factory = mock_session_factory

    dataset = service.extract_experience_dataset(min_trades=5)
    assert dataset is not None
    X_real, y_real, w_real = dataset

    assert len(X_real) == 6
    assert len(y_real) == 6
    assert len(w_real) == 6
    assert set(get_feature_columns()).issubset(X_real.columns)

def test_retrain_with_feedback_pipeline(tmp_path):
    feature_cols = get_feature_columns()
    service = FeedbackLoopService(
        data_dir=tmp_path,
        model_path=tmp_path / "models" / "global_rf_v4.pkl",
        min_auc_threshold=0.40
    )
    service.notifier = None

    # Generate 20 synthetic trades with diverse features to allow RF split
    trades = []
    np.random.seed(42)
    for i in range(25):
        target = 1 if (i % 3 != 0) else 0
        pnl = 10.0 if target == 1 else -10.0
        feat = {col: float(np.random.rand()) for col in feature_cols}
        trades.append(
            MockTrade(
                pnl=pnl,
                target_label=target,
                regime="BULL_MARKET" if target == 1 else "CHOPPY_FLAT",
                confidence=0.60 if target == 1 else 0.35,
                features_dict=feat
            )
        )

    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = trades
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__enter__.return_value = mock_session
    service.session_factory = mock_session_factory

    result = service.retrain_with_feedback(min_real_trades=5, force_deploy=True)
    assert isinstance(result, FeedbackRetrainResult)
    assert result.success is True
    assert result.deployed is True
    assert service.target_model_path.exists()
    assert result.metrics["real_trades"] == 25
