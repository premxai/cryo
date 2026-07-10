"""Domain enumeration for /v1/list-domain — "what did this site publish before 2022?"

Queries the Wayback CDX index (zero storage), filters to article-like URLs,
marks which pages are already in the local corpus, and caches per-domain
results in Redis for an hour (the CDX API is slow and rate-limited).
"""

import json
import re
import urllib.parse

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.quota import get_redis
from backend.config import settings
from backend.services.models import Document
from pipeline.ingest_wayback import _JUNK_PATH_RE

logger = structlog.get_logger()

CDX_API = "https://web.archive.org/cdx/search/cdx"
FREEZE_CUTOFF = "20211231"
CACHE_TTL_SECONDS = 3600
MAX_CDX_ROWS = 500  # fetch more than requested so article filtering still fills the page

_DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)+$"
)


def normalize_domain(raw: str) -> str | None:
    """Reduce user input ('https://www.foo.com/bar', 'foo.com') to a bare domain, or None."""
    value = raw.strip().lower()
    if "://" in value:
        value = urllib.parse.urlparse(value).netloc
    value = value.split("/")[0].split(":")[0]
    if value.startswith("www."):
        value = value[4:]
    return value if _DOMAIN_RE.fullmatch(value) else None


_EXT_RE = re.compile(r"\.(html?|shtml|php|aspx?)$", re.IGNORECASE)
_SLUG_RE = re.compile(r"^[\w\-.]+$")
_UTILITY_SEGMENTS = frozenset(
    [
        "login",
        "logout",
        "signin",
        "signup",
        "register",
        "account",
        "cart",
        "checkout",
        "feed",
        "rss",
        "sitemap",
        "robots.txt",
        "favicon.ico",
        "admin",
        "wp-admin",
        "wp-login",
    ]
)


def _is_content_url(url: str) -> bool:
    """True for content-page URLs, era-appropriate: the pre-2022 web is full of
    /essay.html style paths, unlike the slug-only heuristic used for bulk ingest.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    path = parsed.path
    if len(path) <= 1:  # homepage
        return False
    if _JUNK_PATH_RE.search(path) or _JUNK_PATH_RE.search(url):
        return False
    if ":" in parsed.netloc.split("@")[-1]:  # hostname:port proxy artifacts
        return False
    segments = [s for s in path.split("/") if s]
    if not segments:
        return False
    if any(seg.lower() in _UTILITY_SEGMENTS for seg in segments):
        return False
    last = _EXT_RE.sub("", segments[-1])
    return len(last) >= 2 and bool(_SLUG_RE.fullmatch(last))


def parse_cdx_rows(rows: list) -> list[tuple[str, str]]:
    """CDX JSON rows (header row first) -> deduped (url, timestamp) content pages."""
    pages: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows[1:]:  # row 0 is the header ["original", "timestamp"]
        if len(row) < 2:
            continue
        url, ts = row[0], row[1]
        if url in seen or not _is_content_url(url):
            continue
        seen.add(url)
        pages.append((url, ts))
    return pages


async def _fetch_cdx(domain: str) -> list[tuple[str, str]]:
    """Query the CDX API for a domain's pre-2022 HTML captures."""
    params = {
        "url": f"{domain}/*",
        "output": "json",
        "to": FREEZE_CUTOFF,
        "fl": "original,timestamp",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "urlkey",
        "limit": str(MAX_CDX_ROWS),
    }
    timeout = httpx.Timeout(settings.cdx_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(CDX_API, params=params)
        resp.raise_for_status()
        rows = resp.json() if resp.content else []
    return parse_cdx_rows(rows)


async def _cached_cdx(domain: str) -> list[tuple[str, str]]:
    """CDX results with a 1h Redis cache (the API is slow; domains rarely change)."""
    redis = get_redis()
    cache_key = f"cdx:{domain}"
    if redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            return [tuple(p) for p in json.loads(cached)]
    pages = await _fetch_cdx(domain)
    if redis is not None:
        await redis.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(pages))
    return pages


async def list_domain(db: AsyncSession, domain: str, limit: int) -> list[dict]:
    """Enumerate a domain's archived pre-2022 article pages.

    Returns [{url, timestamp, in_corpus}] — in_corpus marks pages already
    fetched into the local store (readable via /v1/contents without a live fetch).
    """
    pages = (await _cached_cdx(domain))[:limit]
    if not pages:
        return []

    urls = [url for url, _ in pages]
    result = await db.execute(select(Document.url).where(Document.url.in_(urls)))
    stored = {row[0] for row in result.all()}

    logger.info("cryo.list_domain", domain=domain, pages=len(pages), in_corpus=len(stored))
    return [{"url": url, "timestamp": ts, "in_corpus": url in stored} for url, ts in pages]
