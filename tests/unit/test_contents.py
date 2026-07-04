"""Unit tests for the contents service — live fetch, write-through, negative cache."""

from unittest.mock import AsyncMock, MagicMock, patch

from backend.services import contents
from backend.services.wayback import Snapshot


def _db_without_existing_doc():
    """AsyncMock session whose lookups return no existing document."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    return db


async def test_fetch_and_store_writes_through_to_meili(monkeypatch):
    """A live Wayback fetch is stored in PG and indexed into Meilisearch."""
    monkeypatch.setattr(contents, "get_redis", lambda: None)
    snapshot = Snapshot(
        url="https://example.com/2019/essay",
        timestamp="20190601000000",
        text="word " * 100,
        links=["https://example.com/2018/other"],
    )
    db = _db_without_existing_doc()
    with (
        patch.object(contents, "fetch_snapshot", new=AsyncMock(return_value=snapshot)),
        patch.object(contents, "_index_in_meili") as mock_index,
    ):
        doc = await contents.fetch_and_store(db, snapshot.url, None)

    assert doc is not None
    assert doc.source == "wayback_live"
    assert doc.year == 2019
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    mock_index.assert_called_once()
    indexed_doc = mock_index.call_args.args[0]
    assert indexed_doc.id == doc.id


async def test_fetch_and_store_negative_caches_misses(monkeypatch):
    """A URL with no pre-2022 snapshot is negative-cached and returns None."""
    redis = AsyncMock()
    redis.exists.return_value = 0
    monkeypatch.setattr(contents, "get_redis", lambda: redis)
    db = _db_without_existing_doc()
    with patch.object(contents, "fetch_snapshot", new=AsyncMock(return_value=None)):
        doc = await contents.fetch_and_store(db, "https://example.com/gone", None)

    assert doc is None
    redis.setex.assert_awaited_once()
    db.add.assert_not_called()
