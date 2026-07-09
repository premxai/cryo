"""Score the document corpus for authenticity with the Claude judge (doc-level).

Writes human_score / judge_scores / scored_at to PostgreSQL and pushes
human_score into the Meilisearch index so search results carry it.
Resumable: already-scored docs (scored_at set) are skipped, and judge
responses are file-cached under data/cache/judge/.

Usage:
    python pipeline/score_corpus.py               # score everything unscored
    python pipeline/score_corpus.py --limit 5     # smoke test

Prerequisites:
    - ANTHROPIC_API_KEY in .env
    - PostgreSQL running + alembic upgrade head
    - Meilisearch running (score push is best-effort)
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime

sys.path.insert(0, ".")  # allow `python pipeline/score_corpus.py` from repo root

from sqlalchemy import select
from tqdm import tqdm

from backend.db import AsyncSessionLocal
from backend.judge import RewardScorer
from backend.services.models import Document

COMMIT_EVERY = 25


def _push_scores_to_meili(scored: list[tuple[str, float]]) -> None:
    """Partial-update human_score on already-indexed Meilisearch docs."""
    if not scored:
        return
    try:
        from backend.search import INDEX_NAME, get_meili_client

        index = get_meili_client().index(INDEX_NAME)
        index.update_documents([{"id": doc_id, "human_score": hs} for doc_id, hs in scored])
        print(f"[score_corpus] Pushed {len(scored)} scores to Meilisearch.")
    except Exception as exc:
        print(f"[score_corpus] Meilisearch push failed (non-fatal): {exc}")


async def score_corpus(limit: int | None) -> None:
    """Score all unscored documents and persist the results."""
    scorer = RewardScorer()
    if not scorer.has_client():
        raise SystemExit(
            "[score_corpus] No Anthropic client — set ANTHROPIC_API_KEY in .env first."
        )

    async with AsyncSessionLocal() as session:
        stmt = select(Document).where(Document.scored_at.is_(None)).order_by(Document.id)
        if limit:
            stmt = stmt.limit(limit)
        docs = (await session.execute(stmt)).scalars().all()
        if not docs:
            print("[score_corpus] Nothing to score — all documents already scored.")
            return

        scored_for_meili: list[tuple[str, float]] = []
        for i, doc in enumerate(tqdm(docs, desc="scoring", unit=" docs")):
            score = scorer.score_document(
                {"id": doc.id, "url": doc.url, "text": doc.text, "timestamp": doc.timestamp}
            )
            doc.human_score = score.authenticity
            doc.judge_scores = score.model_dump()
            doc.scored_at = datetime.now(UTC)
            scored_for_meili.append((doc.id, score.authenticity))
            if (i + 1) % COMMIT_EVERY == 0:
                await session.commit()
        await session.commit()

    _push_scores_to_meili(scored_for_meili)
    print(f"[score_corpus] Scored {len(docs)} documents.")


def main() -> None:
    """Parse args and run the scorer."""
    parser = argparse.ArgumentParser(description="Judge-score the Cryo document corpus")
    parser.add_argument("--limit", type=int, default=None, help="Max docs to score this run")
    args = parser.parse_args()
    asyncio.run(score_corpus(args.limit))


if __name__ == "__main__":
    main()
