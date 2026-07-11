"""Golden-set search-quality regression — run against a REAL indexed corpus.

Skipped unless CRYO_GOLDEN=1 (needs live Meilisearch with the corpus loaded).
Run pre-launch on the production box:

    CRYO_GOLDEN=1 python -m pytest tests/quality/ -v
"""

import os

import pytest

from backend.models import SearchQuery
from backend.search import keyword_search

pytestmark = pytest.mark.skipif(
    os.environ.get("CRYO_GOLDEN") != "1",
    reason="golden-set regression needs a live indexed corpus (set CRYO_GOLDEN=1)",
)

# (query, domain expected somewhere in the top 10)
GOLDEN_SET = [
    ("do things that don't scale startup", "paulgraham.com"),
    ("programming language question", "stackoverflow.com"),
    ("hacker news discussion technology", "news.ycombinator.com"),
    ("classic literature public domain book", "gutenberg.org"),
    ("encyclopedia article history", "wikipedia.org"),
]


@pytest.mark.parametrize(("query", "expected_domain"), GOLDEN_SET)
def test_golden_query_hits_expected_domain(query: str, expected_domain: str):
    """Each golden query surfaces its expected source domain in the top 10."""
    resp = keyword_search(SearchQuery(q=query, limit=10))
    domains = {r.domain for r in resp.results}
    assert any(expected_domain in d for d in domains), (
        f"{expected_domain} not in top-10 domains for {query!r}: {sorted(domains)}"
    )


def test_golden_no_empty_results():
    """A broad query never returns zero results on a real corpus."""
    resp = keyword_search(SearchQuery(q="the internet", limit=10))
    assert resp.total > 0
