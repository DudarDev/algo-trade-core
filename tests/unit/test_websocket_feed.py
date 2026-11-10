import pytest
import time
from src.engine.infrastructure.websocket_feed import WebSocketFeed

def test_normalize_symbol():
    feed = WebSocketFeed()
    assert feed._normalize_symbol("BTCUSDT") == "BTC/USDT"
    assert feed._normalize_symbol("ETHUSDT") == "ETH/USDT"
    assert feed._normalize_symbol("SOL-USDT") == "SOL/USDT"
    assert feed._to_binance_stream_name("BTC/USDT") == "btcusdt@bookTicker"
    assert feed._to_bybit_symbol("BTC/USDT") == "BTCUSDT"

def test_get_bbo_fresh_and_expired():
    feed = WebSocketFeed()
    now = time.time()
    
    # Fresh tick
    feed.prices["binance"]["BTC/USDT"] = {
        "bid": 88000.0,
        "ask": 88001.0,
        "last": 88000.5,
        "timestamp": now
    }
    bbo = feed.get_bbo("BTC/USDT", "binance")
    assert bbo is not None
    assert bbo["bid"] == 88000.0
    assert bbo["ask"] == 88001.0
    assert feed.get_price("BTC/USDT", "binance") == 88000.5

    # Expired tick (> 4s old)
    feed.prices["binance"]["ETH/USDT"] = {
        "bid": 3000.0,
        "ask": 3001.0,
        "last": 3000.5,
        "timestamp": now - 10.0
    }
    assert feed.get_bbo("ETH/USDT", "binance") is None
    assert feed.get_price("ETH/USDT", "binance") is None

def test_get_stats():
    feed = WebSocketFeed()
    now = time.time()
    feed.prices["binance"]["BTC/USDT"] = {"bid": 88000, "ask": 88001, "timestamp": now}
    feed.prices["bybit"]["BTC/USDT"] = {"bid": 88000, "ask": 88001, "timestamp": now}
    feed.ticks_count = 42

    stats = feed.get_stats()
    assert stats["status"] == "online"
    assert stats["binance_active"] is True
    assert stats["bybit_active"] is True
    assert stats["total_ticks"] == 42
