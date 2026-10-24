import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.engine.infrastructure.market_sentiment import MarketSentimentAnalyzer


@pytest.mark.asyncio
async def test_sentiment_format_defensive():
    analyzer = MarketSentimentAnalyzer()
    res = analyzer._format_sentiment(15, "Extreme Fear")
    assert res["score"] == 15
    assert res["risk_mode"] == "DEFENSIVE"
    assert res["confidence_adjustment"] > 0
    assert res["size_multiplier"] < 1.0


@pytest.mark.asyncio
async def test_sentiment_format_greed():
    analyzer = MarketSentimentAnalyzer()
    res = analyzer._format_sentiment(68, "Greed")
    assert res["score"] == 68
    assert res["risk_mode"] == "MOMENTUM"
    assert res["confidence_adjustment"] < 0
    assert res["size_multiplier"] > 1.0


@pytest.mark.asyncio
async def test_sentiment_fetch_fallback():
    from src.engine.infrastructure.cache_manager import cache_manager
    cache_manager.delete("sentiment:fng")
    analyzer = MarketSentimentAnalyzer()
    with patch("aiohttp.ClientSession.get", side_effect=Exception("Network down")):
        data = await analyzer.get_market_sentiment()
        assert data["score"] == 50
        assert data["risk_mode"] == "BALANCED"
