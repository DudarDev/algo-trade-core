import pytest
from src.engine.application.gemini_sentinel import GeminiSentinel

class DummySettings:
    GEMINI_API_KEY = None

@pytest.mark.asyncio
async def test_gemini_sentinel_local_fallback_ua():
    sentinel = GeminiSentinel(settings=DummySettings())
    context = {
        "balance": 1000.0,
        "total_pnl": 15.5,
        "win_rate": 60.0,
        "total_trades": 50,
        "btc_pulse": "HEALTHY",
        "active_positions": []
    }
    res = await sentinel.ask_copilot("Який статус системи?", context=context, lang="ua")
    assert res["status"] == "success"
    assert "Огляд Квантового Станції" in res["reply"]
    assert "1000.00" in res["reply"]

@pytest.mark.asyncio
async def test_gemini_sentinel_local_fallback_en():
    sentinel = GeminiSentinel(settings=DummySettings())
    context = {
        "balance": 1000.0,
        "total_pnl": 15.5,
        "win_rate": 60.0,
        "total_trades": 50,
        "btc_pulse": "HEALTHY",
        "active_positions": []
    }
    res = await sentinel.ask_copilot("What is the btc trend?", context=context, lang="en")
    assert res["status"] == "success"
    assert "Macro Market Intel" in res["reply"]
