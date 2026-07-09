"""Page retrieval for /v1/contents — PG document store first, live Wayback fallback.

Live fetches are written through into the documents table (source='wayback_live'),
permanently growing the frozen corpus. Unfetchable URLs are negative-cached in
Redis so agents hammering a dead link don't hammer archive.org.
"""

import hashlib

import anyio
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.quota import get_redis
from backend.config import settings
from backend.services.models import Document
from backend.services.wayback import fetch_snapshot, url_to_domain
from pipeline.ingest_utils import count_words, make_doc_id

logger = structlog.get_logger()


def _index_in_meili(doc: Document) -> None:
    """Sync helper: add a live-fetched doc to the cryo_docs search index."""
    from backend.search import INDEX_NAME, get_meili_client

    text = doc.text.replace("\x00", "").replace("\r", " ")
    meili_doc = {
        "id": doc.id,
        "url": doc.url,
        "text": text[:2000],
        "text_preview": text[:300],
        "timestamp": doc.timestamp,
        "year": doc.year,
        "domain": doc.domain,
        "word_count": doc.word_count,
        "content_type": doc.content_type or "article",
    }
    if doc.human_score is not None:
        meili_doc["human_score"] = doc.human_score
    get_meili_client().index(INDEX_NAME).add_documents([meili_doc])


async def index_document(doc: Document) -> None:
    """Write a live-fetched doc through to Meilisearch so it becomes searchable.

    Best-effort: a Meili failure never fails the user's /v1/contents request.
    """
    try:
        await anyio.to_thread.run_sync(_index_in_meili, doc)
        logger.info("cryo.contents.indexed", doc_id=doc.id, url=doc.url)
    except Exception as exc:
        logger.warning("cryo.contents.index_failed", doc_id=doc.id, error=str(exc))


async def get_document_by_id(db: AsyncSession, doc_id: str) -> Document | None:
    """Look up a document by its 16-char corpus id."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    return result.scalar_one_or_none()


async def get_document_by_url(db: AsyncSession, url: str) -> Document | None:
    """Look up the most recent stored capture of a URL."""
    result = await db.execute(
        select(Document).where(Document.url == url).order_by(Document.timestamp.desc()).limit(1)
    )
    return result.scalars().first()


def _negative_cache_key(url: str) -> str:
    return "neg:" + hashlib.sha256(url.encode()).hexdigest()[:32]


async def _is_negative_cached(url: str) -> bool:
    """True when a recent fetch of this URL already failed."""
    redis = get_redis()
    if redis is None:
        return False
    return bool(await redis.exists(_negative_cache_key(url)))


async def _negative_cache(url: str) -> None:
    """Remember that this URL is unfetchable for contents_negative_cache_ttl seconds."""
    redis = get_redis()
    if redis is not None:
        await redis.setex(_negative_cache_key(url), settings.contents_negative_cache_ttl, "1")


async def fetch_and_store(db: AsyncSession, url: str, timestamp: str | None) -> Document | None:
    """Live-fetch a URL from the Wayback Machine and write it through to the store."""
    if await _is_negative_cached(url):
        logger.info("cryo.contents.negative_cache_hit", url=url)
        return None

    snapshot = await fetch_snapshot(url, timestamp)
    if snapshot is None:
        await _negative_cache(url)
        return None

    doc = Document(
        id=make_doc_id(snapshot.url, snapshot.timestamp),
        url=snapshot.url,
        text=snapshot.text,
        timestamp=snapshot.timestamp,
        year=int(snapshot.timestamp[:4]),
        domain=url_to_domain(snapshot.url),
        word_count=count_words(snapshot.text),
        content_type="article",
        source="wayback_live",
        links=snapshot.links,
    )
    existing = await get_document_by_id(db, doc.id)
    if existing is not None:
        return existing
    db.add(doc)
    await db.commit()
    logger.info("cryo.contents.stored", url=url, doc_id=doc.id, words=doc.word_count)
    await index_document(doc)  # the corpus grows where users browse
    return doc


async def resolve_url(db: AsyncSession, url: str, timestamp: str | None) -> Document | None:
    """Resolve a URL: stored capture first, then live Wayback fetch."""
    doc = await get_document_by_url(db, url)
    if doc is not None:
        return doc
    return await fetch_and_store(db, url, timestamp)
