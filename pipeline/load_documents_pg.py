"""Load corpus JSONL files into the PostgreSQL documents table (full text).

Idempotent — re-running skips already-loaded docs (ON CONFLICT DO NOTHING).

Usage:
    python pipeline/load_documents_pg.py
    python pipeline/load_documents_pg.py --data-path data/raw/ --batch-size 500

Prerequisites:
    - PostgreSQL running (docker-compose up -d postgres)
    - Migrations applied (alembic upgrade head)
    - data/raw/*.jsonl exists
"""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from tqdm import tqdm

from backend.db import AsyncSessionLocal
from backend.services.models import Document
from pipeline.ingest_utils import count_words, extract_domain

DEFAULT_BATCH_SIZE = 500


def _row_from_doc(doc: dict) -> dict | None:
    """Map a corpus JSONL doc to a documents-table row. Returns None for malformed docs."""
    text = (doc.get("text") or "").replace("\x00", "")
    doc_id, url = doc.get("id"), doc.get("url")
    if not doc_id or not url or not text:
        return None
    timestamp = str(doc.get("timestamp", ""))[:14] or "20200101120000"
    return {
        "id": str(doc_id)[:16],
        "url": url,
        "text": text,
        "timestamp": timestamp,
        "year": doc.get("year") or int(timestamp[:4]),
        "domain": (doc.get("domain") or extract_domain(url))[:255],
        "word_count": doc.get("word_count") or count_words(text),
        "content_type": (doc.get("content_type") or None),
        "source": "corpus",
    }


async def _insert_batch(rows: list[dict]) -> int:
    """Insert a batch, skipping ids that already exist. Returns rows attempted."""
    if not rows:
        return 0
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(Document).values(rows).on_conflict_do_nothing(index_elements=["id"])
        await session.execute(stmt)
        await session.commit()
    return len(rows)


async def load(data_path: Path, batch_size: int) -> None:
    """Stream all JSONL files under data_path into PostgreSQL."""
    files = sorted(data_path.glob("*.jsonl"))
    if not files:
        raise SystemExit(f"No .jsonl files found in {data_path}")

    total = 0
    for file in files:
        batch: list[dict] = []
        with file.open(encoding="utf-8") as f:
            for line in tqdm(f, desc=file.name, unit=" docs"):
                try:
                    row = _row_from_doc(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if row is None:
                    continue
                batch.append(row)
                if len(batch) >= batch_size:
                    total += await _insert_batch(batch)
                    batch = []
        total += await _insert_batch(batch)
    print(f"[load_documents_pg] Loaded {total} docs from {len(files)} files.")


def main() -> None:
    """Parse args and run the loader."""
    parser = argparse.ArgumentParser(description="Load corpus JSONL into PostgreSQL")
    parser.add_argument("--data-path", type=Path, default=Path("data/raw"))
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()
    asyncio.run(load(args.data_path, args.batch_size))


if __name__ == "__main__":
    main()
