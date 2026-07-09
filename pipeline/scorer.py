"""GPTZero authenticity scoring pipeline.
Scores documents for AI-generated content probability.
Caches results locally (file-based) and in PostgreSQL if available.

Usage:
    python pipeline/scorer.py --input data/raw/batch_000.jsonl --output data/raw/scored.jsonl
"""

import argparse
import json
import os
import time
from pathlib import Path

import structlog
from tqdm import tqdm

from backend.config import settings

logger = structlog.get_logger()

CACHE_DIR = Path("data/cache/scores")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MIN_DOC_LENGTH = 50
RATE_LIMIT_SLEEP = 0.7


def _score_with_gptzero(text: str) -> float | None:
    """Call GPTZero API and return human_score (1 - completely_generated_prob)."""
    import httpx

    api_key = settings.gptzero_api_key or os.environ.get("GPTZERO_API_KEY", "")
    if not api_key:
        return None

    try:
        response = httpx.post(
            "https://api.gptzero.me/v2/predict/text",
            headers={"x-api-key": api_key},
            json={"document": text},
            timeout=30,
        )
        if response.status_code == 429:
            time.sleep(RATE_LIMIT_SLEEP)
            return _score_with_gptzero(text)
        if response.status_code != 200:
            logger.warning("gptzero.api_error", status=response.status_code)
            return None

        data = response.json()
        prob = data.get("documents", [{}])[0].get("completely_generated_prob", None)
        if prob is not None:
            return 1.0 - float(prob)
        return None
    except Exception as exc:
        logger.warning("gptzero.request_error", error=str(exc))
        return None


def _load_cache(doc_id: str) -> float | None:
    path = CACHE_DIR / f"{doc_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text()).get("human_score")
        except Exception:
            return None
    return None


def _save_cache(doc_id: str, human_score: float) -> None:
    path = CACHE_DIR / f"{doc_id}.json"
    try:
        path.write_text(json.dumps({"doc_id": doc_id, "human_score": human_score}))
    except Exception as exc:
        logger.warning("score.cache_write_error", doc_id=doc_id, error=str(exc))


def score_documents(input_path: str, output_path: str, skip_cached: bool = True) -> None:
    """Score all documents in a JSONL file and write scored output."""
    inp = Path(input_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = inp.read_text(encoding="utf-8", errors="replace").strip().split("\n")
    docs = []
    for line in lines:
        if line.strip():
            try:
                docs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    scored = 0
    cached = 0
    skipped = 0
    results = []

    for doc in tqdm(docs, desc="Scoring docs"):
        doc_id = doc.get("id", "")
        cached_score = _load_cache(doc_id)

        if cached_score is not None and skip_cached:
            doc["human_score"] = cached_score
            doc["cryo_certified"] = cached_score >= 0.85
            cached += 1
            results.append(doc)
            continue

        text = doc.get("text", "") or doc.get("text_preview", "") or ""
        if len(text) < MIN_DOC_LENGTH:
            skipped += 1
            results.append(doc)
            continue

        human_score = _score_with_gptzero(text)
        if human_score is not None:
            doc["human_score"] = human_score
            doc["cryo_certified"] = human_score >= 0.85
            _save_cache(doc_id, human_score)
            scored += 1
        else:
            skipped += 1

        results.append(doc)
        time.sleep(RATE_LIMIT_SLEEP)

    with out.open("w", encoding="utf-8") as f:
        for doc in results:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"\n[scorer] Done. {scored} scored, {cached} cached, {skipped} skipped. → {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score docs with GPTZero.")
    parser.add_argument("--input", default="data/raw/batch_000.jsonl")
    parser.add_argument("--output", default="data/raw/scored.jsonl")
    parser.add_argument("--no-cache", action="store_true", help="Re-score even if cached")
    args = parser.parse_args()

    score_documents(
        input_path=args.input,
        output_path=args.output,
        skip_cached=not args.no_cache,
    )


if __name__ == "__main__":
    main()
