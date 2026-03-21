"""Cryo FastAPI application.

Milestone 1.5 endpoints:
    GET /search              — BM25 keyword search (year range, sort, facets, pagination, highlighting)
    GET /suggest             — Autocomplete suggestions
    GET /facets              — Global or query-scoped facet counts
    GET /healthz/live        — Liveness probe
    GET /healthz/ready       — Readiness probe (checks DB)

Added in later milestones:
    POST /score              — M2 LLM council authenticity scoring
    GET /semantic-search     — M3 vector/semantic search
"""

import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db import close_db_pool, get_db, init_db_pool
from backend.logging_config import configure_logging
from backend.models import FacetCount, HealthResponse, SearchQuery, SearchResponse
from backend.search import get_facet_counts, keyword_search, suggest_completions, verify_meilisearch

logger = structlog.get_logger()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    configure_logging()
    logger.info("cryo.startup", env=settings.env, log_level=settings.log_level)

    # DB — non-fatal in dev
    await init_db_pool()

    # Meilisearch — warn but continue if not reachable
    if not verify_meilisearch():
        logger.warning(
            "cryo.startup.meili_unreachable",
            url=settings.meilisearch_url,
            hint="Start with: bin/meilisearch.exe --master-key cryo_dev_key",
        )
    else:
        logger.info("cryo.startup.meili_ok", url=settings.meilisearch_url)

    logger.info("cryo.startup.complete")
    yield

    # Shutdown
    await close_db_pool()
    logger.info("cryo.shutdown")


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Cryo API",
    description="Authentic pre-2022 human web search with RLAIF",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

# Prometheus metrics (exposes /metrics endpoint)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# CORS — GET + POST (POST needed for future /score endpoint)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ── Request ID middleware ──────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Bind a unique request_id to every structlog log line within this request."""
    request_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    structlog.contextvars.clear_contextvars()
    return response


# ── Error handlers ────────────────────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return structured validation errors without leaking internals."""
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — log and return 500 without stack trace."""
    logger.error(
        "cryo.unhandled_exception",
        path=str(request.url.path),
        method=request.method,
        exc_info=exc,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get(
    "/search",
    response_model=SearchResponse,
    summary="BM25 keyword search over pre-2022 corpus",
    tags=["Search"],
)
async def search(params: Annotated[SearchQuery, Depends()]) -> SearchResponse:
    """Search the frozen pre-2022 human web corpus using BM25 keyword matching.

    Supports filtering by year range, domain, and content type.
    Supports sorting by relevance (default) or date.
    Returns facet counts for sidebar filters.
    Results include highlighted matched terms in text_preview.
    """
    try:
        return keyword_search(params)
    except Exception as exc:
        logger.error("cryo.search.failed", query=params.q, error=str(exc))
        raise HTTPException(status_code=503, detail="Search service temporarily unavailable") from exc


@app.get(
    "/suggest",
    response_model=list[str],
    summary="Autocomplete query suggestions",
    tags=["Search"],
)
async def suggest(
    q: str = Query(..., min_length=1, max_length=100, description="Partial query to complete"),
) -> list[str]:
    """Return up to 8 autocomplete suggestions for the given partial query.

    Uses lightweight Meilisearch search to extract common phrases.
    Always returns a list (empty on error — never raises).
    """
    return suggest_completions(q, limit=8)


@app.get(
    "/facets",
    response_model=dict[str, list[FacetCount]],
    summary="Facet counts for filter sidebar",
    tags=["Search"],
)
async def facets(
    q: str = Query(default="", description="Optional query to scope facets"),
) -> dict[str, list[FacetCount]]:
    """Return facet distributions for domain, year, and content_type.

    Pass q to get query-scoped facets (e.g. which domains appear in results for 'python').
    Omit q for global corpus distribution.
    Always returns a dict (empty on error — never raises).
    """
    return get_facet_counts(q)


@app.get(
    "/healthz/live",
    response_model=HealthResponse,
    summary="Liveness probe",
    tags=["Health"],
    include_in_schema=False,
)
async def liveness() -> HealthResponse:
    """Liveness probe — returns 200 if the process is alive."""
    return HealthResponse(status="ok")


@app.get(
    "/healthz/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    tags=["Health"],
    include_in_schema=False,
)
async def readiness(db: Annotated[AsyncSession, Depends(get_db)]) -> HealthResponse:
    """Readiness probe — returns 200 if the app can serve traffic.

    DB failure returns 503 in production, degrades to warning in development.
    """
    try:
        await db.execute(text("SELECT 1"))
        return HealthResponse(status="ok", db="connected")
    except Exception as exc:
        logger.warning("cryo.readiness.db_failed", error=str(exc))
        if settings.is_production:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        return HealthResponse(status="ok", db="unavailable (dev mode)")
