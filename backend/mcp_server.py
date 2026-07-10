"""Hosted MCP server — Cryo as a native tool for Claude and agent frameworks.

Mounted at /mcp in the same FastAPI process (streamable HTTP, stateless).
Auth reuses the same API keys as /v1 via a thin ASGI wrapper; usage is
metered under endpoint='mcp'.
"""

import contextvars
import json

import anyio
import structlog
from fastapi import Response
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import select

from backend.auth.keys import hash_key
from backend.auth.models import ApiKey
from backend.auth.quota import (
    _check_monthly_quota,
    _check_rate_limit,
    get_redis,
    record_usage,
)
from backend.db import AsyncSessionLocal
from backend.errors import APIError
from backend.models import SearchQuery
from backend.search import keyword_search
from backend.services.answer import answer_query
from backend.services.contents import get_document_by_id, resolve_url
from backend.services.domains import list_domain, normalize_domain
from backend.services.similar import find_similar

logger = structlog.get_logger()

mcp = FastMCP(
    "cryo",
    instructions=(
        "Search and browse the frozen pre-2022 human web — content verified to "
        "predate AI-generated text. Use cryo_search to find pages, cryo_get_page "
        "to read full text and discover outbound links, and cryo_find_similar to "
        "explore related documents."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    # DNS-rebinding protection guards *local* servers; /mcp is a public,
    # API-key-authenticated endpoint served behind nginx with arbitrary Hosts.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

_current_key: contextvars.ContextVar[ApiKey | None] = contextvars.ContextVar(
    "cryo_mcp_api_key", default=None
)


async def _validate_key(presented: str) -> ApiKey | None:
    """Look up a presented API key. Returns None when invalid/revoked/DB down."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ApiKey).where(ApiKey.key_hash == hash_key(presented)))
            key = result.scalar_one_or_none()
            return None if key is None or key.revoked_at is not None else key
    except Exception as exc:
        logger.error("cryo.mcp.auth_db_error", error=str(exc))
        return None


async def _consume(units: int = 1) -> None:
    """Rate-limit + quota the current MCP call under endpoint='mcp'."""
    key = _current_key.get()
    if key is None or get_redis() is None:
        return
    throwaway = Response()  # MCP has no HTTP response headers to decorate
    await _check_rate_limit(key, throwaway)
    await _check_monthly_quota(key, throwaway, units)
    await record_usage(key.id, "mcp", units)


class MCPAuthMiddleware:
    """ASGI wrapper: validate the API key header and stash the key for quota metering.

    Resolves the inner streamable-HTTP app lazily so a fresh session manager
    (one .run() per instance — re-created per lifespan in tests) is picked up.
    """

    def __init__(self) -> None:
        self._inner = None
        self._manager = None

    @property
    def app(self):
        """The current streamable-HTTP ASGI app, rebuilt if the session manager changed."""
        if self._inner is None or self._manager is not mcp._session_manager:
            self._inner = mcp.streamable_http_app()
            self._manager = mcp._session_manager
        return self._inner

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        auth = headers.get("authorization", "")
        presented = (
            auth[7:].strip() if auth.lower().startswith("bearer ") else headers.get("x-api-key", "")
        )
        key = await _validate_key(presented) if presented else None
        if key is None:
            await _send_401(send)
            return
        token = _current_key.set(key)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_key.reset(token)


async def _send_401(send) -> None:
    """Emit a bare 401 JSON response from raw ASGI."""
    body = json.dumps(
        {
            "error": {
                "type": "invalid_api_key",
                "message": "Pass a valid API key via 'Authorization: Bearer cryo_sk_...'",
            }
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
async def cryo_search(
    query: str,
    num_results: int = 10,
    year_min: int = 2000,
    year_max: int = 2021,
) -> dict:
    """Search the frozen pre-2022 human web corpus (verified pre-AI content).

    Returns matching pages with id, url, snippet text, year, and relevance score.
    Use cryo_get_page with a result's id or url to read the full text.
    """
    await _consume()
    params = SearchQuery(
        q=query, year_min=year_min, year_max=year_max, limit=min(max(num_results, 1), 50)
    )
    resp = await anyio.to_thread.run_sync(keyword_search, params)
    return {
        "total": resp.total,
        "results": [
            {
                "id": r.id,
                "url": r.url,
                "text": r.text_preview.replace("<mark>", "").replace("</mark>", ""),
                "year": r.year,
                "domain": r.domain,
                "score": r.score,
                "human_score": r.human_score,
                "cryo_certified": r.cryo_certified,
            }
            for r in resp.results
        ],
    }


@mcp.tool()
async def cryo_get_page(url: str = "", id: str = "", timestamp: str = "") -> dict:
    """Retrieve the full text of an archived pre-2022 page by URL or document id.

    Live-fetches from the Wayback Machine when the page isn't stored yet (always
    a pre-2022 snapshot). Returns full text plus outbound article links you can
    follow with further cryo_get_page calls to browse the frozen web.
    """
    if bool(url) == bool(id):
        raise APIError(422, "invalid_request", "Provide exactly one of 'url' or 'id'")
    await _consume()
    async with AsyncSessionLocal() as db:
        doc = (
            await get_document_by_id(db, id)
            if id
            else await resolve_url(db, url, timestamp or None)
        )
    if doc is None:
        raise APIError(404, "document_not_found", "No pre-2022 capture found for this page")
    return {
        "id": doc.id,
        "url": doc.url,
        "text": doc.text,
        "year": doc.year,
        "domain": doc.domain,
        "source": doc.source,
        "links": doc.links or [],
        "human_score": doc.human_score,
        "cryo_certified": (doc.human_score or 0) >= 0.85,
    }


@mcp.tool()
async def cryo_find_similar(id: str = "", url: str = "", num_results: int = 10) -> dict:
    """Find documents semantically similar to a reference document (by id or URL)."""
    if bool(url) == bool(id):
        raise APIError(422, "invalid_request", "Provide exactly one of 'url' or 'id'")
    await _consume()
    async with AsyncSessionLocal() as db:
        source_id, results = await find_similar(db, id or None, url or None, num_results)
    return {
        "source_id": source_id,
        "results": [
            {"id": r.id, "url": r.url, "text": r.text_preview, "year": r.year, "score": r.score}
            for r in results
        ],
    }


@mcp.tool()
async def cryo_answer(query: str, num_sources: int = 6) -> dict:
    """Ask the pre-AI web: get an answer grounded ONLY in archived pre-2022 pages.

    Every citation includes an immutable archive link, capture timestamp, and
    human-authenticity score — useful when you need sources that provably
    predate generative AI. Costs 3 quota units.
    """
    await _consume(units=3)
    async with AsyncSessionLocal() as db:
        return await answer_query(db, query, min(max(num_sources, 2), 10))


@mcp.tool()
async def cryo_list_domain(domain: str, limit: int = 50) -> dict:
    """List a website's archived pre-2022 pages — "what did this site publish?"

    Returns article URLs with capture timestamps. Pages marked in_corpus are
    already stored and readable instantly via cryo_get_page; others will be
    live-fetched from the archive on first read.
    """
    normalized = normalize_domain(domain)
    if normalized is None:
        raise APIError(422, "invalid_domain", "Provide a bare domain like 'paulgraham.com'")
    await _consume()
    async with AsyncSessionLocal() as db:
        pages = await list_domain(db, normalized, min(max(limit, 1), 100))
    return {"domain": normalized, "total": len(pages), "pages": pages}


def mcp_asgi_app():
    """The auth-wrapped streamable-HTTP ASGI app, ready to mount at /mcp."""
    return MCPAuthMiddleware()
