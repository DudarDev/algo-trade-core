import pytest
import time
from src.engine.infrastructure.cache_manager import CacheManager, InMemoryCache


def test_in_memory_cache_crud():
    cache = InMemoryCache()
    assert cache.get("nonexistent") is None
    assert cache.get("nonexistent", "default") == "default"

    cache.set("btc_price", 95200.5, ttl=10)
    assert cache.get("btc_price") == 95200.5

    assert cache.delete("btc_price") is True
    assert cache.get("btc_price") is None
    assert cache.delete("btc_price") is False


def test_in_memory_cache_ttl_expiration():
    cache = InMemoryCache()
    cache.set("temp_signal", {"action": "BUY", "symbol": "BTC/USDT"}, ttl=1)
    assert cache.get("temp_signal")["action"] == "BUY"

    # Wait for TTL to expire
    time.sleep(1.1)
    assert cache.get("temp_signal") is None


def test_cache_manager_json_serialization():
    # Forced in-memory by giving unreachable port
    cm = CacheManager(redis_url="redis://127.0.0.1:54321/0", socket_timeout=0.1)
    assert cm.is_redis_available is False

    payload = {"symbol": "ETH/USDT", "score": 0.88, "tags": ["breakout", "momentum"]}
    cm.set("model:eth", payload, ttl=60)

    cached = cm.get("model:eth")
    assert isinstance(cached, dict)
    assert cached["symbol"] == "ETH/USDT"
    assert cached["score"] == 0.88
    assert "breakout" in cached["tags"]


def test_cache_manager_get_or_set():
    cm = CacheManager(redis_url="redis://127.0.0.1:54321/0", socket_timeout=0.1)
    call_count = 0

    def compute_expensive_metric():
        nonlocal call_count
        call_count += 1
        return {"fng_index": 72, "sentiment": "Greed"}

    val1 = cm.get_or_set("metric:fng", compute_expensive_metric, ttl=5)
    assert val1["fng_index"] == 72
    assert call_count == 1

    # Second call must come from cache without invoking compute
    val2 = cm.get_or_set("metric:fng", compute_expensive_metric, ttl=5)
    assert val2["fng_index"] == 72
    assert call_count == 1


def test_cache_manager_pub_sub_fallback():
    cm = CacheManager(redis_url="redis://127.0.0.1:54321/0", socket_timeout=0.1)
    received = []

    def subscriber(msg):
        received.append(msg)

    cm._subscribers["telemetry"] = [subscriber]
    count = cm.publish("telemetry", {"event": "ORDER_FILLED", "price": 95000})

    assert count == 1
    assert len(received) == 1
    assert received[0]["event"] == "ORDER_FILLED"


def test_cache_manager_stats():
    cm = CacheManager(redis_url="redis://127.0.0.1:54321/0", socket_timeout=0.1)
    cm.set("k1", "v1")
    cm.set("k2", "v2")

    stats = cm.get_stats()
    assert stats["backend"] == "in_memory"
    assert stats["memory_keys_count"] == 2
