"""/v1/answer — "ask the pre-AI web": grounded answers citing only frozen snapshots.

Search the corpus, feed the top documents to Claude with a strict grounding
prompt, and return an answer whose every citation is a pre-2022 capture with
url, archive link, timestamp, and authenticity score. Answers are file-cached
by query so repeat questions cost nothing.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import anyio
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.errors import APIError
from backend.models import SearchQuery
from backend.search import keyword_search
from backend.services.contents import get_document_by_id

logger = structlog.get_logger()

CACHE_DIR = Path("data/cache/answers")
MAX_CONTEXT_CHARS_PER_DOC = 3000
ANSWER_MAX_TOKENS = 700

_CITATION_RE = re.compile(r"\[(\d+)\]")

_client: Any = None


def _get_client() -> Any:
    """Lazy Anthropic client (same pattern as backend/judge.py)."""
    global _client
    if _client is None:
        try:
            import anthropic

            if not settings.anthropic_api_key:
                return None
            _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        except Exception as exc:
            logger.warning("cryo.answer.client_error", error=str(exc))
            return None
    return _client


def _cache_path(query: str, num_sources: int) -> Path:
    key = hashlib.sha256(f"{query}|{num_sources}".encode()).hexdigest()[:32]
    return CACHE_DIR / f"{key}.json"


def _build_prompt(query: str, sources: list[dict]) -> str:
    """Strict grounding prompt: answer only from the numbered frozen snapshots."""
    blocks = []
    for i, s in enumerate(sources, 1):
        blocks.append(
            f"[{i}] {s['url']} (captured {s['timestamp'][:8]})\n{s['text'][:MAX_CONTEXT_CHARS_PER_DOC]}"
        )
    joined = "\n\n---\n\n".join(blocks)
    return (
        "You answer questions using ONLY the archived pre-2022 web pages below. "
        "These are frozen snapshots that predate generative AI.\n\n"
        f"{joined}\n\n---\n\n"
        f"Question: {query}\n\n"
        "Rules:\n"
        "- Use ONLY information from the sources above; never outside knowledge.\n"
        "- Cite sources inline as [1], [2] etc. after each claim.\n"
        "- If the sources don't answer the question, say so plainly.\n"
        "- 2-4 short paragraphs maximum.\n\n"
        "Answer:"
    )


def _archive_url(url: str, timestamp: str) -> str:
    return f"https://web.archive.org/web/{timestamp}/{url}"


async def _gather_sources(db: AsyncSession, query: str, num_sources: int) -> list[dict]:
    """Hybrid search, then hydrate full text from PG (fallback: search preview)."""
    params = SearchQuery(q=query, limit=num_sources)
    resp = await anyio.to_thread.run_sync(keyword_search, params)
    sources = []
    for r in resp.results:
        doc = await get_document_by_id(db, r.id)
        text = doc.text if doc is not None else re.sub(r"</?mark>", "", r.text_preview)
        sources.append(
            {
                "id": r.id,
                "url": r.url,
                "timestamp": r.timestamp,
                "text": text,
                "human_score": r.human_score,
                "cryo_certified": r.cryo_certified,
            }
        )
    return sources


def _citations_for(answer_text: str, sources: list[dict]) -> list[dict]:
    """Sources actually cited as [n]; falls back to all sources if none parse."""
    cited_nums = {int(n) for n in _CITATION_RE.findall(answer_text)}
    indices = sorted(n for n in cited_nums if 1 <= n <= len(sources)) or range(1, len(sources) + 1)
    return [
        {
            "index": i,
            "id": sources[i - 1]["id"],
            "url": sources[i - 1]["url"],
            "archive_url": _archive_url(sources[i - 1]["url"], sources[i - 1]["timestamp"]),
            "timestamp": sources[i - 1]["timestamp"],
            "human_score": sources[i - 1]["human_score"],
            "cryo_certified": sources[i - 1]["cryo_certified"],
        }
        for i in indices
    ]


async def answer_query(db: AsyncSession, query: str, num_sources: int) -> dict:
    """Answer a question from the frozen corpus with provable citations.

    Raises APIError 503 when no Anthropic key is configured, 404 when the
    corpus has no relevant sources.
    """
    cache = _cache_path(query, num_sources)
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8")) | {"cached": True}
        except Exception:
            pass  # unreadable cache entry — recompute

    client = _get_client()
    if client is None:
        raise APIError(
            503, "answer_unavailable", "Answer generation is not configured on this deployment"
        )

    sources = await _gather_sources(db, query, num_sources)
    if not sources:
        raise APIError(404, "no_sources", "No archived sources found for this question")

    prompt = _build_prompt(query, sources)

    def _call() -> str:
        response = client.messages.create(
            model=settings.judge_model,
            max_tokens=ANSWER_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    try:
        answer_text = await anyio.to_thread.run_sync(_call)
    except Exception as exc:
        logger.error("cryo.answer.model_error", query=query, error=str(exc))
        raise APIError(503, "answer_unavailable", "Answer generation failed — try again") from exc

    result = {
        "answer": answer_text,
        "citations": _citations_for(answer_text, sources),
        "model": settings.judge_model,
        "cached": False,
    }
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result), encoding="utf-8")
    except Exception as exc:
        logger.warning("cryo.answer.cache_write_error", error=str(exc))
    logger.info("cryo.answer", query=query, sources=len(sources), cited=len(result["citations"]))
    return result
