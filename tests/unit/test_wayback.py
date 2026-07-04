"""Unit tests for the async Wayback service — link extraction, availability, clamping."""

import httpx

from backend.services import wayback

FIXTURE_HTML = """
<html><body>
<h1>The Old Web</h1>
<a href="https://example.com/2019/how-the-web-was-won">Article link</a>
<a href="/blog/remembering-geocities-pages">Relative article</a>
<a href="https://web.archive.org/web/20200101000000/https://example.com/2020/wayback-rewritten-link">Rewritten</a>
<a href="https://example.com/login">Junk: login</a>
<a href="https://example.com/tag/web">Junk: tag page</a>
<a href="https://example.com/2019/how-the-web-was-won">Duplicate</a>
<a href="mailto:someone@example.com">Mail</a>
</body></html>
"""


def test_extract_links_resolves_filters_dedupes():
    """Links are absolute, junk-filtered, wayback-unwrapped, and deduplicated."""
    links = wayback.extract_links(FIXTURE_HTML, "https://example.com/2019/source-article")
    assert "https://example.com/2019/how-the-web-was-won" in links
    assert "https://example.com/blog/remembering-geocities-pages" in links
    assert "https://example.com/2020/wayback-rewritten-link" in links
    assert not any("login" in link or "/tag/" in link or "mailto" in link for link in links)
    assert len(links) == len(set(links))


def test_clamp_timestamp():
    """Post-freeze timestamps clamp to the 2021 cutoff; pre-freeze pass through."""
    assert wayback.clamp_timestamp("20250101") == wayback.FREEZE_CUTOFF
    assert wayback.clamp_timestamp("20190615") == "20190615"
    assert wayback.clamp_timestamp(None) == wayback.FREEZE_CUTOFF


def test_parse_availability_happy_path():
    """A valid pre-2022 closest snapshot is returned."""
    payload = {
        "archived_snapshots": {
            "closest": {
                "available": True,
                "url": "http://web.archive.org/web/20200401000000/https://example.com/page",
                "timestamp": "20200401000000",
            }
        }
    }
    result = wayback.parse_availability(payload)
    assert result is not None
    assert result[1] == "20200401000000"


def test_parse_availability_rejects_post_freeze_and_missing():
    """Post-2021 snapshots and empty payloads return None."""
    post = {
        "archived_snapshots": {
            "closest": {"available": True, "url": "http://w/x", "timestamp": "20230101000000"}
        }
    }
    assert wayback.parse_availability(post) is None
    assert wayback.parse_availability({}) is None
    assert wayback.parse_availability({"archived_snapshots": {}}) is None


async def test_find_snapshot_uses_mock_transport():
    """find_snapshot parses the availability API over a mocked transport."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["timestamp"] <= wayback.FREEZE_CUTOFF
        return httpx.Response(
            200,
            json={
                "archived_snapshots": {
                    "closest": {
                        "available": True,
                        "url": "http://web.archive.org/web/20201101000000/https://example.com/essay",
                        "timestamp": "20201101000000",
                    }
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        found = await wayback.find_snapshot(client, "https://example.com/essay", "20991231")
    assert found == (
        "http://web.archive.org/web/20201101000000/https://example.com/essay",
        "20201101000000",
    )


def test_extract_text_fallback_chain():
    """_extract_text produces text from plain HTML."""
    html = "<html><body><p>" + " ".join(["word"] * 30) + "</p></body></html>"
    text = wayback._extract_text(html)
    assert "word" in text
