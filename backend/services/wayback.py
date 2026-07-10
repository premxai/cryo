"""Async Wayback Machine client for /v1/contents live page retrieval.

Reuses the pure extraction helpers from pipeline/ingest_wayback.py; the
fetch path is async httpx (the pipeline's sync urllib is batch-only).
"""

import re
import urllib.parse
from dataclasses import dataclass, field

import httpx
import structlog

from backend.config import settings
from pipeline.ingest_wayback import (
    _is_article_url,
    extract_text_fallback,
    extract_text_trafilatura,
    strip_wayback_toolbar,
    url_to_domain,
)

logger = structlog.get_logger()

AVAILABILITY_API = "https://archive.org/wayback/available"
SNAPSHOT_BASE = "https://web.archive.org/web"
FREEZE_CUTOFF = "20211231"  # the corpus is frozen at end of 2021
MAX_LINKS = 50

_HREF_RE = re.compile(r'<a\s[^>]*href=["\']([^"\'#]+)["\']', re.IGNORECASE)
_WAYBACK_REWRITE_RE = re.compile(r"^https?://web\.archive\.org/web/\d+(?:id_|im_|js_|cs_)?/")


@dataclass
class Snapshot:
    """A fetched pre-2022 page: extracted text plus outbound article links."""

    url: str
    timestamp: str
    text: str
    links: list[str] = field(default_factory=list)


def clamp_timestamp(timestamp: str | None) -> str:
    """Clamp a requested YYYYMMDD[HHMMSS] timestamp to the pre-2022 freeze cutoff."""
    ts = (timestamp or FREEZE_CUTOFF)[:14]
    return ts if ts[:8] <= FREEZE_CUTOFF else FREEZE_CUTOFF


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract deduplicated outbound article links from raw page HTML.

    Strips Wayback /web/TIMESTAMP/ rewrites, resolves relative URLs against
    base_url, and keeps only URLs that look like content pages.
    """
    links: list[str] = []
    seen: set[str] = set()
    for href in _HREF_RE.findall(html):
        href = _WAYBACK_REWRITE_RE.sub("", href).strip()
        absolute = urllib.parse.urljoin(base_url, href)
        if not absolute.startswith(("http://", "https://")):
            continue
        if absolute in seen or not _is_article_url(absolute):
            continue
        seen.add(absolute)
        links.append(absolute)
        if len(links) >= MAX_LINKS:
            break
    return links


def parse_availability(payload: dict) -> tuple[str, str] | None:
    """Parse the availability API response into (snapshot_url, timestamp), or None."""
    closest = (payload.get("archived_snapshots") or {}).get("closest") or {}
    if not closest.get("available") or not closest.get("url"):
        return None
    ts = str(closest.get("timestamp", ""))
    if not ts or ts[:8] > FREEZE_CUTOFF:
        return None  # never serve post-freeze content
    return closest["url"], ts


async def find_snapshot(
    client: httpx.AsyncClient, url: str, timestamp: str | None = None
) -> tuple[str, str] | None:
    """Query the Wayback availability API for the closest pre-2022 snapshot."""
    params = {"url": url, "timestamp": clamp_timestamp(timestamp)}
    resp = await client.get(AVAILABILITY_API, params=params)
    resp.raise_for_status()
    return parse_availability(resp.json())


def _extract_text(html: str) -> str:
    """Trafilatura extraction with clean_html fallback (same chain as the pipeline)."""
    stripped = strip_wayback_toolbar(html)
    text = extract_text_trafilatura(stripped)
    if not text or len(text.split()) < 20:
        text = extract_text_fallback(stripped)
    return text or ""


async def fetch_snapshot(url: str, timestamp: str | None = None) -> Snapshot | None:
    """Fetch a pre-2022 snapshot of `url` from the Wayback Machine.

    Uses the id_ endpoint (raw original HTML — no toolbar, no link rewriting).
    Returns None when no pre-freeze snapshot exists or the page has no text.
    """
    timeout = httpx.Timeout(settings.wayback_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        found = await find_snapshot(client, url, timestamp)
        if found is None:
            return None
        _, snap_ts = found

        raw_url = f"{SNAPSHOT_BASE}/{snap_ts}id_/{url}"
        resp = await client.get(raw_url)
        resp.raise_for_status()
        html = resp.text

    text = _extract_text(html)
    if not text:
        logger.info("cryo.wayback.no_text", url=url, timestamp=snap_ts)
        return None
    return Snapshot(url=url, timestamp=snap_ts, text=text, links=extract_links(html, url))


__all__ = [
    "Snapshot",
    "clamp_timestamp",
    "extract_links",
    "fetch_snapshot",
    "find_snapshot",
    "parse_availability",
    "url_to_domain",
]
