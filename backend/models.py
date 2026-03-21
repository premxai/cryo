"""Pydantic v2 request/response schemas for the Cryo API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SearchQuery(BaseModel):
    """Validated query parameters for keyword search."""

    q: str = Field(..., min_length=1, max_length=500, description="Search query")
    year_min: int = Field(default=2000, ge=2000, le=2021, description="Earliest year to include")
    year_max: int = Field(default=2021, ge=2000, le=2021, description="Latest year to include")
    limit: int = Field(default=20, ge=1, le=50, description="Results per page")
    offset: int = Field(default=0, ge=0, le=1000, description="Pagination offset")
    sort: Literal["relevance", "date_desc", "date_asc"] = Field(
        default="relevance", description="Sort order"
    )
    domain: str | None = Field(default=None, max_length=100, description="Filter by domain")
    content_type: Literal["article", "encyclopedia", "discussion", "qa", "blog"] | None = Field(
        default=None, description="Filter by content type"
    )

    @field_validator("q")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Strip null bytes and leading/trailing whitespace."""
        v = v.replace("\x00", "").strip()
        if not v:
            raise ValueError("Query is empty after sanitization")
        return v

    @field_validator("domain")
    @classmethod
    def sanitize_domain(cls, v: str | None) -> str | None:
        """Strip quotes and whitespace from domain filter to prevent injection."""
        if v is None:
            return v
        return v.replace('"', "").replace("'", "").strip() or None

    @field_validator("year_max")
    @classmethod
    def year_max_gte_year_min(cls, v: int, info) -> int:
        """Ensure year_max >= year_min (validated after year_min is set)."""
        year_min = (info.data or {}).get("year_min", 2000)
        if v < year_min:
            raise ValueError(f"year_max ({v}) must be >= year_min ({year_min})")
        return v


class FacetCount(BaseModel):
    """A single facet value and its document count."""

    value: str
    count: int


class SearchResult(BaseModel):
    """A single search result returned to the client."""

    id: str
    url: str
    text_preview: str = Field(..., description="First 300 chars or highlighted snippet")
    timestamp: str
    year: int
    domain: str
    word_count: int | None = None
    content_type: str | None = None

    # Populated in M2 (authenticity scoring)
    human_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Composite authenticity score (1.0 = fully human)",
    )
    cryo_certified: bool = Field(
        default=False,
        description="True if human_score >= 0.85",
    )

    # Populated in M4 (RLAIF judge scoring)
    reward_scores: dict | None = None


class SearchResponse(BaseModel):
    """Top-level response from /search."""

    query: str
    results: list[SearchResult]
    total: int = Field(..., description="Total matches in index (may exceed returned results)")
    search_time_ms: int
    facets: dict[str, list[FacetCount]] = Field(
        default_factory=dict,
        description="Facet counts for domain, year, content_type",
    )


class HealthResponse(BaseModel):
    """Response from /healthz/* endpoints."""

    status: str
    db: str | None = None
