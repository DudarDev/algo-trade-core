import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ai_optimizer.weekly_retrain_service import WeeklyRetrainService
from src.infrastructure.ai.feature_engineer import get_feature_columns

def create_synthetic_data(n=300):
    timestamps = [1700000000000 + i * 300000 for i in range(n)]
    np.random.seed(42)
    # Згенеруємо синусоїду з трендом для гарантованої наявності обох класів (0 і 1)
    t = np.linspace(0, 10, n)
    closes = 100.0 + 5.0 * np.sin(t) + np.random.randn(n) * 0.2
    highs = closes + np.random.rand(n) * 0.8
    lows = closes - np.random.rand(n) * 0.8
    opens = closes + np.random.randn(n) * 0.1
    volumes = np.random.rand(n) * 1000 + 100

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    })

def test_prepare_dataset_and_training(tmp_path):
    service = WeeklyRetrainService(
        pairs=["BTC/USDT"],
        timeframe="5m",
        history_days=5,
        min_auc_threshold=0.45
    )
    service.notifier = None
    service.history_dir = tmp_path / "history"
    service.models_dir = tmp_path / "models"
    service.backups_dir = tmp_path / "models" / "backups"
    service.target_model_path = tmp_path / "models" / "test_model.pkl"
    service.history_log_path = tmp_path / "history.json"
    
    service.history_dir.mkdir(parents=True)
    service.models_dir.mkdir(parents=True)
    service.backups_dir.mkdir(parents=True)

    df_synth = create_synthetic_data(350)
    df_synth.to_csv(service.history_dir / "BTC_USDT_5m.csv", index=False)

    df_labeled = service.prepare_dataset()
    assert not df_labeled.empty
    assert "Target" in df_labeled.columns
    assert set(get_feature_columns()).issubset(df_labeled.columns)

    model, metrics = service.train_and_validate(df_labeled)
    assert model is not None
    assert "roc_auc" in metrics
    assert "accuracy" in metrics
    assert metrics["train_samples"] > 0

    success = service.deploy_model_safely(model, metrics)
    assert success is True
    assert service.target_model_path.exists()

def test_quality_gate_rejection(tmp_path):
    service = WeeklyRetrainService(min_auc_threshold=0.85)
    service.notifier = None
    service.target_model_path = tmp_path / "dummy_model.pkl"
    service.models_dir = tmp_path / "models"
    service.backups_dir = tmp_path / "models" / "backups"
    service.history_log_path = tmp_path / "history.json"
    
    # Спроба деплою моделі з низьким ROC-AUC (0.55 < 0.85)
    metrics = {"roc_auc": 0.55, "accuracy": 0.52, "train_samples": 100, "test_samples": 20}
    success = service.deploy_model_safely(MagicMock(), metrics)
    
    # Має бути відхилено Quality Gate
    assert success is False
    assert not service.target_model_path.exists()
