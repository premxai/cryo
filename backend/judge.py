"""Claude API reward scorer for RLAIF.
Scores search results on 4 dimensions: authenticity, relevance, quality, provenance.
Caches all scores in PostgreSQL (falls back to file cache if DB unavailable).
"""

import json
import os
from pathlib import Path
from typing import Any

import structlog

from backend.config import settings
from backend.models import RewardScore

logger = structlog.get_logger()

REWARD_WEIGHTS = {
    "authenticity": 0.40,
    "relevance": 0.30,
    "quality": 0.20,
    "provenance": 0.10,
}

# Doc-level scoring (no query, so no relevance) — REWARD_WEIGHTS renormalized
DOC_WEIGHTS = {
    "authenticity": 0.57,
    "quality": 0.29,
    "provenance": 0.14,
}
DOC_QUERY_SENTINEL = "__doc__"  # cache key namespace for query-less scores

CACHE_DIR = Path("data/cache/judge")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class RewardScorer:
    """Scores a (query, doc) pair using Claude API with file-based caching."""

    def __init__(self) -> None:
        self._client: Any = None
        self._model = settings.judge_model

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic

                api_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
                if not api_key:
                    logger.warning("cryo.judge.no_api_key")
                    return None
                self._client = anthropic.Anthropic(api_key=api_key)
            except Exception as exc:
                logger.warning("cryo.judge.client_error", error=str(exc))
                return None
        return self._client

    def _cache_path(self, doc_id: str, query: str) -> Path:
        key = f"{doc_id}|{query}"
        import hashlib

        h = hashlib.sha256(key.encode()).hexdigest()[:32]
        return CACHE_DIR / f"{h}.json"

    def _load_cache(self, doc_id: str, query: str) -> RewardScore | None:
        path = self._cache_path(doc_id, query)
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return RewardScore(**data)
            except Exception:
                return None
        return None

    def _save_cache(self, doc_id: str, query: str, score: RewardScore) -> None:
        path = self._cache_path(doc_id, query)
        try:
            path.write_text(json.dumps(score.model_dump(), indent=2))
        except Exception as exc:
            logger.warning("cryo.judge.cache_write_error", error=str(exc))

    def _build_prompt(self, query: str, doc: dict) -> str:
        text = (doc.get("text") or doc.get("text_preview") or "")[:1000]
        human_score = doc.get("human_score", "N/A")
        return (
            "You are evaluating search results for Cryo, a search engine "
            "for authentic pre-AI human content.\n\n"
            f"Query: {query}\n"
            f"Document URL: {doc.get('url', 'N/A')}\n"
            f"Document timestamp: {doc.get('timestamp', 'N/A')}\n"
            f"Document text: {text}\n"
            f"GPTZero human score: {human_score}\n\n"
            "Rate this document 0.0 to 1.0 on each dimension:\n"
            "1. authenticity: Is this genuinely human-written? (use GPTZero score + writing style)\n"
            "2. relevance: Does this document answer the query well?\n"
            "3. quality: Is this substantive, well-reasoned, worth reading?\n"
            "4. provenance: Is the timestamp credible? Does the content match the era?\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"authenticity": 0.0, "relevance": 0.0, "quality": 0.0, "provenance": 0.0}'
        )

    def score(self, query: str, doc: dict) -> RewardScore:
        doc_id = doc.get("id", "")
        cached = self._load_cache(doc_id, query)
        if cached is not None:
            return cached

        client = self._get_client()
        if client is None:
            fallback = self._fallback_score(doc)
            self._save_cache(doc_id, query, fallback)
            return fallback

        prompt = self._build_prompt(query, doc)
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            score = RewardScore(
                authenticity=float(data.get("authenticity", 0)),
                relevance=float(data.get("relevance", 0)),
                quality=float(data.get("quality", 0)),
                provenance=float(data.get("provenance", 0)),
            )
        except Exception as exc:
            logger.warning("cryo.judge.score_error", doc_id=doc_id, error=str(exc))
            score = self._fallback_score(doc)

        score.total = (
            REWARD_WEIGHTS["authenticity"] * score.authenticity
            + REWARD_WEIGHTS["relevance"] * score.relevance
            + REWARD_WEIGHTS["quality"] * score.quality
            + REWARD_WEIGHTS["provenance"] * score.provenance
        )
        self._save_cache(doc_id, query, score)
        return score

    def has_client(self) -> bool:
        """True when an Anthropic client is available (API key configured)."""
        return self._get_client() is not None

    def _build_doc_prompt(self, doc: dict) -> str:
        """Query-less prompt: rate the document itself, not its fit to a search."""
        text = (doc.get("text") or doc.get("text_preview") or "")[:1500]
        return (
            "You are auditing a document for Cryo, a verified archive of "
            "pre-2022, authentically human-written web content.\n\n"
            f"Document URL: {doc.get('url', 'N/A')}\n"
            f"Document timestamp: {doc.get('timestamp', 'N/A')}\n"
            f"Document text: {text}\n\n"
            "Rate this document 0.0 to 1.0 on each dimension:\n"
            "1. authenticity: Is this genuinely human-written (not AI-generated, "
            "not machine-translated boilerplate, not scraped spam)?\n"
            "2. quality: Is this substantive, coherent, worth preserving?\n"
            "3. provenance: Is the timestamp credible? Does style/content match the era?\n\n"
            "Respond ONLY with valid JSON:\n"
            '{"authenticity": 0.0, "quality": 0.0, "provenance": 0.0}'
        )

    def score_document(self, doc: dict) -> RewardScore:
        """Score a document without a query (relevance = 0, excluded from total).

        Used by pipeline/score_corpus.py to build the verified-corpus proof pack.
        Cached under the __doc__ namespace; never caches fallback scores, so a
        missing API key doesn't poison the cache.
        """
        doc_id = doc.get("id", "")
        cached = self._load_cache(doc_id, DOC_QUERY_SENTINEL)
        if cached is not None:
            return cached

        client = self._get_client()
        if client is None:
            return self._fallback_score(doc)

        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=200,
                messages=[{"role": "user", "content": self._build_doc_prompt(doc)}],
            )
            raw = response.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw)
            score = RewardScore(
                authenticity=float(data.get("authenticity", 0)),
                relevance=0.0,
                quality=float(data.get("quality", 0)),
                provenance=float(data.get("provenance", 0)),
            )
        except Exception as exc:
            logger.warning("cryo.judge.doc_score_error", doc_id=doc_id, error=str(exc))
            return self._fallback_score(doc)

        score.total = round(
            DOC_WEIGHTS["authenticity"] * score.authenticity
            + DOC_WEIGHTS["quality"] * score.quality
            + DOC_WEIGHTS["provenance"] * score.provenance,
            4,
        )
        self._save_cache(doc_id, DOC_QUERY_SENTINEL, score)
        return score

    def _fallback_score(self, doc: dict) -> RewardScore:
        human_score = doc.get("human_score")
        if human_score is not None:
            return RewardScore(
                authenticity=human_score,
                relevance=0.5,
                quality=0.5,
                provenance=0.5,
                total=(0.40 * human_score + 0.30 * 0.5 + 0.20 * 0.5 + 0.10 * 0.5),
            )
        return RewardScore(total=0.5)
