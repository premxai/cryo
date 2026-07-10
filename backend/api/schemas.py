"""Pydantic request/response schemas for the /v1 API (Exa-style DX)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    human_score: float | None = Field(
        default=None, description="Judge authenticity score (1.0 = confidently human-written)"
    )
    cryo_certified: bool = Field(default=False, description="True when human_score >= 0.85")


class V1SearchResponse(BaseModel):
    """POST /v1/search response."""

    results: list[V1Result]
    total: int = Field(..., description="Estimated total matches in the corpus")
    search_time_ms: int
    request_id: str


class V1ContentsRequest(BaseModel):
    """POST /v1/contents request body — exactly one of ids or urls."""

    ids: list[str] | None = Field(default=None, max_length=10, description="Corpus document ids")
    urls: list[str] | None = Field(default=None, max_length=10, description="Page URLs to retrieve")
    timestamp: str | None = Field(
        default=None,
        pattern=r"^\d{8}(\d{6})?$",
        description="Preferred snapshot time YYYYMMDD (clamped to pre-2022)",
    )
    include_links: bool = Field(default=True, description="Include outbound article links")

    @model_validator(mode="after")
    def exactly_one_of_ids_or_urls(self) -> "V1ContentsRequest":
        """Require exactly one non-empty selector."""
        if bool(self.ids) == bool(self.urls):
            raise ValueError("Provide exactly one of 'ids' or 'urls' (non-empty)")
        return self


class V1ContentsResult(BaseModel):
    """A retrieved page with full text."""

    id: str
    url: str
    title: str | None = None
    text: str
    published_year: int
    domain: str
    source: str = Field(..., description="'corpus' or 'wayback_live'")
    links: list[str] | None = Field(
        default=None, description="Outbound article links (live fetches only)"
    )
    human_score: float | None = Field(
        default=None, description="Judge authenticity score (1.0 = confidently human-written)"
    )
    cryo_certified: bool = Field(default=False, description="True when human_score >= 0.85")


class V1ContentsError(BaseModel):
    """A per-item retrieval failure — the batch itself never fails."""

    item: str
    reason: str


class V1ContentsResponse(BaseModel):
    """POST /v1/contents response."""

    results: list[V1ContentsResult]
    errors: list[V1ContentsError] = Field(default_factory=list)
    request_id: str


class V1FindSimilarRequest(BaseModel):
    """POST /v1/find-similar request body — exactly one of id or url."""

    id: str | None = Field(default=None, max_length=16, description="Corpus document id")
    url: str | None = Field(default=None, max_length=2000, description="Stored document URL")
    num_results: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def exactly_one_of_id_or_url(self) -> "V1FindSimilarRequest":
        """Require exactly one selector."""
        if bool(self.id) == bool(self.url):
            raise ValueError("Provide exactly one of 'id' or 'url'")
        return self


class V1FindSimilarResponse(BaseModel):
    """POST /v1/find-similar response."""

    source_id: str
    results: list[V1Result]
    search_time_ms: int
    request_id: str


class V1ListDomainRequest(BaseModel):
    """POST /v1/list-domain request body."""

    domain: str = Field(
        ..., min_length=4, max_length=253, description="Domain to enumerate, e.g. paulgraham.com"
    )
    limit: int = Field(default=50, ge=1, le=100)


class V1DomainPage(BaseModel):
    """One archived page discovered for a domain."""

    url: str
    timestamp: str = Field(..., description="Wayback capture time YYYYMMDDHHMMSS")
    in_corpus: bool = Field(..., description="Already stored — /v1/contents serves it instantly")


class V1ListDomainResponse(BaseModel):
    """POST /v1/list-domain response."""

    domain: str
    pages: list[V1DomainPage]
    total: int
    request_id: str


class V1AnswerRequest(BaseModel):
    """POST /v1/answer request body."""

    query: str = Field(..., min_length=3, max_length=500, description="Question to answer")
    num_sources: int = Field(default=6, ge=2, le=10, description="Frozen sources to ground on")

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Strip null bytes and whitespace."""
        v = v.replace("\x00", "").strip()
        if not v:
            raise ValueError("Query is empty after sanitization")
        return v


class V1Citation(BaseModel):
    """A frozen, provable source backing part of an answer."""

    index: int = Field(..., description="Matches [n] markers in the answer text")
    id: str
    url: str
    archive_url: str = Field(..., description="Immutable Wayback Machine link to this capture")
    timestamp: str
    human_score: float | None = None
    cryo_certified: bool = False


class V1AnswerResponse(BaseModel):
    """POST /v1/answer response — every citation predates generative AI."""

    answer: str
    citations: list[V1Citation]
    model: str
    cached: bool
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
