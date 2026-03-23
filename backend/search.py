"""Search logic — BM25 keyword search (Meilisearch) + semantic re-ranking (fastembed)."""

import time
from typing import Any

import meilisearch
import structlog

from backend.config import settings
from backend.models import FacetCount, SearchQuery, SearchResponse, SearchResult

logger = structlog.get_logger()

INDEX_NAME = "cryo_docs"
RERANK_CANDIDATES = 50  # fetch this many from BM25, re-rank, return top N

_meili_client: meilisearch.Client | None = None
_embed_model: Any = None  # lazy-loaded fastembed model


def _get_embed_model():
    """Lazily load the fastembed model (downloads ~40MB on first call)."""
    global _embed_model
    if _embed_model is None:
        try:
            from fastembed import TextEmbedding

            _embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            logger.info("cryo.search.embed_model_loaded", model="BAAI/bge-small-en-v1.5")
        except Exception as exc:
            logger.warning("cryo.search.embed_unavailable", error=str(exc))
            _embed_model = None
    return _embed_model


def _cosine_scores(query: str, texts: list[str]) -> list[float]:
    """Return cosine similarity scores between query and each text. Falls back to 0.0."""
    model = _get_embed_model()
    if model is None or not texts:
        return [0.0] * len(texts)
    try:
        import numpy as np

        all_texts = [query] + texts
        vecs = list(model.embed(all_texts))
        q_vec = np.array(vecs[0])
        doc_vecs = np.array(vecs[1:])
        q_norm = np.linalg.norm(q_vec)
        doc_norms = np.linalg.norm(doc_vecs, axis=1)
        if q_norm == 0:
            return [0.0] * len(texts)
        sims = doc_vecs @ q_vec / (doc_norms * q_norm + 1e-9)
        return sims.tolist()
    except Exception as exc:
        logger.warning("cryo.search.rerank_error", error=str(exc))
        return [0.0] * len(texts)


def get_meili_client() -> meilisearch.Client:
    """Return (and lazily create) the Meilisearch client."""
    global _meili_client
    if _meili_client is None:
        _meili_client = meilisearch.Client(settings.meilisearch_url, settings.meilisearch_key)
    return _meili_client


def verify_meilisearch() -> bool:
    """Return True if Meilisearch is reachable. Called at startup."""
    try:
        get_meili_client().health()
        return True
    except Exception as exc:
        logger.warning("cryo.search.meili_unreachable", error=str(exc))
        return False


def _build_filter(params: SearchQuery) -> str:
    """Build a Meilisearch filter expression from query parameters."""
    parts: list[str] = [
        f"year >= {params.year_min}",
        f"year <= {params.year_max}",
    ]
    if params.domain:
        escaped = params.domain.replace('"', '\\"')
        parts.append(f'domain = "{escaped}"')
    if params.content_type:
        parts.append(f'content_type = "{params.content_type}"')
    return " AND ".join(parts)


def _build_sort(sort: str) -> list[str]:
    """Map sort param to Meilisearch sort rules."""
    if sort == "date_desc":
        return ["year:desc"]
    if sort == "date_asc":
        return ["year:asc"]
    return []  # relevance = Meilisearch default ranking


def _parse_facets(raw_facets: dict) -> dict[str, list[FacetCount]]:
    """Convert Meilisearch facet distribution to FacetCount lists."""
    result: dict[str, list[FacetCount]] = {}
    for facet_name, values in raw_facets.items():
        result[facet_name] = [
            FacetCount(value=str(v), count=c)
            for v, c in sorted(values.items(), key=lambda x: -x[1])
        ]
    return result


def _hit_to_result(h: dict) -> SearchResult:
    """Convert a Meilisearch hit (with optional _formatted) to SearchResult."""
    formatted = h.get("_formatted", {})
    # Use highlighted snippet if available, fall back to stored preview
    preview = formatted.get("text_preview") or h.get("text_preview", "")
    return SearchResult(
        id=h["id"],
        url=h.get("url", ""),
        text_preview=preview[:600],  # allow more room for highlighted snippets
        timestamp=h.get("timestamp", ""),
        year=h.get("year", 0),
        domain=h.get("domain", ""),
        word_count=h.get("word_count"),
        content_type=h.get("content_type"),
    )


