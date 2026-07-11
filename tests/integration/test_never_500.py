"""Property-based test: /v1/search never returns 500, whatever the query.

Uses the sync TestClient (hypothesis and async tests don't mix); the app runs
with mocked infra, so search 503s — the property under test is that no input
can crash the handler into a raw 500.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

ACCEPTABLE = {200, 401, 404, 422, 429, 503}


def _fake_key():
    key = MagicMock()
    key.id = uuid.uuid4()
    key.monthly_quota = 1000
    key.rate_limit_per_minute = 60
    key.revoked_at = None
    return key


@pytest.fixture(scope="module")
def sync_client():
    """Module-scoped TestClient with lifespan running and auth overridden."""
    with (
        patch("backend.db.init_db_pool", new_callable=AsyncMock),
        patch("backend.db.close_db_pool", new_callable=AsyncMock),
        patch("backend.auth.quota.init_redis", new_callable=AsyncMock),
        patch("backend.auth.quota.close_redis", new_callable=AsyncMock),
        patch("backend.search.verify_meilisearch", return_value=True),
    ):
        from backend.auth.keys import require_api_key
        from backend.main import app
        from backend.mcp_server import mcp

        mcp._session_manager = None  # single-use session manager, fresh per lifespan
        app.dependency_overrides[require_api_key] = _fake_key
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc
        app.dependency_overrides.pop(require_api_key, None)


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(query=st.text(min_size=0, max_size=600))
def test_v1_search_never_500(sync_client, query):
    """Arbitrary text — including null bytes, emoji, RTL, oversized — never 500s."""
    resp = sync_client.post("/v1/search", json={"query": query})
    assert resp.status_code in ACCEPTABLE, f"{resp.status_code} for query {query!r}"


@settings(
    max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    body=st.dictionaries(
        st.text(max_size=20), st.one_of(st.text(max_size=50), st.integers(), st.none())
    )
)
def test_v1_search_arbitrary_body_never_500(sync_client, body):
    """Garbage request bodies never 500."""
    resp = sync_client.post("/v1/search", json=body)
    assert resp.status_code in ACCEPTABLE
