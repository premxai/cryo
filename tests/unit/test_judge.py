"""Unit tests for the doc-level judge scoring mode (mocked Anthropic client)."""

import json
from unittest.mock import MagicMock, patch

from backend.judge import DOC_QUERY_SENTINEL, DOC_WEIGHTS, RewardScorer


def _mock_client(payload: dict):
    """Anthropic client stub whose messages.create returns the given JSON."""
    client = MagicMock()
    block = MagicMock()
    block.text = json.dumps(payload)
    client.messages.create.return_value = MagicMock(content=[block])
    return client


def _fresh_scorer(tmp_path, monkeypatch):
    """A scorer with the file cache redirected to a temp dir."""
    import backend.judge as judge_mod

    monkeypatch.setattr(judge_mod, "CACHE_DIR", tmp_path)
    return RewardScorer()


def test_score_document_parses_and_weights(tmp_path, monkeypatch):
    """Doc-level scores parse the 3 dims; total uses DOC_WEIGHTS, relevance stays 0."""
    scorer = _fresh_scorer(tmp_path, monkeypatch)
    scorer._client = _mock_client({"authenticity": 0.9, "quality": 0.8, "provenance": 0.7})

    score = scorer.score_document({"id": "doc1", "url": "https://x.com/a", "text": "hello " * 50})

    assert score.authenticity == 0.9
    assert score.relevance == 0.0
    expected = round(
        DOC_WEIGHTS["authenticity"] * 0.9
        + DOC_WEIGHTS["quality"] * 0.8
        + DOC_WEIGHTS["provenance"] * 0.7,
        4,
    )
    assert score.total == expected


def test_score_document_caches_under_doc_namespace(tmp_path, monkeypatch):
    """Second call hits the cache — the API is called exactly once."""
    scorer = _fresh_scorer(tmp_path, monkeypatch)
    client = _mock_client({"authenticity": 0.6, "quality": 0.5, "provenance": 0.5})
    scorer._client = client

    first = scorer.score_document({"id": "doc2", "text": "words"})
    second = scorer.score_document({"id": "doc2", "text": "words"})

    assert client.messages.create.call_count == 1
    assert first.model_dump() == second.model_dump()
    assert scorer._cache_path("doc2", DOC_QUERY_SENTINEL).exists()


def test_score_document_no_client_returns_fallback_uncached(tmp_path, monkeypatch):
    """Without an API key the fallback is returned and NOT cached."""
    scorer = _fresh_scorer(tmp_path, monkeypatch)
    with patch.object(scorer, "_get_client", return_value=None):
        score = scorer.score_document({"id": "doc3", "text": "words"})
    assert score.total == 0.5  # neutral fallback
    assert not scorer._cache_path("doc3", DOC_QUERY_SENTINEL).exists()


def test_score_document_api_error_returns_fallback_uncached(tmp_path, monkeypatch):
    """A malformed API response falls back without poisoning the cache."""
    scorer = _fresh_scorer(tmp_path, monkeypatch)
    client = MagicMock()
    block = MagicMock()
    block.text = "not json at all"
    client.messages.create.return_value = MagicMock(content=[block])
    scorer._client = client

    score = scorer.score_document({"id": "doc4", "text": "words"})
    assert score.total == 0.5
    assert not scorer._cache_path("doc4", DOC_QUERY_SENTINEL).exists()
