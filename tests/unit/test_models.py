"""Unit tests for Pydantic input validation models."""

import pytest
from pydantic import ValidationError

from backend.models import SearchQuery, SearchResult


class TestSearchQuery:
    """Tests for SearchQuery input validation."""

    def test_valid_query(self):
        q = SearchQuery(q="machine learning")
        assert q.q == "machine learning"
        assert q.year_min == 2000
        assert q.year_max == 2021
        assert q.limit == 20
        assert q.offset == 0
        assert q.sort == "relevance"

    def test_query_strips_whitespace(self):
        q = SearchQuery(q="  hello world  ")
        assert q.q == "hello world"

    def test_query_strips_null_bytes(self):
        q = SearchQuery(q="test\x00query")
        assert q.q == "testquery"

    def test_empty_query_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="   ")

    def test_null_byte_only_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="\x00")

    def test_query_too_long_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="x" * 501)

    def test_query_max_length_ok(self):
        q = SearchQuery(q="x" * 500)
        assert len(q.q) == 500

    def test_year_max_default(self):
        q = SearchQuery(q="test")
        assert q.year_max == 2021

    def test_year_max_custom(self):
        q = SearchQuery(q="test", year_max=2019)
        assert q.year_max == 2019

    def test_year_max_too_high_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="test", year_max=2022)

    def test_year_max_too_low_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="test", year_max=1999)

    def test_limit_default(self):
        q = SearchQuery(q="test")
        assert q.limit == 20

    def test_limit_max(self):
        q = SearchQuery(q="test", limit=50)
        assert q.limit == 50

    def test_limit_too_high_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="test", limit=51)

    def test_limit_zero_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="test", limit=0)

    def test_year_max_less_than_year_min_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="test", year_min=2020, year_max=2018)

    def test_year_min_equal_year_max_ok(self):
        q = SearchQuery(q="test", year_min=2019, year_max=2019)
        assert q.year_min == q.year_max == 2019

    def test_sort_relevance_default(self):
        q = SearchQuery(q="test")
        assert q.sort == "relevance"

    def test_sort_date_desc_ok(self):
        q = SearchQuery(q="test", sort="date_desc")
        assert q.sort == "date_desc"

    def test_sort_invalid_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="test", sort="popularity")

    def test_offset_default_zero(self):
        q = SearchQuery(q="test")
        assert q.offset == 0

    def test_offset_too_high_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="test", offset=1001)

    def test_domain_filter_accepted(self):
        q = SearchQuery(q="test", domain="wikipedia.org")
        assert q.domain == "wikipedia.org"

    def test_domain_quotes_stripped(self):
        q = SearchQuery(q="test", domain='"wikipedia.org"')
        assert '"' not in q.domain

    def test_content_type_qa_accepted(self):
        q = SearchQuery(q="test", content_type="qa")
        assert q.content_type == "qa"

    def test_content_type_invalid_raises(self):
        with pytest.raises(ValidationError):
            SearchQuery(q="test", content_type="video")


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_minimal_result(self):
        r = SearchResult(
            id="abc123",
            url="https://example.com/page",
            text_preview="Some text preview",
            timestamp="20210315",
            year=2021,
            domain="example.com",
        )
        assert r.human_score is None
        assert r.cryo_certified is False
        assert r.reward_scores is None

    def test_human_score_valid(self):
        r = SearchResult(
            id="x",
            url="https://example.com",
            text_preview="t",
            timestamp="20200101",
            year=2020,
            domain="example.com",
            human_score=0.92,
        )
        assert r.human_score == 0.92

    def test_human_score_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            SearchResult(
                id="x",
                url="https://example.com",
                text_preview="t",
                timestamp="20200101",
                year=2020,
                domain="example.com",
                human_score=1.5,
            )
