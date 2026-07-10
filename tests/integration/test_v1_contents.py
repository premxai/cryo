"""Integration tests for /v1/contents and /v1/find-similar (mocked services)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models import SearchResult


def _fake_key():
    key = MagicMock()
    key.id = uuid.uuid4()
    key.monthly_quota = 1000
    key.rate_limit_per_minute = 60
    key.revoked_at = None
    return key


def _fake_document(doc_id: str = "abc123def4567890"):
    doc = MagicMock()
    doc.id = doc_id
    doc.url = "https://example.com/2019/essays/the-quiet-web"
    doc.text = "Full text of the archived page, not truncated."
    doc.year = 2019
    doc.domain = "example.com"
    doc.source = "corpus"
    doc.links = ["https://example.com/2018/other-essay"]
    doc.human_score = 0.92
    return doc


@pytest.fixture
async def authed_client(client):
    """Client with auth + DB overridden."""
    from backend.auth.keys import require_api_key
    from backend.db import get_db
    from backend.main import app

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[require_api_key] = _fake_key
    app.dependency_overrides[get_db] = override_db
    yield client
    app.dependency_overrides.pop(require_api_key, None)
    app.dependency_overrides.pop(get_db, None)


async def test_contents_requires_key(client):
    resp = await client.post("/v1/contents", json={"ids": ["abc"]})
    assert resp.status_code == 401


async def test_contents_validates_selector(authed_client):
    """Both or neither of ids/urls → 422."""
    resp = await authed_client.post("/v1/contents", json={})
    assert resp.status_code == 422
    resp = await authed_client.post(
        "/v1/contents", json={"ids": ["a"], "urls": ["https://x.com/y"]}
    )
    assert resp.status_code == 422


async def test_contents_by_id_returns_doc_and_per_item_errors(authed_client):
    """Known id → result; unknown id → per-item error, batch still 200."""
    doc = _fake_document()

    async def fake_get(db, doc_id):
        return doc if doc_id == doc.id else None

    with patch("backend.api.v1.get_document_by_id", side_effect=fake_get):
        resp = await authed_client.post("/v1/contents", json={"ids": [doc.id, "nope0000nope0000"]})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["text"] == doc.text
    assert body["results"][0]["source"] == "corpus"
    assert body["results"][0]["links"] == doc.links
    assert body["results"][0]["human_score"] == 0.92
    assert body["results"][0]["cryo_certified"] is True
    assert len(body["errors"]) == 1
    assert body["errors"][0]["item"] == "nope0000nope0000"


async def test_contents_by_url_live_fetch(authed_client):
    """URL path resolves via resolve_url (store-or-fetch)."""
    doc = _fake_document()
    doc.source = "wayback_live"
    with patch("backend.api.v1.resolve_url", new=AsyncMock(return_value=doc)) as mock_resolve:
        resp = await authed_client.post(
            "/v1/contents",
            json={"urls": [doc.url], "timestamp": "20190601", "include_links": False},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["source"] == "wayback_live"
    assert body["results"][0]["links"] is None  # include_links=False
    mock_resolve.assert_awaited_once()


async def test_find_similar_returns_ranked_results(authed_client):
    """find-similar maps service results into the v1 shape."""
    results = [
        SearchResult(
            id="neighbor12345678",
            url="https://example.com/2018/related-essay",
            text_preview="A related essay.",
            timestamp="20180101120000",
            year=2018,
            domain="example.com",
            score=0.91,
        )
    ]
    with patch(
        "backend.api.v1.find_similar", new=AsyncMock(return_value=("source1234567890", results))
    ):
        resp = await authed_client.post(
            "/v1/find-similar", json={"id": "source1234567890", "num_results": 5}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_id"] == "source1234567890"
    assert body["results"][0]["score"] == 0.91


async def test_find_similar_unknown_doc_404(authed_client):
    """ValueError from the service → 404 document_not_found."""
    with patch(
        "backend.api.v1.find_similar",
        new=AsyncMock(side_effect=ValueError("Document 'x' not found")),
    ):
        resp = await authed_client.post("/v1/find-similar", json={"id": "x"})
    assert resp.status_code == 404
    assert resp.json()["error"]["type"] == "document_not_found"


async def test_find_similar_validates_selector(authed_client):
    """Both id and url → 422."""
    resp = await authed_client.post(
        "/v1/find-similar", json={"id": "a", "url": "https://example.com/x"}
    )
    assert resp.status_code == 422
