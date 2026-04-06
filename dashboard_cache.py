"""
Redis cache-aside pattern for dashboard endpoints (Week 14).

Usage — as a dependency in a FastAPI route:

    @router.get("/zones/{zone_id}/summary")
    async def get_summary(
        zone_id: uuid.UUID,
        cache: DashboardCache = Depends(get_dashboard_cache),
        db: AsyncSession = Depends(get_db),
    ):
        cached = await cache.get(f"zone_summary:{zone_id}")
        if cached:
            return cached
        data = await build_summary(zone_id, db)
        await cache.set(f"zone_summary:{zone_id}", data, ttl=60)
        return data

TTL defaults:
  - Zone load summary:         60  seconds  (near real-time for Priya)
  - Sustainability scores:     300 seconds  (5 min — updated nightly)
  - Tariff schedule:           900 seconds  (15 min — rarely changes)
  - Usage breakdown:           120 seconds  (2 min — billing dashboard)
  - Demand forecasts:          300 seconds  (5 min — updated hourly)
"""
from __future__ import annotations

import json
import logging
from typing import Any

from shems.core.cache.redis_client import get_redis

logger = logging.getLogger(__name__)

# Default TTLs in seconds per cache key prefix
_DEFAULT_TTL = 120

TTL_MAP: dict[str, int] = {
    "zone_summary":        60,
    "zone_forecast":       300,
    "zone_alerts":         30,
    "sustainability":      300,
    "tariff_schedule":     900,
    "usage_breakdown":     120,
    "billing_account":     300,
}

_CACHE_PREFIX = "dashboard"


class DashboardCache:
    """Thin async wrapper over Redis for dashboard key-value caching."""

    async def get(self, key: str) -> Any | None:
        try:
            redis = await get_redis()
            raw = await redis.get(f"{_CACHE_PREFIX}:{key}")
            if raw:
                logger.debug("Cache HIT: %s", key)
                return json.loads(raw)
        except Exception as exc:
            logger.warning("Cache GET failed for %s: %s", key, exc)
        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            redis = await get_redis()
            prefix = key.split(":")[0]
            ttl = ttl or TTL_MAP.get(prefix, _DEFAULT_TTL)
            await redis.setex(
                f"{_CACHE_PREFIX}:{key}",
                ttl,
                json.dumps(value, default=str),
            )
            logger.debug("Cache SET: %s (ttl=%ds)", key, ttl)
        except Exception as exc:
            logger.warning("Cache SET failed for %s: %s", key, exc)

    async def invalidate(self, key: str) -> None:
        try:
            redis = await get_redis()
            await redis.delete(f"{_CACHE_PREFIX}:{key}")
            logger.debug("Cache DEL: %s", key)
        except Exception as exc:
            logger.warning("Cache DEL failed for %s: %s", key, exc)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching a wildcard pattern. Returns count deleted."""
        try:
            redis = await get_redis()
            keys = await redis.keys(f"{_CACHE_PREFIX}:{pattern}")
            if keys:
                await redis.delete(*keys)
                logger.debug("Cache DEL pattern=%s count=%d", pattern, len(keys))
                return len(keys)
        except Exception as exc:
            logger.warning("Cache DEL pattern failed %s: %s", pattern, exc)
        return 0


_cache_instance: DashboardCache | None = None


def get_dashboard_cache() -> DashboardCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = DashboardCache()
    return _cache_instance


def cached_response(key_template: str, ttl: int | None = None):
    """
    Decorator factory for FastAPI route handlers.
    key_template may reference route path parameters by name: "zone_summary:{zone_id}"

    Usage:
        @router.get("/zones/{zone_id}/summary")
        @cached_response("zone_summary:{zone_id}", ttl=60)
        async def get_summary(zone_id: uuid.UUID, db=Depends(get_db)):
            ...
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_dashboard_cache()
            # Resolve key template from kwargs
            try:
                key = key_template.format(**{k: str(v) for k, v in kwargs.items()})
            except KeyError:
                key = key_template

            cached = await cache.get(key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)

            # Only cache Pydantic models and dicts
            if hasattr(result, "model_dump"):
                await cache.set(key, result.model_dump(), ttl)
            elif isinstance(result, (dict, list)):
                await cache.set(key, result, ttl)

            return result

        return wrapper
    return decorator
