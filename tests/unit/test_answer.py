"""Unit tests for the /v1/answer service (mocked Anthropic + search + PG)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.errors import APIError
from backend.models import SearchResponse, SearchResult
from backend.services import answer as answer_mod


def _search_response(n: int = 2) -> SearchResponse:
    results = [
        SearchResult(
            id=f"doc{i}",
            url=f"https://example.com/2019/essay-{i}",
            text_preview=f"Preview text {i}.",
            timestamp="20190101120000",
            year=2019,
            domain="example.com",
            human_score=0.9,
            cryo_certified=True,
        )
        for i in range(1, n + 1)
    ]
    return SearchResponse(query="q", results=results, total=n, search_time_ms=5)


def _mock_client(text: str):
    client = MagicMock()
    block = MagicMock()
    block.text = text
    client.messages.create.return_value = MagicMock(content=[block])
    return client


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(answer_mod, "CACHE_DIR", tmp_path)
    return tmp_path


async def test_answer_happy_path_and_cache(isolated_cache):
    """Grounded answer with parsed citations; second call served from cache."""
    client = _mock_client("The old web was weird [1]. It was also small [2].")
    with (
        patch.object(answer_mod, "_get_client", return_value=client),
        patch.object(answer_mod, "keyword_search", return_value=_search_response()),
        patch.object(answer_mod, "get_document_by_id", new=AsyncMock(return_value=None)),
    ):
        first = await answer_mod.answer_query(AsyncMock(), "what was the old web like", 2)
        second = await answer_mod.answer_query(AsyncMock(), "what was the old web like", 2)

    assert first["cached"] is False
    assert len(first["citations"]) == 2
    assert first["citations"][0]["archive_url"].startswith("https://web.archive.org/web/2019")
    assert first["citations"][0]["human_score"] == 0.9
    assert second["cached"] is True
    assert client.messages.create.call_count == 1  # cache absorbed the repeat


async def test_answer_no_key_503(isolated_cache):
    """No Anthropic client → APIError 503 answer_unavailable, nothing cached."""
    with (
        patch.object(answer_mod, "_get_client", return_value=None),
        pytest.raises(APIError) as exc,
    ):
        await answer_mod.answer_query(AsyncMock(), "unique no-key question", 4)
    assert exc.value.status_code == 503
    assert exc.value.error_type == "answer_unavailable"
    assert not list(isolated_cache.iterdir())


async def test_answer_no_sources_404(isolated_cache):
    """Empty search → 404 no_sources."""
    empty = SearchResponse(query="q", results=[], total=0, search_time_ms=1)
    with (
        patch.object(answer_mod, "_get_client", return_value=_mock_client("x")),
        patch.object(answer_mod, "keyword_search", return_value=empty),
        pytest.raises(APIError) as exc,
    ):
        await answer_mod.answer_query(AsyncMock(), "question with no matches", 4)
    assert exc.value.status_code == 404


async def test_answer_uncited_falls_back_to_all_sources(isolated_cache):
    """An answer without [n] markers cites every source rather than none."""
    client = _mock_client("A plain answer with no citation markers.")
    with (
        patch.object(answer_mod, "_get_client", return_value=client),
        patch.object(answer_mod, "keyword_search", return_value=_search_response(3)),
        patch.object(answer_mod, "get_document_by_id", new=AsyncMock(return_value=None)),
    ):
        result = await answer_mod.answer_query(AsyncMock(), "another unique question", 3)
    assert len(result["citations"]) == 3


async def test_answer_full_text_hydration(isolated_cache):
    """When the doc exists in PG, its full text (not the preview) feeds the prompt."""
    doc = MagicMock()
    doc.text = "FULL ARCHIVED TEXT " * 50
    captured = {}

    def capture_prompt(*args, **kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        block = MagicMock()
        block.text = "Answer [1]."
        return MagicMock(content=[block])

    client = MagicMock()
    client.messages.create.side_effect = capture_prompt
    with (
        patch.object(answer_mod, "_get_client", return_value=client),
        patch.object(answer_mod, "keyword_search", return_value=_search_response(1)),
        patch.object(answer_mod, "get_document_by_id", new=AsyncMock(return_value=doc)),
    ):
        await answer_mod.answer_query(AsyncMock(), "hydration check question", 1)
    assert "FULL ARCHIVED TEXT" in captured["prompt"]
