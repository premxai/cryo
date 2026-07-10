"""Export the scored corpus as an auditable dataset sample (the proof pack).

Writes:
    data/export/cryo_sample_v1.jsonl  — one scored document per line
    data/export/stats.json            — corpus composition + score distribution

Usage:
    python pipeline/export_dataset.py
    python pipeline/export_dataset.py --min-score 0.85 --limit 10000

Prerequisites:
    - PostgreSQL running, documents scored (pipeline/score_corpus.py)
"""

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, ".")  # allow `python pipeline/export_dataset.py` from repo root

from sqlalchemy import select

from backend.db import AsyncSessionLocal
from backend.services.models import Document

EXPORT_DIR = Path("data/export")


def _doc_row(doc: Document) -> dict:
    """The exported shape — everything a buyer needs to audit a document."""
    return {
        "id": doc.id,
        "url": doc.url,
        "text": doc.text,
        "timestamp": doc.timestamp,
        "year": doc.year,
        "domain": doc.domain,
        "source": doc.source,
        "word_count": doc.word_count,
        "content_type": doc.content_type,
        "human_score": doc.human_score,
        "judge_scores": doc.judge_scores,
        "scored_at": doc.scored_at.isoformat() if doc.scored_at else None,
    }


def _score_bucket(score: float) -> str:
    """Histogram bucket label like '0.8-0.9'."""
    low = min(int(score * 10) / 10, 0.9)
    return f"{low:.1f}-{low + 0.1:.1f}"


def _build_stats(rows: list[dict]) -> dict:
    """Composition + score-distribution summary for stats.json."""
    scores = [r["human_score"] for r in rows if r["human_score"] is not None]
    return {
        "total_documents": len(rows),
        "scored_documents": len(scores),
        "by_source": dict(Counter(r["source"] for r in rows)),
        "by_year": dict(sorted(Counter(r["year"] for r in rows).items())),
        "by_content_type": dict(Counter(r["content_type"] or "unknown" for r in rows)),
        "score_distribution": dict(sorted(Counter(_score_bucket(s) for s in scores).items())),
        "mean_human_score": round(sum(scores) / len(scores), 4) if scores else None,
        "certified_count": sum(1 for s in scores if s >= 0.85),
    }


async def export(min_score: float | None, limit: int | None) -> None:
    """Write the JSONL sample and stats file."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    async with AsyncSessionLocal() as session:
        stmt = select(Document).where(Document.scored_at.is_not(None)).order_by(Document.id)
        if min_score is not None:
            stmt = stmt.where(Document.human_score >= min_score)
        if limit:
            stmt = stmt.limit(limit)
        docs = (await session.execute(stmt)).scalars().all()

    if not docs:
        raise SystemExit("[export] No scored documents — run pipeline/score_corpus.py first.")

    rows = [_doc_row(d) for d in docs]
    sample_path = EXPORT_DIR / "cryo_sample_v1.jsonl"
    with sample_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats = _build_stats(rows)
    (EXPORT_DIR / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"[export] Wrote {len(rows)} docs to {sample_path}")
    print(f"[export] Stats: {json.dumps(stats, indent=2)[:400]}")


def main() -> None:
    """Parse args and run the export."""
    parser = argparse.ArgumentParser(description="Export the scored Cryo corpus sample")
    parser.add_argument(
        "--min-score", type=float, default=None, help="Only docs at/above this human_score"
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap exported doc count")
    args = parser.parse_args()
    asyncio.run(export(args.min_score, args.limit))


if __name__ == "__main__":
    main()
