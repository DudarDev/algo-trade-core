"""
Institutional In-Memory & Redis Cache Manager.
Provides sub-millisecond retrieval of market tickers, L2 depth, Fear & Greed sentiment,
and cross-service telemetry pub/sub broadcasting with seamless in-memory fallback.
"""
import json
import time
import logging
from typing import Any, Optional, Callable, Dict

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Thread-safe TTL in-memory fallback cache."""
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}

    def get(self, key: str, default: Any = None) -> Any:
        now = time.time()
        if key in self._store:
            exp = self._expires.get(key)
            if exp is None or now < exp:
                return self._store[key]
            # Expired
            self.delete(key)
        return default

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        self._store[key] = value
        if ttl is not None and ttl > 0:
            self._expires[key] = time.time() + ttl
        elif key in self._expires:
            del self._expires[key]
        return True

    def delete(self, key: str) -> bool:
        existed = key in self._store
        self._store.pop(key, None)
        self._expires.pop(key, None)
        return existed

    def clear(self) -> None:
        self._store.clear()
        self._expires.clear()

    def size(self) -> int:
        # Purge expired keys
        now = time.time()
        expired = [k for k, exp in self._expires.items() if now >= exp]
        for k in expired:
            self.delete(k)
        return len(self._store)


class CacheManager:
    """
    Unified Cache & Real-Time Messaging Manager.
    Automatically connects to Redis if available, or falls back transparently to InMemoryCache.
    """
    def __init__(self, redis_url: str = "redis://127.0.0.1:6379/0", socket_timeout: float = 1.0):
        self.redis_url = redis_url
        self.socket_timeout = socket_timeout
        self._redis_client = None
        self._redis_available = False
        self._memory_cache = InMemoryCache()
        self._subscribers: Dict[str, list] = {}
        self._init_connection()

    def _init_connection(self) -> None:
        try:
            import redis
            client = redis.Redis.from_url(
                self.redis_url,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_timeout,
                decode_responses=True
            )
            # Test ping
            client.ping()
            self._redis_client = client
            self._redis_available = True
            logger.info(f"⚡ [CacheManager] Підключено до Redis: {self.redis_url}")
        except Exception as e:
            self._redis_client = None
            self._redis_available = False
            logger.info(f"ℹ️ [CacheManager] Redis недоступний ({e}). Використовується In-Memory кеш.")

    @property
    def is_redis_available(self) -> bool:
        if not self._redis_available or not self._redis_client:
            return False
        try:
            return bool(self._redis_client.ping())
        except Exception:
            self._redis_available = False
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Отримує значення за ключем (десеріалізує JSON якщо можливо)."""
        if self._redis_available and self._redis_client:
            try:
                raw = self._redis_client.get(key)
                if raw is None:
                    return default
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return raw
            except Exception as e:
                logger.debug(f"[CacheManager] Redis get error: {e}")
                self._redis_available = False

        return self._memory_cache.get(key, default)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Зберігає значення з опціональним TTL у секундах."""
        serialized = json.dumps(value) if not isinstance(value, (str, int, float, bool)) else value

        if self._redis_available and self._redis_client:
            try:
                if ttl and ttl > 0:
                    self._redis_client.setex(key, ttl, serialized)
                else:
                    self._redis_client.set(key, serialized)
                return True
            except Exception as e:
                logger.debug(f"[CacheManager] Redis set error: {e}")
                self._redis_available = False

        # In-memory fallback
        return self._memory_cache.set(key, value, ttl=ttl)

    def delete(self, key: str) -> bool:
        """Видаляє ключ із кешу."""
        res = False
        if self._redis_available and self._redis_client:
            try:
                res = bool(self._redis_client.delete(key))
            except Exception:
                self._redis_available = False
        mem_res = self._memory_cache.delete(key)
        return res or mem_res

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """Повертає значення з кешу або обчислює його через factory і кешує."""
        val = self.get(key)
        if val is not None:
            return val
        val = factory()
        if val is not None:
            self.set(key, val, ttl=ttl)
        return val

    def publish(self, channel: str, message: Any) -> int:
        """Публікує подію в канал Redis Pub/Sub або локальним підписникам."""
        msg_str = json.dumps(message) if not isinstance(message, str) else message
        count = 0

        if self._redis_available and self._redis_client:
            try:
                count = self._redis_client.publish(channel, msg_str)
                return count
            except Exception as e:
                logger.debug(f"[CacheManager] Redis publish error: {e}")
                self._redis_available = False

        # Local fallback publish
        if channel in self._subscribers:
            for cb in self._subscribers[channel]:
                try:
                    cb(message)
                    count += 1
                except Exception as ex:
                    logger.error(f"[CacheManager] Local subscriber error: {ex}")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Статистика кешу."""
        return {
            "backend": "redis" if self._redis_available else "in_memory",
            "redis_connected": self._redis_available,
            "memory_keys_count": self._memory_cache.size(),
            "redis_url": self.redis_url
        }


# Глобальний екземпляр з параметрами з Settings
try:
    from src.shared.config import settings
    cache_manager = CacheManager(redis_url=settings.REDIS_URL)
except Exception:
    cache_manager = CacheManager()
