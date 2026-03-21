"""Ingest Project Gutenberg books into Cryo's JSONL format.

Uses the gutendex.com API (no key required) to fetch popular English
public-domain books, strips header/footer boilerplate, and chunks each
book into 800-1000 word searchable segments.

Usage:
    python pipeline/ingest_gutenberg.py --books 500
    python pipeline/ingest_gutenberg.py --books 200 --output data/raw/gutenberg.jsonl
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pipeline.ingest_utils import (
    append_jsonl,
    count_words,
    exponential_backoff,
    format_timestamp,
    load_checkpoint,
    make_doc_id,
    save_checkpoint,
)

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

GUTENDEX_BASE = "https://gutendex.com/books"
CHUNK_WORDS_MIN = 700
CHUNK_WORDS_MAX = 1100
MAX_CHUNKS_PER_BOOK = 10
MIN_BOOK_WORDS = 5000
CHECKPOINT_EVERY = 50
REQUEST_DELAY = 0.5  # seconds between downloads

# Patterns marking Gutenberg header/footer boundaries
_START_PATTERNS = [
    r"\*\*\* START OF (THE|THIS) PROJECT GUTENBERG",
    r"\*\*\*START OF (THE|THIS) PROJECT GUTENBERG",
    r"START OF (THE|THIS) PROJECT GUTENBERG EBOOK",
]
_END_PATTERNS = [
    r"\*\*\* END OF (THE|THIS) PROJECT GUTENBERG",
    r"\*\*\*END OF (THE|THIS) PROJECT GUTENBERG",
    r"END OF (THE|THIS) PROJECT GUTENBERG EBOOK",
]


def _get(url: str, timeout: int = 20) -> bytes:
    """Perform a GET request and return raw bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": "CryoBot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_book_list(page: int) -> dict:
    """Fetch one page of popular English plain-text books from gutendex."""
    params = urllib.parse.urlencode(
        {
            "languages": "en",
            "mime_type": "text/plain",
            "page": page,
        }
    )
    raw = _get(f"{GUTENDEX_BASE}?{params}")
    return json.loads(raw.decode("utf-8"))


def get_plaintext_url(book: dict) -> str | None:
    """Extract the best plain-text download URL from a book entry."""
    formats = book.get("formats", {})
    for mime in ("text/plain; charset=utf-8", "text/plain; charset=us-ascii", "text/plain"):
        if mime in formats:
            return formats[mime]
    # Fallback: any text/plain key
    for key, url in formats.items():
        if key.startswith("text/plain"):
            return url
    return None


def strip_gutenberg_boilerplate(text: str) -> str:
    """Remove Project Gutenberg header and footer from raw book text."""
    start_idx = 0
    for pattern in _START_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Skip to end of the start-marker line
            line_end = text.find("\n", match.end())
            if line_end != -1:
                start_idx = line_end + 1
            break

    end_idx = len(text)
    for pattern in _END_PATTERNS:
        match = re.search(pattern, text[start_idx:], re.IGNORECASE)
        if match:
            end_idx = start_idx + match.start()
            break

    return text[start_idx:end_idx].strip()


