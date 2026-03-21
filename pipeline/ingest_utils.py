"""Shared utilities for all Cryo data ingestion pipelines.

Every ingest_*.py script imports from here — no duplication.
"""

import hashlib
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any


def clean_html(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#?\w+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_doc_id(url: str, timestamp: str) -> str:
    """Stable unique doc ID from URL + timestamp."""
    raw = f"{url}|{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def format_timestamp(year: int, month: int = 1, day: int = 1) -> str:
    """Format as FineWeb-style timestamp string YYYYMMDDHHMMSS."""
    return f"{year}{month:02d}{day:02d}120000"


def append_jsonl(path: Path, docs: list[dict]) -> None:
    """Atomically append docs to a JSONL file. Creates parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")


def exponential_backoff(
    fn: Callable,
    max_retries: int = 5,
    base_delay: float = 1.0,
) -> Any:
    """Call fn() with exponential backoff on exception. Raises on final failure."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            delay = base_delay * (2 ** attempt)
            print(f"  Retry {attempt + 1}/{max_retries} in {delay:.0f}s: {exc}")
            time.sleep(delay)
    raise RuntimeError(f"Failed after {max_retries} retries") from last_exc


def count_words(text: str) -> int:
    """Count whitespace-separated words."""
    return len(text.split())


def extract_domain(url: str) -> str:
    """Extract domain from URL without importing urllib."""
    match = re.match(r"https?://([^/]+)", url)
    return match.group(1) if match else "unknown"


def load_checkpoint(path: Path) -> int:
    """Return the last saved offset, or 0 if no checkpoint exists."""
    if path.exists():
        try:
            return int(path.read_text().strip())
        except (ValueError, OSError):
            return 0
    return 0


def save_checkpoint(path: Path, offset: int) -> None:
    """Persist the current offset to a checkpoint file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(offset))
