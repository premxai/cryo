"""/v1/find-similar — semantically similar documents via Meilisearch + fastembed rerank.

The Qdrant path is unavailable in production (sentence-transformers is an
optional ml extra), so similarity = salient-term BM25 recall re-ranked by
cosine similarity against the source document text.
"""

import re
from collections import Counter

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import SearchResult
from backend.search import INDEX_NAME, _cosine_scores, _hit_to_result, get_meili_client
from backend.services.contents import get_document_by_id, get_document_by_url

logger = structlog.get_logger()

RERANK_CANDIDATES = 50
SALIENT_TERMS = 8
_WORD_RE = re.compile(r"[a-z][a-z\-]{2,}")
_STOPWORDS = frozenset(
    ["the", "and", "for", "that", "with", "this", "from", "was", "were", "are", "has", "have", "had", "not", "but", "all", "can", "its", "you", "your", "they", "their", "our", "out", "very", "will", "would", "there", "been", "being", "about", "into", "more", "other", "some", "such", "than", "then", "them", "these", "those", "when", "where", "which", "while", "who", "whom", "why", "how", "what", "over", "under", "between", "because", "during", "before", "after", "above", "below", "just", "also"]
)


def salient_terms(text: str, limit: int = SALIENT_TERMS) -> str:
    """Extract the most frequent non-stopword terms — the BM25 recall query."""
    words = _WORD_RE.findall(text.lower()[:5000])
    counts = Counter(w for w in words if w not in _STOPWORDS)
    return " ".join(term for term, _ in counts.most_common(limit))


async def _source_text(db: AsyncSession, doc_id: str | None, url: str | None) -> tuple[str, str]:
    """Return (source_id, source_text) for the reference document.

    Tries the PG document store first, then the Meilisearch index (preview text).
    Raises ValueError when the document cannot be found.
    """
    if doc_id:
        doc = await get_document_by_id(db, doc_id)
        if doc is not None:
            return doc.id, doc.text
        hit = _meili_get(doc_id)
        if hit is not None:
            return doc_id, hit.get("text_preview", "")
        raise ValueError(f"Document '{doc_id}' not found")
    doc = await get_document_by_url(db, url or "")
    if doc is None:
        raise ValueError(f"No stored document for URL '{url}' — fetch it via /v1/contents first")
    return doc.id, doc.text


def _meili_get(doc_id: str) -> dict | None:
    """Fetch a single document from Meilisearch by id filter."""
    try:
        raw = get_meili_client().index(INDEX_NAME).search("", {"filter": f'id = "{doc_id}"', "limit": 1})
        hits = raw.get("hits", [])
        return hits[0] if hits else None
    except Exception as exc:
        logger.warning("cryo.similar.meili_get_failed", doc_id=doc_id, error=str(exc))
        return None


async def find_similar(
    db: AsyncSession,
    doc_id: str | None,
    url: str | None,
    num_results: int = 10,
) -> tuple[str, list[SearchResult]]:
    """Return (source_id, results) — documents most similar to the reference doc."""
    source_id, text = await _source_text(db, doc_id, url)
    query = salient_terms(text)
    if not query:
        return source_id, []

    index = get_meili_client().index(INDEX_NAME)
    raw = index.search(query, {"limit": RERANK_CANDIDATES, "attributesToHighlight": []})
    hits = [h for h in raw.get("hits", []) if h.get("id") != source_id]
    if not hits:
        return source_id, []

    scores = _cosine_scores(text[:2000], [h.get("text_preview", "") or "" for h in hits])
    for h, s in zip(hits, scores, strict=True):
        h["_cryo_score"] = round(s, 4)
    hits.sort(key=lambda h: h["_cryo_score"], reverse=True)

    logger.info("cryo.similar", source_id=source_id, candidates=len(hits), query=query)
    return source_id, [_hit_to_result(h) for h in hits[:num_results]]
