"""Typed response objects for the Cryo SDK."""

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """A document matched by search or find-similar."""

    id: str
    url: str
    text: str
    published_year: int
    domain: str
    title: str | None = None
    score: float | None = None
    content_type: str | None = None
    human_score: float | None = None
    cryo_certified: bool = False


@dataclass
class ContentsResult:
    """A retrieved page with full archived text."""

    id: str
    url: str
    text: str
    published_year: int
    domain: str
    source: str
    title: str | None = None
    links: list[str] | None = None
    human_score: float | None = None
    cryo_certified: bool = False


@dataclass
class ContentsResponse:
    """Batch page retrieval: per-item results and per-item errors."""

    results: list[ContentsResult]
    errors: list[dict]


@dataclass
class DomainPage:
    """One archived page discovered for a domain."""

    url: str
    timestamp: str
    in_corpus: bool


@dataclass
class Citation:
    """A frozen, provable source backing part of an answer."""

    index: int
    id: str
    url: str
    archive_url: str
    timestamp: str
    human_score: float | None = None
    cryo_certified: bool = False


@dataclass
class Answer:
    """A grounded answer whose every citation predates generative AI."""

    answer: str
    citations: list[Citation]
    model: str
    cached: bool = False


@dataclass
class Usage:
    """Current-month quota consumption for the calling key."""

    month: str
    quota: int
    used: int
    remaining: int
    by_endpoint: dict = field(default_factory=dict)
