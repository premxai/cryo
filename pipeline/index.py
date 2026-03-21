"""Index downloaded JSONL docs into Meilisearch.

Usage:
    python pipeline/index.py
    python pipeline/index.py --data-path data/raw/ --batch-size 1000

Prerequisites:
    - Meilisearch running: docker-compose up -d meilisearch
    - data/raw/*.jsonl exists (run download.py first)
    - Run validate.py before this to catch corrupt data early
"""

import argparse
import json
from pathlib import Path

import meilisearch
from tqdm import tqdm

from backend.config import settings

INDEX_NAME = "cryo_docs"
DEFAULT_BATCH_SIZE = 1000


def get_client() -> meilisearch.Client:
    """Create and verify Meilisearch client."""
    client = meilisearch.Client(settings.meilisearch_url, settings.meilisearch_key)
    try:
        client.health()
    except Exception as exc:
        raise RuntimeError(
            f"Cannot connect to Meilisearch at {settings.meilisearch_url}. "
            "Is it running? Try: docker-compose up -d meilisearch"
        ) from exc
    return client


def configure_index(client: meilisearch.Client) -> meilisearch.index.Index:
    """Create index if it doesn't exist and configure searchable/filterable fields."""
    index = client.index(INDEX_NAME)

    # Create index if needed (idempotent — safe to re-run)
    try:
        client.create_index(INDEX_NAME, {"primaryKey": "id"})
        print(f"[index] Created index '{INDEX_NAME}'.")
    except meilisearch.errors.MeilisearchApiError as exc:
        if "index_already_exists" in str(exc):
            print(f"[index] Index '{INDEX_NAME}' already exists — skipping creation.")
        else:
            raise

    # Configure fields
    index.update_searchable_attributes(["text", "url", "domain"])
    index.update_filterable_attributes(["year", "domain", "content_type"])
    index.update_sortable_attributes(["year"])

    # Faceting: expose top 20 values per facet
    index.update_faceting_settings({"maxValuesPerFacet": 20})

    # Note: highlightPreTag/highlightPostTag are set per-query in search.py,
    # not as index settings. Meilisearch doesn't support them in update_settings.

    # Ranking: boost recent pre-2022 content
    index.update_ranking_rules([
        "words",
        "typo",
        "proximity",
        "attribute",
        "sort",
        "exactness",
    ])

    print("[index] Index configured.")
    return index


def stream_docs(data_path: Path):
    """Yield all docs from all JSONL files in the data directory."""
    jsonl_files = sorted(data_path.glob("*.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"No JSONL files found in {data_path}")

    for jsonl_file in jsonl_files:
        with jsonl_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue


def index_documents(data_path: str, batch_size: int) -> None:
    """Main indexing loop — reads JSONL files and bulk-inserts into Meilisearch."""
    path = Path(data_path)
    client = get_client()
    index = configure_index(client)

    batch: list[dict] = []
    total_indexed = 0
    batch_num = 0

    with tqdm(desc="Indexing docs", unit="doc") as pbar:
        for doc in stream_docs(path):
            # Compute text_preview; ensure content_type has a default
            doc["text_preview"] = doc["text"][:300]
            doc.setdefault("content_type", "article")
            batch.append(doc)

            if len(batch) >= batch_size:
                task = index.add_documents(batch)
                total_indexed += len(batch)
                pbar.update(len(batch))
                batch_num += 1
                batch = []

                if batch_num % 10 == 0:
                    print(f"[index] {total_indexed:,} docs indexed so far...")

        # Final partial batch
        if batch:
            index.add_documents(batch)
            total_indexed += len(batch)
            pbar.update(len(batch))

    print(f"\n[index] Done. {total_indexed:,} documents indexed into '{INDEX_NAME}'.")
    print(f"[index] Meilisearch URL: {settings.meilisearch_url}")
    print("[index] Test with: curl 'localhost:7700/indexes/cryo_docs/search?q=machine+learning'")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Index JSONL docs into Meilisearch.")
    parser.add_argument("--data-path", type=str, default="data/raw", help="Path to JSONL files.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Docs per batch.")
    args = parser.parse_args()

    index_documents(data_path=args.data_path, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
