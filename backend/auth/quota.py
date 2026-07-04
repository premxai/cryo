"""Per-key rate limiting (Redis fixed window) + monthly quota + usage ledger.

Redis is authoritative for the hot path; a BackgroundTask upserts durable
per-endpoint counts into PostgreSQL (usage_ledger) for /v1/usage and future billing.
Mirrors the db.py pattern: Redis missing is a warning in dev, fatal in production.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import BackgroundTasks, Depends, Response
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.auth.keys import require_api_key
from backend.auth.models import ApiKey, UsageLedger
from backend.config import settings
from backend.errors import APIError

logger = structlog.get_logger()

_redis = None  # lazy module-level client, initialized at app startup


async def init_redis() -> None:
    """Connect to Redis at startup. Dev-optional, prod-fatal (same pattern as db.py)."""
    global _redis
    try:
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        await _redis.ping()
        logger.info("cryo.redis.connected", url=settings.redis_url.split("@")[-1])
    except Exception as exc:
        _redis = None
        if settings.is_production:
            raise
        logger.warning(
            "cryo.redis.unavailable",
            error=str(exc),
            hint="Start Redis: docker-compose up -d redis (rate limits disabled)",
        )


async def close_redis() -> None:
    """Close the Redis client at shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis():
    """Return the shared Redis client, or None when unavailable (dev)."""
    return _redis


def current_month() -> str:
    """Return the current UTC month as 'YYYY-MM' — the quota window key."""
    return datetime.now(UTC).strftime("%Y-%m")


async def _check_rate_limit(key: ApiKey, response: Response) -> None:
    """Fixed 60s window: INCR rl:{key_id}:{minute}. Raises 429 when over the per-key limit."""
    window = int(time.time()) // 60
    redis_key = f"rl:{key.id}:{window}"
    count = await _redis.incr(redis_key)
    if count == 1:
        await _redis.expire(redis_key, 120)
    limit = key.rate_limit_per_minute
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
    if count > limit:
        retry_after = 60 - int(time.time()) % 60
        raise APIError(
            429,
            "rate_limited",
            f"Rate limit of {limit} requests/minute exceeded",
            headers={"Retry-After": str(retry_after)},
        )


async def _check_monthly_quota(key: ApiKey, response: Response, units: int) -> None:
    """INCRBY quota:{key_id}:{month}. DECR back and raise 429 when over quota."""
    redis_key = f"quota:{key.id}:{current_month()}"
    used = await _redis.incrby(redis_key, units)
    if used == units:
        await _redis.expire(redis_key, 40 * 86400)  # outlives the month, then self-cleans
    quota = key.monthly_quota
    response.headers["X-Quota-Limit"] = str(quota)
    response.headers["X-Quota-Remaining"] = str(max(0, quota - used))
    if used > quota:
        await _redis.decrby(redis_key, units)
        raise APIError(
            429,
            "quota_exceeded",
            f"Monthly quota of {quota} requests exhausted — resets on the 1st (UTC)",
        )


async def record_usage(api_key_id, endpoint: str, units: int = 1) -> None:
    """Upsert request counts into the durable usage_ledger (runs as a BackgroundTask)."""
    from backend.db import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            stmt = pg_insert(UsageLedger).values(
                api_key_id=api_key_id,
                month=current_month(),
                endpoint=endpoint,
                request_count=units,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_usage_key_month_endpoint",
                set_={"request_count": UsageLedger.request_count + units},
            )
            await session.execute(stmt)
            await session.commit()
    except Exception as exc:
        logger.warning("cryo.usage.ledger_write_failed", endpoint=endpoint, error=str(exc))


async def consume_quota(
    key: ApiKey,
    response: Response,
    background: BackgroundTasks,
    endpoint: str,
    units: int = 1,
) -> None:
    """Enforce rate limit + monthly quota for `units`, then schedule the ledger write.

    No-ops (with a debug log) when Redis is unavailable in development.
    """
    if _redis is None:
        logger.debug("cryo.quota.skipped_no_redis", endpoint=endpoint)
        return
    await _check_rate_limit(key, response)
    await _check_monthly_quota(key, response, units)
    background.add_task(record_usage, key.id, endpoint, units)


def enforce_limits(endpoint: str) -> Callable:
    """Dependency factory: authenticated key + rate limit + 1 quota unit for `endpoint`."""

    async def dependency(
        response: Response,
        background: BackgroundTasks,
        key: Annotated[ApiKey, Depends(require_api_key)],
    ) -> ApiKey:
        await consume_quota(key, response, background, endpoint)
        return key

    return dependency