def chunk_text(
    text: str, min_words: int = CHUNK_WORDS_MIN, max_words: int = CHUNK_WORDS_MAX
) -> list[str]:
    """Split text into chunks of roughly min_words–max_words words, splitting at paragraph boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current_parts: list[str] = []
    current_count = 0

    for para in paragraphs:
        para_words = len(para.split())
        if current_count + para_words > max_words and current_count >= min_words:
            chunks.append("\n\n".join(current_parts))
            current_parts = [para]
            current_count = para_words
        else:
            current_parts.append(para)
            current_count += para_words

    if current_count >= min_words:
        chunks.append("\n\n".join(current_parts))

    return chunks


def download_book(url: str) -> str | None:
    """Download plain-text book content, handling charset."""
    try:
        raw = _get(url, timeout=30)
    except Exception:
        return None
    # Try UTF-8 first, fall back to latin-1
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def book_to_docs(book: dict) -> list[dict]:
    """Download and chunk one Gutenberg book into Cryo documents."""
    txt_url = get_plaintext_url(book)
    if not txt_url:
        return []

    raw = download_book(txt_url)
    if not raw:
        return []

    text = strip_gutenberg_boilerplate(raw)
    if count_words(text) < MIN_BOOK_WORDS:
        return []

    chunks = chunk_text(text)[:MAX_CHUNKS_PER_BOOK]
    if not chunks:
        return []

    title = book.get("title", "Unknown Title")
    authors = ", ".join(a.get("name", "") for a in book.get("authors", []))
    book_id = str(book.get("id", ""))
    gutenberg_url = f"https://www.gutenberg.org/ebooks/{book_id}"

    # Use 2010 as a proxy year for digital availability
    timestamp = format_timestamp(2010, 1, 1)

    docs: list[dict] = []
    for i, chunk in enumerate(chunks):
        url = f"{gutenberg_url}#chunk{i}"
        wc = count_words(chunk)
        docs.append(
            {
                "id": make_doc_id(url, timestamp),
                "url": gutenberg_url,
                "text": f"{title} — {authors}\n\n{chunk}" if i == 0 else chunk,
                "timestamp": timestamp,
                "year": 2010,
                "domain": "gutenberg.org",
                "word_count": wc,
                "content_type": "book",
            }
        )

    return docs


def ingest(book_limit: int, output: Path, checkpoint_path: Path) -> None:
    """Main ingestion loop — page through gutendex and download books."""
    done = load_checkpoint(checkpoint_path)
    collected = done
    print(f"[gutenberg] Starting from checkpoint: {done} docs already saved")

    page = 1
    batch_buf: list[dict] = []
    books_attempted = 0

    pbar = None
    if HAS_TQDM:
        pbar = tqdm(desc="Gutenberg docs", unit="doc", total=book_limit)
        pbar.update(done)

    while collected < book_limit:

        def _fetch_page(p=page) -> dict:
            data = fetch_book_list(p)
            time.sleep(REQUEST_DELAY)
            return data

        try:
            data = exponential_backoff(_fetch_page, max_retries=5, base_delay=2.0)
        except RuntimeError as exc:
            print(f"[gutenberg] Failed to fetch page {page}: {exc}")
            break

        books = data.get("results", [])
        if not books:
            print("[gutenberg] No more books available.")
            break

        for book in books:
            if collected >= book_limit:
                break
            books_attempted += 1

            def _fetch_book(b=book) -> list[dict]:
                docs = book_to_docs(b)
                time.sleep(REQUEST_DELAY)
                return docs

            try:
                docs = exponential_backoff(_fetch_book, max_retries=3, base_delay=2.0)
            except RuntimeError as exc:
                print(f"[gutenberg] Skipping book {book.get('id')}: {exc}")
                continue

            if not docs:
                continue

            batch_buf.extend(docs)
            collected += len(docs)

            if pbar:
                pbar.update(len(docs))

            if len(batch_buf) >= CHECKPOINT_EVERY:
                append_jsonl(output, batch_buf)
                save_checkpoint(checkpoint_path, collected)
                batch_buf = []

        if not data.get("next"):
            print("[gutenberg] Reached last page of gutendex.")
            break

        page += 1

    if batch_buf:
        append_jsonl(output, batch_buf)
        save_checkpoint(checkpoint_path, collected)

    if pbar:
        pbar.close()

    print(f"[gutenberg] Done. {collected} docs from ~{books_attempted} books -> {output}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Ingest Project Gutenberg books into Cryo.")
    parser.add_argument(
        "--books", type=int, default=500, help="Target number of document chunks (not books)"
    )
    parser.add_argument("--output", type=str, default="data/raw/gutenberg.jsonl")
    args = parser.parse_args()

    output = Path(args.output)
    checkpoint = Path("data/.checkpoint_gutenberg")
    ingest(args.books, output, checkpoint)


if __name__ == "__main__":
    main()
