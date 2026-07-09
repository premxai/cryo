"""Trajectory collection for RLAIF training.

For each query: semantic search → score with AI judge → save trajectory.
Trajectories are saved as JSONL for offline PPO training.

Usage:
    python training/collect.py --queries 100
    python training/collect.py --queries 500 --output training/trajectories.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, ".")
from backend.judge import RewardScorer
from backend.search import semantic_search

DEFAULT_QUERIES = [
    "machine learning best practices 2020",
    "python async programming guide",
    "climate change renewable energy solutions 2019",
    "startup fundraising advice seed round",
    "deep learning natural language processing survey",
    "remote work productivity tips 2021",
    "bitcoin blockchain technology explained",
    "mental health therapy techniques",
    "kubernetes docker deployment tutorial",
    "history of the internet web development",
    "data science career advice",
    "open source software contributing guide",
    "nutrition science diet research",
    "philosophy consciousness free will",
    "photography composition techniques",
    "economics inequality wealth distribution",
    "cybersecurity password security best practices",
    "urban planning city design",
    "music theory composition fundamentals",
    "writing fiction storytelling craft",
]


def collect_trajectories(
    queries: list[str],
    output_path: str,
    max_docs_per_query: int = 10,
) -> None:
    """Collect trajectories: queries → search → judge → save."""
    scorer = RewardScorer()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    total_pairs = 0
    with out.open("w", encoding="utf-8") as f:
        for query in tqdm(queries, desc="Collecting trajectories"):
            try:
                response = semantic_search(query, limit=max_docs_per_query)
            except Exception as exc:
                tqdm.write(f"[collect] Search failed for '{query}': {exc}")
                continue

            for result in response.results:
                doc = result.model_dump()
                try:
                    score = scorer.score(query, doc)
                except Exception as exc:
                    tqdm.write(f"[collect] Judge failed: {exc}")
                    continue

                traj = {
                    "query": query,
                    "doc_id": doc.get("id", ""),
                    "doc_text": (doc.get("text") or doc.get("text_preview") or "")[:2000],
                    "authenticity": score.authenticity,
                    "relevance": score.relevance,
                    "quality": score.quality,
                    "provenance": score.provenance,
                    "total": score.total,
                }
                f.write(json.dumps(traj, ensure_ascii=False) + "\n")
                total_pairs += 1

    print(f"\n[collect] Done. {total_pairs} (query, doc, reward) pairs saved to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect RLAIF trajectories.")
    parser.add_argument(
        "--queries",
        type=int,
        default=100,
        help="Number of queries to use (cycles through DEFAULT_QUERIES)",
    )
    parser.add_argument("--output", default="training/trajectories.jsonl")
    parser.add_argument("--max-docs", type=int, default=10)
    args = parser.parse_args()

    import itertools

    queries = list(itertools.islice(itertools.cycle(DEFAULT_QUERIES), args.queries))

    collect_trajectories(
        queries=queries,
        output_path=args.output,
        max_docs_per_query=args.max_docs,
    )


if __name__ == "__main__":
    main()
