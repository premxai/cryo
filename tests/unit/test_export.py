"""Unit tests for the dataset export shape and stats builder."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pipeline.export_dataset import _build_stats, _doc_row, _score_bucket


def _fake_doc(doc_id: str, score: float, source: str = "corpus", year: int = 2019):
    doc = MagicMock()
    doc.id = doc_id
    doc.url = f"https://example.com/{doc_id}"
    doc.text = "full text"
    doc.timestamp = "20190101120000"
    doc.year = year
    doc.domain = "example.com"
    doc.source = source
    doc.word_count = 100
    doc.content_type = "article"
    doc.human_score = score
    doc.judge_scores = {"authenticity": score, "quality": 0.7, "provenance": 0.6, "total": 0.7}
    doc.scored_at = datetime(2026, 7, 9, tzinfo=UTC)
    return doc


def test_doc_row_carries_full_provenance_chain():
    """Exported rows include url, timestamp, source, scores, and scored_at."""
    row = _doc_row(_fake_doc("abc", 0.9))
    for field in (
        "id",
        "url",
        "text",
        "timestamp",
        "year",
        "domain",
        "source",
        "human_score",
        "judge_scores",
        "scored_at",
    ):
        assert field in row
    assert row["scored_at"].startswith("2026-07-09")


def test_build_stats_composition_and_certified_count():
    """Stats aggregate sources, years, score distribution, certified count."""
    rows = [
        _doc_row(_fake_doc("a", 0.95)),
        _doc_row(_fake_doc("b", 0.90, source="wayback_live")),
        _doc_row(_fake_doc("c", 0.40, year=2015)),
    ]
    stats = _build_stats(rows)
    assert stats["total_documents"] == 3
    assert stats["scored_documents"] == 3
    assert stats["by_source"] == {"corpus": 2, "wayback_live": 1}
    assert stats["certified_count"] == 2
    assert stats["mean_human_score"] == 0.75


def test_score_bucket_edges():
    """Buckets are stable at edges, 1.0 folds into the top bucket."""
    assert _score_bucket(0.0) == "0.0-0.1"
    assert _score_bucket(0.85) == "0.8-0.9"
    assert _score_bucket(1.0) == "0.9-1.0"
