import pytest
from unittest.mock import AsyncMock, MagicMock
from src.engine.application.arbitrage import ArbitrageEngine
from src.shared.config import Settings
from src.engine.domain.models import ArbitrageOpportunity


@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=Settings)
    settings.ARBITRAGE_FEE_PCT = 0.001  # 0.1% per trade -> 0.20% roundtrip
    settings.ARBITRAGE_MIN_SPREAD_PCT = 0.5  # 0.5% net spread threshold
    settings.ARBITRAGE_SCAN_INTERVAL_SEC = 4.0
    settings.ARBITRAGE_ENABLED = True
    settings.REDIS_URL = "redis://127.0.0.1:6379/0"
    return settings


@pytest.fixture
def mock_exchanges():
    binance = MagicMock()
    binance.exchange = MagicMock()
    bybit = MagicMock()
    bybit.exchange = MagicMock()
    return {"binance": binance, "bybit": bybit}


@pytest.mark.asyncio
async def test_find_opportunity_detected(mock_settings, mock_exchanges, tmp_path):
    # Binance ask: 100.0, Bybit bid: 101.0 -> Gross spread = 1.0%, Net = 0.8% (> 0.5%)
    mock_exchanges["binance"].exchange.fetch_ticker = AsyncMock(return_value={"bid": 99.8, "ask": 100.0, "last": 99.9})
    mock_exchanges["bybit"].exchange.fetch_ticker = AsyncMock(return_value={"bid": 101.0, "ask": 101.2, "last": 101.1})

    engine = ArbitrageEngine(settings=mock_settings, exchanges=mock_exchanges, data_dir=str(tmp_path))
    opp = await engine.find_opportunity("BTC/USDT")

    assert opp is not None
    assert opp.symbol == "BTC/USDT"
    assert opp.buy_exchange == "binance"
    assert opp.buy_price == 100.0
    assert opp.sell_exchange == "bybit"
    assert opp.sell_price == 101.0
    assert abs(opp.gross_spread_pct - 1.0) < 0.01
    assert abs(opp.net_spread_pct - 0.8) < 0.01


@pytest.mark.asyncio
async def test_find_opportunity_below_threshold(mock_settings, mock_exchanges, tmp_path):
    # Binance ask: 100.0, Bybit bid: 100.2 -> Gross spread = 0.2%, Net = 0.0% (< 0.5%)
    mock_exchanges["binance"].exchange.fetch_ticker = AsyncMock(return_value={"bid": 99.9, "ask": 100.0, "last": 99.95})
    mock_exchanges["bybit"].exchange.fetch_ticker = AsyncMock(return_value={"bid": 100.2, "ask": 100.3, "last": 100.25})

    engine = ArbitrageEngine(settings=mock_settings, exchanges=mock_exchanges, data_dir=str(tmp_path))
    opp = await engine.find_opportunity("BTC/USDT")

    assert opp is None


@pytest.mark.asyncio
async def test_scan_radar_multi_symbols(mock_settings, mock_exchanges, tmp_path):
    # BTC: normal spread (+0.1% gross)
    # ETH: arbitrage window (+1.2% gross -> +1.0% net)
    async def fake_fetch_binance(symbol):
        if symbol == "BTC/USDT":
            return {"bid": 70000.0, "ask": 70010.0}
        return {"bid": 3000.0, "ask": 3000.0}

    async def fake_fetch_bybit(symbol):
        if symbol == "BTC/USDT":
            return {"bid": 70015.0, "ask": 70025.0}
        return {"bid": 3036.0, "ask": 3040.0}  # 3036 vs 3000 -> +1.2% gross

    mock_exchanges["binance"].exchange.fetch_ticker = AsyncMock(side_effect=fake_fetch_binance)
    mock_exchanges["bybit"].exchange.fetch_ticker = AsyncMock(side_effect=fake_fetch_bybit)

    engine = ArbitrageEngine(settings=mock_settings, exchanges=mock_exchanges, data_dir=str(tmp_path))
    radar_data = await engine.scan_radar(["BTC/USDT", "ETH/USDT"])

    assert radar_data["status"] == "active"
    assert radar_data["pairs_scanned"] == 2
    assert radar_data["active_opportunities_count"] == 1
    assert len(radar_data["opportunities"]) == 1
    assert radar_data["opportunities"][0]["symbol"] == "ETH/USDT"
    assert radar_data["opportunities"][0]["route"] == "Binance ➔ Bybit"
    assert (tmp_path / "arbitrage_radar.json").exists()
