"""Embedding pipeline — sentence-transformers → Qdrant vector index.

Reads JSONL docs, embeds them with all-MiniLM-L6-v2,
and indexes into Qdrant collection "cryo_embeddings".

Usage:
    python pipeline/embed.py
    python pipeline/embed.py --data-path data/raw/ --batch-size 64
"""

import argparse
import json
import sys
from pathlib import Path

import structlog
from tqdm import tqdm

from backend.config import settings

logger = structlog.get_logger()

COLLECTION_NAME = "cryo_embeddings"
EMBEDDING_DIM = 384
CHECKPOINT_FILE = Path("data/.embed_checkpoint")


def get_qdrant_client():
    """Create Qdrant client — returns None if unavailable."""
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(settings.qdrant_url, timeout=10)
        client.get_collections()
        return client
    except Exception as exc:
        logger.warning("cryo.embed.qdrant_unavailable", error=str(exc))
        return None


def ensure_collection(client) -> None:
    """Create collection if it doesn't exist."""
    from qdrant_client.models import Distance, VectorParams

    try:
        client.create_collection(
            COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info("cryo.embed.collection_created", name=COLLECTION_NAME)
    except Exception:
        pass


def stream_docs(data_path: Path):
    """Yield all docs from all JSONL files in the directory."""
    jsonl_files = sorted(data_path.glob("*.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"No JSONL files found in {data_path}")

    for jsonl_file in jsonl_files:
        with jsonl_file.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue


def load_checkpoint() -> int:
    if CHECKPOINT_FILE.exists():
        try:
            return int(CHECKPOINT_FILE.read_text().strip())
        except ValueError:
            return 0
    return 0


def save_checkpoint(count: int) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(str(count))


def embed_documents(data_path: str, batch_size: int) -> None:
    """Main embedding loop."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("sentence-transformers not installed. Run: pip install sentence-transformers")
        sys.exit(1)

    path = Path(data_path)
    qdrant = get_qdrant_client()
    if qdrant:
        ensure_collection(qdrant)

    already_done = load_checkpoint()
    model = SentenceTransformer(settings.embedding_model, device="cpu")
    logger.info("cryo.embed.model_loaded", model=settings.embedding_model)

    batch: list[str] = []
    batch_ids: list[str] = []
    batch_meta: list[dict] = []
    total_embedded = already_done
    doc_count = 0

    for doc in tqdm(stream_docs(path), desc="Embedding docs", unit="doc"):
        doc_count += 1
        if doc_count <= already_done:
            continue

        text = doc.get("text", "") or doc.get("text_preview", "") or ""
        if not text.strip():
            continue

        batch.append(text[:2000])
        batch_ids.append(doc.get("id", f"doc_{doc_count}"))
        batch_meta.append(
            {
                "url": doc.get("url", ""),
                "timestamp": doc.get("timestamp", ""),
                "year": doc.get("year", 0),
                "domain": doc.get("domain", ""),
                "content_type": doc.get("content_type", "article"),
            }
        )

        if len(batch) >= batch_size:
            _embed_and_index(model, qdrant, batch, batch_ids, batch_meta)
            total_embedded += len(batch)
            save_checkpoint(total_embedded)
            batch, batch_ids, batch_meta = [], [], []

    if batch:
        _embed_and_index(model, qdrant, batch, batch_ids, batch_meta)
        total_embedded += len(batch)
        save_checkpoint(total_embedded)

    print(f"\n[embed] Done. {total_embedded} docs embedded.")


def _embed_and_index(model, qdrant, texts: list[str], ids: list[str], metas: list[dict]) -> None:
    """Embed a batch and index into Qdrant (skip if Qdrant unavailable)."""
    try:
        vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    except Exception as exc:
        logger.error("cryo.embed.encode_error", error=str(exc))
        return

    if qdrant is None:
        return

    try:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=abs(hash(doc_id)) % (2**63),
                vector=vec.tolist(),
                payload=meta,
            )
            for doc_id, vec, meta in zip(ids, vectors, metas, strict=True)
        ]
        qdrant.upsert(COLLECTION_NAME, points=points, wait=False)
    except Exception as exc:
        logger.warning("cryo.embed.qdrant_upsert_error", error=str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed docs and index into Qdrant.")
    parser.add_argument("--data-path", default="data/raw")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    embed_documents(data_path=args.data_path, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
