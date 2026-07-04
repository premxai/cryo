"""Integration tests for the authenticated /v1 API (mocked auth + search)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from backend.models import SearchResponse, SearchResult


def _fake_key():
    """An ApiKey-shaped object without touching the DB."""
    key = MagicMock()
    key.id = uuid.uuid4()
    key.monthly_quota = 1000
    key.rate_limit_per_minute = 60
    key.revoked_at = None
    return key


def _fake_search_response() -> SearchResponse:
    return SearchResponse(
        query="test",
        results=[
            SearchResult(
                id="abc123",
                url="https://example.com/2019/how-to-bake-bread.html",
                text_preview="Baking <mark>bread</mark> at home is simple.",
                timestamp="20190101120000",
                year=2019,
                domain="example.com",
                content_type="blog",
                score=0.87,
            )
        ],
        total=1,
        search_time_ms=12,
    )


@pytest.fixture
async def authed_client(client):
    """Client with require_api_key overridden — bypasses the DB lookup."""
    from backend.auth.keys import require_api_key
    from backend.main import app

    app.dependency_overrides[require_api_key] = _fake_key
    yield client
    app.dependency_overrides.pop(require_api_key, None)


async def test_v1_search_requires_key(client):
    """Missing credentials → 401 with the structured error envelope."""
    resp = await client.post("/v1/search", json={"query": "old web"})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["type"] == "missing_api_key"
    assert "request_id" in body["error"]


async def test_v1_search_returns_results(authed_client):
    """Valid key → 200 with Exa-shaped results, no highlight markup."""
    with patch("backend.api.v1.keyword_search", return_value=_fake_search_response()):
        resp = await authed_client.post(
            "/v1/search",
            json={"query": "bread", "num_results": 5},
            headers={"authorization": "Bearer cryo_sk_test"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    result = body["results"][0]
    assert result["url"] == "https://example.com/2019/how-to-bake-bread.html"
    assert "<mark>" not in result["text"]
    assert result["title"] == "How To Bake Bread"
    assert result["published_year"] == 2019
    assert result["score"] == 0.87
    assert body["request_id"]


async def test_v1_search_validates_body(authed_client):
    """Empty query → 422 validation error."""
    resp = await authed_client.post("/v1/search", json={"query": "   "})
    assert resp.status_code == 422


async def test_v1_search_num_results_capped(authed_client):
    """num_results above 50 → 422."""
    resp = await authed_client.post("/v1/search", json={"query": "x", "num_results": 100})
    assert resp.status_code == 422


async def test_v1_usage_shape(authed_client):
    """Usage endpoint returns quota arithmetic from the ledger."""
    from unittest.mock import AsyncMock

    from backend.db import get_db
    from backend.main import app

    rows = MagicMock()
    rows.all.return_value = [("search", 40), ("contents", 2)]
    session = AsyncMock()
    session.execute.return_value = rows

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        resp = await authed_client.get("/v1/usage")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["used"] == 42
    assert body["remaining"] == 958
    assert body["by_endpoint"] == {"search": 40, "contents": 2}
