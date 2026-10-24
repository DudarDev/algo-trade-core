import pytest
from unittest.mock import patch, AsyncMock
from src.engine.infrastructure.news_analyzer import NewsAnalyzer


def test_analyze_text_bullish_high_impact():
    analyzer = NewsAnalyzer()
    res = analyzer.analyze_text(
        title="Bitcoin Surges to Record High as SEC Approves Historic Spot ETF Inflows",
        description="Massive institutional buying drives BTC past resistance."
    )
    assert "BTC" in res["symbols"]
    assert res["sentiment"] == "BULLISH"
    assert res["impact"] == "HIGH"
    assert "каталізатор" in res["ai_takeaway"]


def test_analyze_text_bearish_high_impact():
    analyzer = NewsAnalyzer()
    res = analyzer.analyze_text(
        title="Solana DEX Suffers Massive Hack: Exploit Drains Millions in Liquidations",
        description="Vulnerability discovered in smart contract leads to emergency outage."
    )
    assert "SOL" in res["symbols"]
    assert res["sentiment"] == "BEARISH"
    assert res["impact"] == "HIGH"
    assert "Критичний ризик" in res["ai_takeaway"]


def test_analyze_text_neutral():
    analyzer = NewsAnalyzer()
    res = analyzer.analyze_text(
        title="Crypto market overview: Weekly discussion on blockchain trends",
        description="Analysts share general thoughts on industry developments."
    )
    assert res["sentiment"] == "NEUTRAL"
    assert res["impact"] == "LOW"


def test_blackout_filter_activation():
    analyzer = NewsAnalyzer()
    # Імітуємо критичну новину
    article = {
        "title": "Solana Protocol Exploited in $50M Hack",
        "source": "Cointelegraph",
        "symbols": ["SOL"],
        "sentiment": "BEARISH",
        "impact": "HIGH"
    }
    analyzer._cached_news = [article]
    analyzer._update_blackouts()

    is_blocked, reason = analyzer.is_symbol_blacklisted_by_news("SOL/USDT")
    assert is_blocked is True
    assert "Захисний блекаут" in reason

    # Інша пара не повинна блокуватися
    btc_blocked, _ = analyzer.is_symbol_blacklisted_by_news("BTC/USDT")
    assert btc_blocked is False

    blackouts = analyzer.get_active_blackouts()
    assert "SOL" in blackouts
    assert blackouts["SOL"]["minutes_remaining"] > 0


@pytest.mark.asyncio
async def test_fetch_latest_news_mock():
    analyzer = NewsAnalyzer()
    mock_rss = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item>
                <title>Ethereum Rally Continues with Strong ETF Inflows</title>
                <link>https://example.com/eth-rally</link>
                <pubDate>Fri, 24 Oct 2026 12:00:00 GMT</pubDate>
                <description>Ether breaks out above key moving averages.</description>
            </item>
        </channel>
    </rss>"""

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.read = AsyncMock(return_value=mock_rss)
        mock_get.return_value.__aenter__.return_value = mock_resp

        news = await analyzer.fetch_latest_news(force_refresh=True)
        assert len(news) >= 1
        assert "ETH" in news[0]["symbols"]
        assert news[0]["sentiment"] == "BULLISH"
