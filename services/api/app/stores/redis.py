"""Redis store for caching and distributed locks.

Handles:
- Caching with TTL policies
- Distributed locks (prevent thundering herd)
- Atomic operations

TTL policies:
- Shopping responses: 1-6 hours
- Immersive results: 7-30 days
- Merchant URL by offerId: 7-30 days
- UI payload cache: 30-300 seconds
- Hydration locks: 30-120 seconds
- FX rates (OpenExchangeRates): ~1 hour
"""

import json
import logging
from typing import Any

import redis.asyncio as redis

from app.settings import get_settings

# TTL constants (in seconds)
TTL_SHOPPING_CACHE = 3600  # 1 hour
TTL_IMMERSIVE_CACHE = 604800  # 7 days
TTL_MERCHANT_URL = 604800  # 7 days
TTL_UI_PAYLOAD = 60  # 1 minute
TTL_HYDRATION_LOCK = 60  # 1 minute
TTL_FX_RATES = 3600  # 1 hour

# Key prefixes
PREFIX_SHOPPING = "shopping:"
PREFIX_IMMERSIVE = "immersive:"
PREFIX_MERCHANT_URL = "merchant_url:"
PREFIX_UI_PAYLOAD = "ui:"
PREFIX_LOCK = "lock:"
PREFIX_FX_RATES = "fx:rates:"

# Redis client (initialized on startup)
_redis: redis.Redis | None = None
logger = logging.getLogger("uvicorn.error")


async def init_redis() -> None:
    """Initialize Redis connection."""
    global _redis
    settings = get_settings()
    _redis = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    # Validate connectivity early (especially for `rediss://` in production).
    await _redis.ping()
    logger.info("Redis connected")


async def close_redis() -> None:
    """Close Redis connection."""
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


def _get_redis() -> redis.Redis:
    """Get Redis client instance."""
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis


# ============================================================
# Generic cache operations
# ============================================================


async def cache_get(key: str) -> str | None:
    """Get value from cache.

    Args:
        key: Cache key.

    Returns:
        Cached value or None if not found.
    """
    return await _get_redis().get(key)


async def cache_set(key: str, value: str, ttl: int) -> None:
    """Set value in cache with TTL.

    Args:
        key: Cache key.
        value: Value to cache.
        ttl: Time-to-live in seconds.
    """
    await _get_redis().setex(key, ttl, value)


async def cache_delete(key: str) -> None:
    """Delete value from cache.

    Args:
        key: Cache key.
    """
    await _get_redis().delete(key)


async def cache_get_json(key: str) -> dict[str, Any] | None:
    """Get JSON value from cache.

    Args:
        key: Cache key.

    Returns:
        Parsed JSON dict or None if not found.
    """
    value = await cache_get(key)
    if value:
        return json.loads(value)
    return None


async def cache_set_json(key: str, value: dict[str, Any], ttl: int) -> None:
    """Set JSON value in cache.

    Args:
        key: Cache key.
        value: Dict to cache as JSON.
        ttl: Time-to-live in seconds.
    """
    await cache_set(key, json.dumps(value), ttl)


# ============================================================
# Specialized cache operations
# ============================================================


async def get_merchant_url_cache(offer_id: str) -> str | None:
    """Get cached merchant URL for offer.

    Args:
        offer_id: Offer identifier.

    Returns:
        Merchant URL or None if not cached.
    """
    return await cache_get(f"{PREFIX_MERCHANT_URL}{offer_id}")


async def set_merchant_url_cache(offer_id: str, url: str) -> None:
    """Cache merchant URL for offer.

    Args:
        offer_id: Offer identifier.
        url: Merchant URL.
    """
    await cache_set(f"{PREFIX_MERCHANT_URL}{offer_id}", url, TTL_MERCHANT_URL)


async def get_immersive_cache(token: str) -> dict[str, Any] | None:
    """Get cached immersive product data.

    Args:
        token: Immersive product token.

    Returns:
        Cached data or None if not found.
    """
    return await cache_get_json(f"{PREFIX_IMMERSIVE}{token}")


async def set_immersive_cache(token: str, data: dict[str, Any]) -> None:
    """Cache immersive product data.

    Args:
        token: Immersive product token.
        data: Data to cache.
    """
    await cache_set_json(f"{PREFIX_IMMERSIVE}{token}", data, TTL_IMMERSIVE_CACHE)


# ============================================================
# FX rates cache (OpenExchangeRates)
# ============================================================


async def get_fx_rates_cache(base: str = "USD") -> dict[str, Any] | None:
    """Get cached FX rates payload for a base currency."""
    return await cache_get_json(f"{PREFIX_FX_RATES}{base.upper()}")


async def set_fx_rates_cache(base: str, payload: dict[str, Any]) -> None:
    """Cache FX rates payload for a base currency (TTL ~1 hour)."""
    await cache_set_json(f"{PREFIX_FX_RATES}{base.upper()}", payload, TTL_FX_RATES)


# ============================================================
# Distributed locks (prevent thundering herd)
# ============================================================


async def acquire_lock(key: str, ttl: int = TTL_HYDRATION_LOCK) -> bool:
    """Acquire a distributed lock.

    Args:
        key: Lock key (e.g., offer_id).
        ttl: Lock timeout in seconds.

    Returns:
        True if lock acquired, False if already locked.
    """
    lock_key = f"{PREFIX_LOCK}{key}"
    # SET NX (only if not exists) with TTL
    result = await _get_redis().set(lock_key, "1", nx=True, ex=ttl)
    return result is not None


async def release_lock(key: str) -> None:
    """Release a distributed lock.

    Args:
        key: Lock key.
    """
    await cache_delete(f"{PREFIX_LOCK}{key}")


async def is_locked(key: str) -> bool:
    """Check if a lock exists.

    Args:
        key: Lock key.

    Returns:
        True if locked, False otherwise.
    """
    result = await cache_get(f"{PREFIX_LOCK}{key}")
    return result is not None
