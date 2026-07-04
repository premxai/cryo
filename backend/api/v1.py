"""The /v1 authenticated API router — search, usage (contents + find-similar in Phase 2)."""

import re
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import (
    V1Result,
    V1SearchRequest,
    V1SearchResponse,
    V1UsageResponse,
)
from backend.auth.keys import require_api_key
from backend.auth.models import ApiKey, UsageLedger
from backend.auth.quota import current_month, enforce_limits
from backend.db import get_db
from backend.errors import APIError
from backend.models import SearchQuery, SearchResult
from backend.search import keyword_search

logger = structlog.get_logger()

router = APIRouter(prefix="/v1", tags=["v1"])

_MARK_RE = re.compile(r"</?mark>")
_SLUG_STRIP_RE = re.compile(r"\.(html?|php|aspx?)$", re.IGNORECASE)


def _title_from_url(url: str) -> str | None:
    """Best-effort human-readable title from the last URL path segment."""
    path = url.split("?")[0].rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    slug = _SLUG_STRIP_RE.sub("", slug)
    title = slug.replace("-", " ").replace("_", " ").strip()
    if not title or title.startswith(("http", "www.")) or len(title) < 3:
        return None
    return title[:120].title()


def _to_v1_result(r: SearchResult) -> V1Result:
    """Map an internal SearchResult to the public v1 shape (no highlight markup)."""
    return V1Result(
        id=r.id,
        url=r.url,
        title=_title_from_url(r.url),
        text=_MARK_RE.sub("", r.text_preview),
        score=r.score,
        published_year=r.year,
        domain=r.domain,
        content_type=r.content_type,
    )


@router.post(
    "/search",
    response_model=V1SearchResponse,
    summary="Search the frozen pre-2022 human web",
)
async def v1_search(
    body: V1SearchRequest,
    request: Request,
    key: Annotated[ApiKey, Depends(enforce_limits("search"))],
) -> V1SearchResponse:
    """Hybrid BM25 + semantic-rerank search over the verified pre-AI-era corpus."""
    params = SearchQuery(
        q=body.query,
        year_min=body.year_min,
        year_max=body.year_max,
        limit=body.num_results,
        domain=body.domain,
        content_type=body.content_type,
    )
    try:
        internal = keyword_search(params)
    except Exception as exc:
        logger.error("cryo.v1.search_failed", query=body.query, error=str(exc))
        raise APIError(503, "search_unavailable", "Search is temporarily unavailable") from exc

    return V1SearchResponse(
        results=[_to_v1_result(r) for r in internal.results],
        total=internal.total,
        search_time_ms=internal.search_time_ms,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.get(
    "/usage",
    response_model=V1UsageResponse,
    summary="Current-month API usage for this key",
)
async def v1_usage(
    key: Annotated[ApiKey, Depends(require_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> V1UsageResponse:
    """Return quota consumption for the calling key, broken down by endpoint."""
    month = current_month()
    rows = await db.execute(
        select(UsageLedger.endpoint, UsageLedger.request_count).where(
            UsageLedger.api_key_id == key.id, UsageLedger.month == month
        )
    )
    by_endpoint = {endpoint: count for endpoint, count in rows.all()}
    used = sum(by_endpoint.values())
    return V1UsageResponse(
        month=month,
        quota=key.monthly_quota,
        used=used,
        remaining=max(0, key.monthly_quota - used),
        by_endpoint=by_endpoint,
    )
