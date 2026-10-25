import pytest
from unittest.mock import patch, MagicMock
from src.engine.application.tasks import (
    task_refresh_news_feed,
    task_sync_market_sentiment,
    task_deep_backtest,
    task_retrain_ai_model,
    task_feedback_loop_retrain
)
from src.engine.infrastructure.cache_manager import cache_manager


def test_task_deep_backtest():
    res = task_deep_backtest(symbol="SOL/USDT", timeframe="15m", initial_balance=500.0)
    assert res["status"] == "success"
    assert res["metrics"]["symbol"] == "SOL/USDT"
    assert res["metrics"]["final_balance"] > 500.0

    task_id = res["task_id"]
    cached = cache_manager.get(f"backtest:{task_id}")
    assert cached is not None
    assert cached["profit_factor"] == 2.14


@patch("src.engine.infrastructure.market_sentiment.MarketSentimentAnalyzer.get_market_sentiment")
def test_task_sync_market_sentiment(mock_get_sentiment):
    mock_get_sentiment.return_value = {
        "score": 68,
        "value": 68,
        "classification": "Greed",
        "risk_posture": "ACCUMULATE"
    }

    res = task_sync_market_sentiment()
    assert res["status"] == "success"
    assert res["data"]["value"] == 68

    cached = cache_manager.get("sentiment:fng")
    assert cached is not None
    assert cached["classification"] == "Greed"


@patch("src.engine.infrastructure.news_analyzer.NewsAnalyzer.fetch_latest_news")
def test_task_refresh_news_feed(mock_fetch_news):
    mock_fetch_news.return_value = [
        {"title": "Bitcoin Hits All-Time High", "sentiment": "BULLISH", "impact": "HIGH"}
    ]

    res = task_refresh_news_feed()
    assert res["status"] == "success"
    assert res["count"] == 1

    cached = cache_manager.get("news:feed")
    assert cached is not None
    assert len(cached) == 1
    assert cached[0]["sentiment"] == "BULLISH"


@patch("src.ai_optimizer.weekly_retrain_service.WeeklyRetrainService.prepare_dataset")
@patch("src.ai_optimizer.weekly_retrain_service.WeeklyRetrainService.train_and_validate")
@patch("src.ai_optimizer.weekly_retrain_service.WeeklyRetrainService.deploy_model_safely")
def test_task_retrain_ai_model(mock_deploy, mock_train, mock_prepare):
    mock_prepare.return_value = MagicMock(empty=False)
    mock_train.return_value = (MagicMock(), {"roc_auc": 0.72, "accuracy": 0.68})
    mock_deploy.return_value = True

    res = task_retrain_ai_model(pairs=["BTC/USDT"], history_days=7)
    assert res["status"] == "deployed"
    assert res["metrics"]["roc_auc"] == 0.72

    cached = cache_manager.get("task:retrain:latest")
    assert cached is not None
    assert cached["status"] == "deployed"


@patch("src.infrastructure.ai.feedback_loop.FeedbackLoopService.retrain_with_feedback")
def test_task_feedback_loop_retrain(mock_retrain):
    from src.infrastructure.ai.feedback_loop import FeedbackRetrainResult
    mock_retrain.return_value = FeedbackRetrainResult(
        success=True,
        deployed=True,
        trained_samples=100,
        real_trades_used=25,
        metrics={"roc_auc": 0.88, "accuracy": 0.82},
        message="Model updated successfully!"
    )

    res = task_feedback_loop_retrain(min_real_trades=10)
    assert res["status"] == "deployed"
    assert res["deployed"] is True
    assert res["metrics"]["roc_auc"] == 0.88

    cached = cache_manager.get("task:feedback_retrain:latest")
    assert cached is not None
    assert cached["deployed"] is True
