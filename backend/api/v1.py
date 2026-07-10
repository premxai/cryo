"""The /v1 authenticated API router — search, usage (contents + find-similar in Phase 2)."""

import re
import time
from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import (
    V1ContentsError,
    V1ContentsRequest,
    V1ContentsResponse,
    V1ContentsResult,
    V1FindSimilarRequest,
    V1FindSimilarResponse,
    V1Result,
    V1SearchRequest,
    V1SearchResponse,
    V1UsageResponse,
)
from backend.auth.keys import require_api_key
from backend.auth.models import ApiKey, UsageLedger
from backend.auth.quota import consume_quota, current_month, enforce_limits
from backend.db import get_db
from backend.errors import APIError
from backend.models import SearchQuery, SearchResult
from backend.search import keyword_search
from backend.services.contents import get_document_by_id, resolve_url
from backend.services.models import Document
from backend.services.similar import find_similar

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
        human_score=r.human_score,
        cryo_certified=r.cryo_certified,
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


def _doc_to_contents_result(doc: Document, include_links: bool) -> V1ContentsResult:
    """Map a stored Document to the /v1/contents response shape."""
    return V1ContentsResult(
        id=doc.id,
        url=doc.url,
        title=_title_from_url(doc.url),
        text=doc.text,
        published_year=doc.year,
        domain=doc.domain,
        source=doc.source,
        links=doc.links if include_links else None,
        human_score=doc.human_score,
        cryo_certified=(doc.human_score or 0) >= 0.85,
    )


@router.post(
    "/contents",
    response_model=V1ContentsResponse,
    summary="Retrieve full archived page text by id or URL",
)
async def v1_contents(
    body: V1ContentsRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    key: Annotated[ApiKey, Depends(require_api_key)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> V1ContentsResponse:
    """Fetch full document text — from the frozen corpus store, else live from
    the Wayback Machine (always pre-2022 snapshots; live fetches are stored).

    Each requested item costs 1 quota unit. Failures are per-item, never batch-wide.
    """
    items = body.ids or body.urls or []
    await consume_quota(key, response, background, "contents", units=len(items))

    results: list[V1ContentsResult] = []
    errors: list[V1ContentsError] = []
    for item in items:
        try:
            if body.ids:
                doc = await get_document_by_id(db, item)
                reason = "Unknown document id"
            else:
                doc = await resolve_url(db, item, body.timestamp)
                reason = "No pre-2022 snapshot available for this URL"
            if doc is None:
                errors.append(V1ContentsError(item=item, reason=reason))
            else:
                results.append(_doc_to_contents_result(doc, body.include_links))
        except Exception as exc:
            logger.warning("cryo.v1.contents_item_failed", item=item, error=str(exc))
            errors.append(V1ContentsError(item=item, reason="Retrieval failed — try again later"))

    return V1ContentsResponse(
        results=results,
        errors=errors,
        request_id=getattr(request.state, "request_id", ""),
    )


@router.post(
    "/find-similar",
    response_model=V1FindSimilarResponse,
    summary="Find documents similar to a reference document",
)
async def v1_find_similar(
    body: V1FindSimilarRequest,
    request: Request,
    key: Annotated[ApiKey, Depends(enforce_limits("find_similar"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> V1FindSimilarResponse:
    """Semantic neighbors of a document: BM25 recall on its salient terms,
    re-ranked by embedding cosine similarity against the full source text.
    """
    start_ms = int(time.time() * 1000)
    try:
        source_id, internal = await find_similar(db, body.id, body.url, body.num_results)
    except ValueError as exc:
        raise APIError(404, "document_not_found", str(exc)) from exc
    except Exception as exc:
        logger.error("cryo.v1.find_similar_failed", error=str(exc))
        raise APIError(
            503, "search_unavailable", "Find-similar is temporarily unavailable"
        ) from exc

    return V1FindSimilarResponse(
        source_id=source_id,
        results=[_to_v1_result(r) for r in internal],
        search_time_ms=int(time.time() * 1000) - start_ms,
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
