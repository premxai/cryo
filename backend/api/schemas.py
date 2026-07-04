"""Pydantic request/response schemas for the /v1 API (Exa-style DX)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class V1SearchRequest(BaseModel):
    """POST /v1/search request body."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    num_results: int = Field(default=10, ge=1, le=50, description="Number of results")
    year_min: int = Field(default=2000, ge=2000, le=2021, description="Earliest year")
    year_max: int = Field(default=2021, ge=2000, le=2021, description="Latest year")
    domain: str | None = Field(default=None, max_length=100, description="Filter by domain")
    content_type: Literal["article", "encyclopedia", "discussion", "qa", "blog"] | None = Field(
        default=None, description="Filter by content type"
    )

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Strip null bytes and whitespace."""
        v = v.replace("\x00", "").strip()
        if not v:
            raise ValueError("Query is empty after sanitization")
        return v


class V1Result(BaseModel):
    """A single document in a /v1 search-shaped response."""

    id: str
    url: str
    title: str | None = Field(default=None, description="Best-effort title from the URL slug")
    text: str = Field(..., description="Matched text snippet")
    score: float | None = Field(default=None, description="Combined BM25+semantic score")
    published_year: int
    domain: str
    content_type: str | None = None


class V1SearchResponse(BaseModel):
    """POST /v1/search response."""

    results: list[V1Result]
    total: int = Field(..., description="Estimated total matches in the corpus")
    search_time_ms: int
    request_id: str


class V1UsageResponse(BaseModel):
    """GET /v1/usage response — current month consumption from the durable ledger."""

    month: str
    quota: int
    used: int
    remaining: int
    by_endpoint: dict[str, int] = Field(default_factory=dict)


class V1ErrorBody(BaseModel):
    """Inner error object returned on every /v1 error."""

    type: str
    message: str
    request_id: str


class V1Error(BaseModel):
    """Top-level error envelope: {"error": {type, message, request_id}}."""

    error: V1ErrorBody