def keyword_search(params: SearchQuery) -> SearchResponse:
    """BM25 search with semantic re-ranking over the pre-2022 corpus.

    Fetches up to RERANK_CANDIDATES from Meilisearch, re-ranks by cosine
    similarity using fastembed, then returns params.limit results.

    Args:
        params: Validated SearchQuery with all filter/sort/pagination options.

    Returns:
        SearchResponse with matched documents, facets, and timing.
    """
    client = get_meili_client()
    index = client.index(INDEX_NAME)
    start_ms = int(time.time() * 1000)

    # Fetch more candidates when re-ranking by relevance
    use_rerank = params.sort == "relevance"
    fetch_limit = RERANK_CANDIDATES if use_rerank else params.limit

    search_params: dict = {
        "limit": fetch_limit,
        "offset": params.offset if not use_rerank else 0,
        "filter": _build_filter(params),
        "facets": ["domain", "year", "content_type"],
        "attributesToRetrieve": [
            "id",
            "url",
            "text_preview",
            "timestamp",
            "year",
            "domain",
            "word_count",
            "content_type",
        ],
        "attributesToHighlight": ["text_preview"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
        "cropLength": 200,
        "attributesToCrop": ["text_preview"],
    }

    sort = _build_sort(params.sort)
    if sort:
        search_params["sort"] = sort

    try:
        raw = index.search(params.q, search_params)
    except Exception as exc:
        logger.error("cryo.search.meili_error", query=params.q, error=str(exc))
        raise

    hits = raw.get("hits", [])

    # Semantic re-ranking — only on relevance sort
    if use_rerank and hits and _get_embed_model() is not None:
        texts = [h.get("text_preview", "") or "" for h in hits]
        scores = _cosine_scores(params.q, texts)
        # Combine: 0.5 × BM25_rank_score + 0.5 × cosine_sim
        n = len(hits)
        ranked = sorted(
            ((h, s, i) for i, (h, s) in enumerate(zip(hits, scores, strict=True))),
            key=lambda t: 0.5 * (1 - t[2] / n) + 0.5 * t[1],
            reverse=True,
        )
        hits = [h for h, _, _ in ranked]
        # Apply pagination after re-ranking
        hits = hits[params.offset : params.offset + params.limit]
    else:
        hits = hits[: params.limit]

    elapsed = int(time.time() * 1000) - start_ms
    results = [_hit_to_result(h) for h in hits]
    facets = _parse_facets(raw.get("facetDistribution") or {})

    logger.info(
        "cryo.search.keyword",
        query=params.q,
        hits=len(results),
        total=raw.get("estimatedTotalHits", 0),
        elapsed_ms=elapsed,
        offset=params.offset,
        sort=params.sort,
        reranked=use_rerank,
    )

    return SearchResponse(
        query=params.q,
        results=results,
        total=raw.get("estimatedTotalHits", 0),
        search_time_ms=elapsed,
        facets=facets,
    )


def suggest_completions(q: str, limit: int = 8) -> list[str]:
    """Return autocomplete suggestions by searching domains + common prefixes.

    Uses a lightweight search with domain facets to extract suggestions.
    Falls back to empty list on any error — never raises.

    Args:
        q: Partial query string to complete.
        limit: Maximum number of suggestions.

    Returns:
        List of suggestion strings.
    """
    try:
        client = get_meili_client()
        index = client.index(INDEX_NAME)
        raw = index.search(
            q,
            {
                "limit": limit * 2,
                "attributesToRetrieve": ["text_preview"],
                "attributesToHighlight": [],
                "facets": ["domain"],
            },
        )
        # Extract unique multi-word phrases from previews that start with q
        suggestions: list[str] = []
        q_lower = q.lower()
        seen: set[str] = set()
        for hit in raw.get("hits", []):
            preview = hit.get("text_preview", "")
            words = preview.split()
            for i, word in enumerate(words):
                if word.lower().startswith(q_lower) and i + 1 < len(words):
                    phrase = f"{word} {words[i + 1]}".lower()
                    if phrase not in seen and len(phrase) > len(q):
                        suggestions.append(phrase)
                        seen.add(phrase)
                        if len(suggestions) >= limit:
                            return suggestions
        return suggestions[:limit]
    except Exception as exc:
        logger.warning("cryo.search.suggest_error", q=q, error=str(exc))
        return []


def get_facet_counts(q: str = "") -> dict[str, list[FacetCount]]:
    """Return facet distributions for a query (or global if q is empty).

    Args:
        q: Optional query to scope facets. Empty string = global distribution.

    Returns:
        Dict mapping facet name to list of FacetCount objects.
    """
    try:
        client = get_meili_client()
        index = client.index(INDEX_NAME)
        raw = index.search(
            q or "",
            {
                "limit": 0,
                "facets": ["domain", "year", "content_type"],
            },
        )
        return _parse_facets(raw.get("facetDistribution") or {})
    except Exception as exc:
        logger.warning("cryo.search.facets_error", q=q, error=str(exc))
        return {}
