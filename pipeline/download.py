"""Download pre-2022 human web documents from FineWeb (HuggingFace).

Usage:
    python pipeline/download.py --limit 100000 --output data/raw/
    python pipeline/download.py --limit 100000 --resume   # resume from checkpoint

Output: data/raw/batch_000.jsonl ... batch_009.jsonl (10k docs each)
Each doc: {id, url, text, timestamp, year, domain, word_count}
"""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from tqdm import tqdm

# Pre-2022 crawl IDs in FineWeb — anything CC-MAIN-2021 or earlier
VALID_CRAWL_PREFIXES = (
    "CC-MAIN-2013",
    "CC-MAIN-2014",
    "CC-MAIN-2015",
    "CC-MAIN-2016",
    "CC-MAIN-2017",
    "CC-MAIN-2018",
    "CC-MAIN-2019",
    "CC-MAIN-2020",
    "CC-MAIN-2021",
)

CHECKPOINT_FILE = "data/.checkpoint"
BATCH_SIZE = 10_000
MIN_WORD_COUNT = 100
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def is_pre_2022(crawl: str) -> bool:
    """Return True if the crawl ID represents pre-2022 content."""
    return any(crawl.startswith(prefix) for prefix in VALID_CRAWL_PREFIXES)


def strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = TAG_RE.sub(" ", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def extract_year(timestamp: str) -> int | None:
    """Extract 4-digit year from timestamp string like '20210315120000'."""
    if timestamp and len(timestamp) >= 4:
        try:
            return int(timestamp[:4])
        except ValueError:
            return None
    return None


def extract_domain(url: str) -> str:
    """Extract domain from URL string."""
    try:
        # Simple extraction: everything between // and the next /
        match = re.search(r"://([^/]+)", url)
        return match.group(1) if match else ""
    except Exception:
        return ""


def make_doc_id(url: str, timestamp: str) -> str:
    """Stable, unique doc ID from URL + timestamp."""
    raw = f"{url}|{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def clean_doc(raw: dict) -> dict | None:
    """Transform a raw FineWeb record into a Cryo document. Returns None to skip."""
    url = raw.get("url", "")
    text_raw = raw.get("text", "")
    timestamp = raw.get("timestamp", "")
    crawl = raw.get("crawl", "")

    if not is_pre_2022(crawl):
        return None

    text = strip_html(text_raw)
    word_count = len(text.split())

    if word_count < MIN_WORD_COUNT:
        return None

    year = extract_year(timestamp)
    if year is None or year > 2021:
        return None

    return {
        "id": make_doc_id(url, timestamp),
        "url": url,
        "text": text,
        "timestamp": timestamp,
        "year": year,
        "domain": extract_domain(url),
        "word_count": word_count,
    }


def load_checkpoint() -> int:
    """Return the number of docs already saved (0 if no checkpoint)."""
    path = Path(CHECKPOINT_FILE)
    if path.exists():
        try:
            return int(path.read_text().strip())
        except ValueError:
            return 0
    return 0


def save_checkpoint(count: int) -> None:
    """Persist progress count so the run can be resumed after interruption."""
    Path(CHECKPOINT_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(CHECKPOINT_FILE).write_text(str(count))


def stream_with_retry(max_retries: int = 5):
    """Stream FineWeb dataset with exponential backoff on network errors."""
    from datasets import load_dataset

    for attempt in range(max_retries):
        try:
            return load_dataset(
                "HuggingFaceFW/fineweb",
                split="train",
                streaming=True,
            )
        except Exception as exc:
            wait = 2**attempt
            print(f"[download] Stream attempt {attempt + 1} failed: {exc}. Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("Failed to connect to FineWeb after max retries.")


def download(limit: int, output_dir: str, resume: bool) -> None:
    """Main download loop — streams FineWeb and writes JSONL batches."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    already_saved = load_checkpoint() if resume else 0
    if already_saved > 0:
        print(f"[download] Resuming from checkpoint: {already_saved} docs already saved.")

    batch_index = already_saved // BATCH_SIZE
    current_batch: list[dict] = []
    total_saved = already_saved
    total_scanned = 0
    skipped = 0

    dataset = stream_with_retry()

    with tqdm(total=limit, initial=already_saved, desc="Downloading docs", unit="doc") as pbar:
        for raw in dataset:
            total_scanned += 1

            # Skip already-processed docs when resuming
            if total_saved >= limit:
                break
            if resume and total_scanned <= already_saved:
                continue

            doc = clean_doc(raw)
            if doc is None:
                skipped += 1
                continue

            current_batch.append(doc)

            if len(current_batch) >= BATCH_SIZE:
                batch_path = out / f"batch_{batch_index:03d}.jsonl"
                with batch_path.open("w", encoding="utf-8") as f:
                    for d in current_batch:
                        f.write(json.dumps(d, ensure_ascii=False) + "\n")

                total_saved += len(current_batch)
                save_checkpoint(total_saved)
                pbar.update(len(current_batch))
                print(f"[download] Saved batch {batch_index} → {batch_path} ({total_saved} total)")

                batch_index += 1
                current_batch = []

            if total_saved >= limit:
                break

    # Write any remaining docs in the final partial batch
    if current_batch:
        batch_path = out / f"batch_{batch_index:03d}.jsonl"
        with batch_path.open("w", encoding="utf-8") as f:
            for d in current_batch:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        total_saved += len(current_batch)
        save_checkpoint(total_saved)

    print(
        f"\n[download] Done. {total_saved} docs saved. {skipped} skipped. Scanned {total_scanned}."
    )


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Download FineWeb pre-2022 documents.")
    parser.add_argument("--limit", type=int, default=100_000, help="Number of docs to save.")
    parser.add_argument("--output", type=str, default="data/raw", help="Output directory.")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint.")
    args = parser.parse_args()

    download(limit=args.limit, output_dir=args.output, resume=args.resume)


if __name__ == "__main__":
    main()
