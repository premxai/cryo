"""Unit tests for the domain-enumeration service (CDX parsing, normalization, cache)."""

from unittest.mock import AsyncMock, patch

import httpx

from backend.services import domains

CDX_ROWS = [
    ["original", "timestamp"],
    ["https://example.com/2019/how-the-web-was-won", "20190301000000"],
    ["https://example.com/2019/how-the-web-was-won", "20190401000000"],  # dupe URL
    ["https://example.com/login", "20190101000000"],  # junk path
    ["https://example.com/2020/remembering-geocities", "20200601000000"],
    ["https://example.com/x", "20200101000000"],  # too-short path
]


def test_normalize_domain_variants():
    """Scheme, www, path, and port are stripped; garbage rejected."""
    assert domains.normalize_domain("https://www.Foo.com/bar?x=1") == "foo.com"
    assert domains.normalize_domain("paulgraham.com") == "paulgraham.com"
    assert domains.normalize_domain("sub.domain.co.uk:8080") == "sub.domain.co.uk"
    assert domains.normalize_domain("not a domain") is None
    assert domains.normalize_domain("localhost") is None  # no TLD
    assert domains.normalize_domain("") is None


def test_parse_cdx_rows_filters_and_dedupes():
    """Header skipped, junk/short URLs filtered, duplicates collapsed."""
    pages = domains.parse_cdx_rows(CDX_ROWS)
    urls = [u for u, _ in pages]
    assert "https://example.com/2019/how-the-web-was-won" in urls
    assert "https://example.com/2020/remembering-geocities" in urls
    assert not any("login" in u for u in urls)
    assert len(urls) == len(set(urls))


async def test_fetch_cdx_uses_freeze_cutoff(monkeypatch):
    """The CDX query is bounded to pre-2022 captures."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=CDX_ROWS)

    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient

    def patched_client(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_client(**kwargs)

    monkeypatch.setattr(domains.httpx, "AsyncClient", patched_client)
    pages = await domains._fetch_cdx("example.com")
    assert captured["params"]["to"] == domains.FREEZE_CUTOFF
    assert len(pages) == 2


async def test_cached_cdx_hits_redis(monkeypatch):
    """Second call within TTL is served from Redis, not the CDX API."""
    redis = AsyncMock()
    redis.get.return_value = '[["https://example.com/2019/cached-essay", "20190101000000"]]'
    monkeypatch.setattr(domains, "get_redis", lambda: redis)
    with patch.object(domains, "_fetch_cdx", new=AsyncMock()) as mock_fetch:
        pages = await domains._cached_cdx("example.com")
    mock_fetch.assert_not_awaited()
    assert pages == [("https://example.com/2019/cached-essay", "20190101000000")]
