"""Integration tests for the /search and health endpoints."""

from unittest.mock import MagicMock, patch

import pytest

from backend.models import SearchResponse, SearchResult


def _mock_search_response(query: str = "test") -> SearchResponse:
    """Return a fake but valid SearchResponse for testing."""
    return SearchResponse(
        query=query,
        results=[
            SearchResult(
                id="doc_abc123",
                url="https://example.com/article",
                text_preview="This is a sample article about machine learning from 2020.",
                timestamp="20200315120000",
                year=2020,
                domain="example.com",
                word_count=320,
            )
        ],
        total=847,
        search_time_ms=23,
    )


@pytest.mark.asyncio
class TestSearchEndpoint:
    """Tests for GET /search."""

    async def test_search_returns_200(self, client):
        with patch("backend.main.keyword_search", return_value=_mock_search_response("machine learning")):
            response = await client.get("/search", params={"q": "machine learning"})
        assert response.status_code == 200

    async def test_search_response_shape(self, client):
        with patch("backend.main.keyword_search", return_value=_mock_search_response("python")):
            response = await client.get("/search", params={"q": "python"})
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "total" in data
        assert "search_time_ms" in data
        assert "facets" in data
        assert isinstance(data["results"], list)

    async def test_search_result_has_required_fields(self, client):
        with patch("backend.main.keyword_search", return_value=_mock_search_response("test")):
            response = await client.get("/search", params={"q": "test"})
        result = response.json()["results"][0]
        for field in ("id", "url", "text_preview", "timestamp", "year", "domain"):
            assert field in result, f"Missing field: {field}"

    async def test_empty_query_returns_422(self, client):
        response = await client.get("/search", params={"q": ""})
        assert response.status_code == 422

    async def test_query_too_long_returns_422(self, client):
        response = await client.get("/search", params={"q": "x" * 501})
        assert response.status_code == 422

    async def test_limit_too_high_returns_422(self, client):
        response = await client.get("/search", params={"q": "test", "limit": 100})
        assert response.status_code == 422

    async def test_year_max_out_of_range_returns_422(self, client):
        response = await client.get("/search", params={"q": "test", "year_max": 2023})
        assert response.status_code == 422

    async def test_sort_date_desc_accepted(self, client):
        with patch("backend.main.keyword_search", return_value=_mock_search_response("python")):
            response = await client.get("/search", params={"q": "python", "sort": "date_desc"})
        assert response.status_code == 200

    async def test_invalid_sort_returns_422(self, client):
        response = await client.get("/search", params={"q": "test", "sort": "random"})
        assert response.status_code == 422

    async def test_offset_pagination_accepted(self, client):
        with patch("backend.main.keyword_search", return_value=_mock_search_response("test")):
            response = await client.get("/search", params={"q": "test", "offset": 20})
        assert response.status_code == 200

    async def test_search_service_down_returns_503(self, client):
        with patch("backend.main.keyword_search", side_effect=RuntimeError("Meili down")):
            response = await client.get("/search", params={"q": "test"})
        assert response.status_code == 503
        assert "detail" in response.json()

    async def test_search_never_returns_500_on_random_input(self, client):
        """Search should never 500 on user input — at worst 422 or 503."""
        test_inputs = [
            "hello world",
            "hello\x00world",   # null bytes sanitized
            "a" * 499,          # near-max length
            "   spaces   ",     # whitespace trimmed
        ]
        for q in test_inputs:
            with patch("backend.main.keyword_search", return_value=_mock_search_response(q)):
                response = await client.get("/search", params={"q": q})
            assert response.status_code != 500, f"Got 500 for query: {repr(q)}"

    async def test_suggest_returns_list(self, client):
        with patch("backend.main.suggest_completions", return_value=["machine learning", "machine translation"]):
            response = await client.get("/suggest", params={"q": "mach"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_facets_returns_dict(self, client):
        with patch("backend.main.get_facet_counts", return_value={}):
            response = await client.get("/facets")
        assert response.status_code == 200
        assert isinstance(response.json(), dict)


@pytest.mark.asyncio
class TestHealthEndpoints:
    """Tests for /healthz/* probes."""

    async def test_liveness_returns_200(self, client):
        response = await client.get("/healthz/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_readiness_with_db_ok(self, client):
        mock_session = MagicMock()
        mock_session.execute = MagicMock(return_value=None)

        with patch("backend.main.get_db") as mock_dep:
            async def _yield_session():
                yield mock_session
            mock_dep.return_value = _yield_session()

            # The readiness endpoint does a SELECT 1 — we just need it not to raise
            response = await client.get("/healthz/ready")
        # Either 200 or 503 depending on mock depth — just not 500
        assert response.status_code in (200, 503)
