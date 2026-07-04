"""Unit tests for rate limiting and monthly quota enforcement (mocked Redis)."""

import re
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, Response

from backend.auth import quota
from backend.errors import APIError


class FakeKey:
    """Minimal ApiKey stand-in."""

    def __init__(self, rate: int = 60, monthly: int = 1000) -> None:
        self.id = uuid.uuid4()
        self.rate_limit_per_minute = rate
        self.monthly_quota = monthly


@pytest.fixture
def redis_mock(monkeypatch):
    """Install an AsyncMock in place of the module-level Redis client."""
    mock = AsyncMock()
    monkeypatch.setattr(quota, "_redis", mock)
    return mock


def test_current_month_format():
    """Month key looks like YYYY-MM."""
    assert re.fullmatch(r"\d{4}-\d{2}", quota.current_month())


async def test_rate_limit_under_limit_sets_headers(redis_mock):
    """Under the limit: no raise, X-RateLimit headers present."""
    redis_mock.incr.return_value = 5
    response = Response()
    await quota._check_rate_limit(FakeKey(rate=60), response)
    assert response.headers["X-RateLimit-Limit"] == "60"
    assert response.headers["X-RateLimit-Remaining"] == "55"


async def test_rate_limit_exceeded_raises_429(redis_mock):
    """Over the limit: APIError 429 rate_limited with Retry-After."""
    redis_mock.incr.return_value = 61
    with pytest.raises(APIError) as exc:
        await quota._check_rate_limit(FakeKey(rate=60), Response())
    assert exc.value.status_code == 429
    assert exc.value.error_type == "rate_limited"
    assert "Retry-After" in exc.value.headers


async def test_quota_under_limit_sets_headers(redis_mock):
    """Under quota: no raise, X-Quota headers present."""
    redis_mock.incrby.return_value = 10
    response = Response()
    await quota._check_monthly_quota(FakeKey(monthly=1000), response, units=1)
    assert response.headers["X-Quota-Limit"] == "1000"
    assert response.headers["X-Quota-Remaining"] == "990"


async def test_quota_exceeded_rolls_back_and_raises(redis_mock):
    """Over quota: the increment is rolled back and 429 quota_exceeded raised."""
    redis_mock.incrby.return_value = 1001
    with pytest.raises(APIError) as exc:
        await quota._check_monthly_quota(FakeKey(monthly=1000), Response(), units=1)
    assert exc.value.status_code == 429
    assert exc.value.error_type == "quota_exceeded"
    redis_mock.decrby.assert_awaited_once()


async def test_consume_quota_noop_without_redis(monkeypatch):
    """When Redis is unavailable (dev), consume_quota allows the request through."""
    monkeypatch.setattr(quota, "_redis", None)
    await quota.consume_quota(FakeKey(), Response(), BackgroundTasks(), "search")
