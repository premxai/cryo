"""Integration test fixtures — mocks external services so tests run without live infra."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    """Async test client for the FastAPI app with external services mocked."""
    # Mock the DB pool init so tests don't need a real PostgreSQL
    with (
        patch("backend.db.init_db_pool", new_callable=AsyncMock),
        patch("backend.db.close_db_pool", new_callable=AsyncMock),
        patch("backend.search.verify_meilisearch", return_value=True),
    ):
        from backend.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
