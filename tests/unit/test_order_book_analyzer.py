import pytest
from unittest.mock import AsyncMock, MagicMock

from src.engine.infrastructure.order_book_analyzer import OrderBookAnalyzer


@pytest.fixture
def mock_exchange_manager():
    mgr = MagicMock()
    mgr.public_exchange = MagicMock()
    return mgr


@pytest.mark.asyncio
async def test_order_book_strong_bid_support(mock_exchange_manager):
    """Тест виявлення сильної підтримки покупців (Bid/Ask > 1.5x)."""
    # 20 рівнів bids із великим об'ємом, asks із малим об'ємом
    bids = [[100.0 - (i * 0.1), 50.0] for i in range(20)] # total 1000
    asks = [[100.1 + (i * 0.1), 10.0] for i in range(20)] # total 200
    
    mock_exchange_manager.public_exchange.fetch_order_book = AsyncMock(return_value={
        "bids": bids,
        "asks": asks
    })

    analyzer = OrderBookAnalyzer(exchange_manager=mock_exchange_manager)
    res = await analyzer.analyze_order_book("BTC/USDT")

    assert res["status"] == "STRONG_BID_SUPPORT"
    assert res["imbalance_ratio"] >= 1.5
    assert res["score_adjustment"] == 0.10
    assert res["ask_wall_detected"] is False


@pytest.mark.asyncio
async def test_order_book_heavy_ask_wall_resistance(mock_exchange_manager):
    """Тест виявлення стіни на продаж (Ask Wall), яка блокує ріст ціни."""
    bids = [[100.0 - (i * 0.1), 10.0] for i in range(20)] # total 200
    # На рівні 100.2 стоїть масивна стіна 200 монет (35% від 580)
    asks = [[100.1, 10.0], [100.2, 200.0]] + [[100.3 + (i * 0.1), 20.0] for i in range(18)]

    mock_exchange_manager.public_exchange.fetch_order_book = AsyncMock(return_value={
        "bids": bids,
        "asks": asks
    })

    analyzer = OrderBookAnalyzer(exchange_manager=mock_exchange_manager)
    res = await analyzer.analyze_order_book("ETH/USDT")

    assert res["status"] == "HEAVY_ASK_RESISTANCE"
    assert res["score_adjustment"] == -0.15
    assert res["ask_wall_detected"] is True


@pytest.mark.asyncio
async def test_funding_rate_sentiment():
    """Тест аналізу фандингу: перегрітий ринок vs шорт-сквіз."""
    analyzer = OrderBookAnalyzer()
    
    # 1. Нейтральний/збалансований
    res_normal = await analyzer.get_funding_sentiment("SOL/USDT")
    assert res_normal["sentiment"] == "HEALTHY_BALANCED"
    assert res_normal["is_safe"] is True

    # 2. Перегрітий лонгами (> 0.05%)
    analyzer._funding_cache["SOL/USDT"] = (0.0008, 9999999999.0)
    res_hot = await analyzer.get_funding_sentiment("SOL/USDT")
    assert res_hot["sentiment"] == "OVERHEATED_LONGS"
    assert res_hot["is_safe"] is False
    assert res_hot["score_adjustment"] == -0.15

    # 3. Шорт-сквіз (< -0.01%)
    analyzer._funding_cache["SOL/USDT"] = (-0.0003, 9999999999.0)
    res_squeeze = await analyzer.get_funding_sentiment("SOL/USDT")
    assert res_squeeze["sentiment"] == "SHORT_SQUEEZE_PRIME"
    assert res_squeeze["score_adjustment"] == 0.10
