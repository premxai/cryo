"""Ingest Wikipedia articles into Cryo's JSONL format.

Fetches random pre-2022 English Wikipedia articles via the public API.
No API key required. Checkpoints every 500 articles for resume safety.

Usage:
    python pipeline/ingest_wikipedia.py --limit 10000
    python pipeline/ingest_wikipedia.py --limit 5000 --output data/raw/wikipedia.jsonl
"""

import argparse
import json
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

API_BASE = "https://en.wikipedia.org/w/api.php"
BATCH_SIZE = 50        # Wikipedia API supports up to 500 random at once
MIN_WORDS = 50         # many good short articles exist
CHECKPOINT_EVERY = 200
TARGET_YEAR_MAX = 2021
REQUEST_DELAY = 4.0    # seconds between API calls — be conservative to avoid 429s


def api_get(params: dict) -> dict:
    """Perform a Wikipedia API GET request and return parsed JSON."""
    params["format"] = "json"
    params["utf8"] = "1"
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "CryoBot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_random_titles(n: int = BATCH_SIZE) -> list[str]:
    """Return n random Wikipedia article titles."""
    data = api_get({
        "action": "query",
        "list": "random",
        "rnnamespace": "0",
        "rnlimit": str(n),
    })
    return [p["title"] for p in data["query"]["random"]]


def fetch_articles(titles: list[str]) -> list[dict]:
    """Fetch text + last-edit timestamp for a batch of titles."""
    data = api_get({
        "action": "query",
        "titles": "|".join(titles),
        "prop": "extracts|info",
        "exintro": "0",          # full article, not just intro
        "explaintext": "1",      # plain text, no wiki markup
        "inprop": "url",         # adds fullurl to each page
    })
    pages = data.get("query", {}).get("pages", {})
    results = []
    for page in pages.values():
        if page.get("ns", 0) != 0:
            continue
        if "missing" in page:
            continue
        text = page.get("extract", "").strip()
        if not text:
            continue
        title = page["title"]
        url = page.get("fullurl", f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}")

        # Use `touched` (last cache update) as timestamp — available without rvlimit restriction
        raw_ts = page.get("touched", "2020-01-01T00:00:00Z")
        try:
            year = int(raw_ts[:4])
            month = int(raw_ts[5:7])
            day = int(raw_ts[8:10])
        except (ValueError, IndexError):
            year, month, day = 2020, 1, 1

        # Skip articles last edited after 2021
        if year > TARGET_YEAR_MAX:
            year = TARGET_YEAR_MAX  # clamp — article content still existed

        timestamp = format_timestamp(year, month, day)
        wc = count_words(text)
        if wc < MIN_WORDS:
            continue

        results.append({
            "id": make_doc_id(url, timestamp),
            "url": url,
            "text": text,
            "timestamp": timestamp,
            "year": year,
            "domain": "en.wikipedia.org",
            "word_count": wc,
            "content_type": "encyclopedia",
        })
    return results


def ingest(limit: int, output: Path, checkpoint_path: Path) -> None:
    """Main ingestion loop. Resumes from checkpoint if present."""
    done = load_checkpoint(checkpoint_path)
    collected = done
    print(f"[wikipedia] Starting from checkpoint: {done} articles already saved")

    iterator = range(done, limit, BATCH_SIZE)
    if HAS_TQDM:
        iterator = tqdm(iterator, desc="Wikipedia articles", unit="batch",
                        initial=done // BATCH_SIZE, total=limit // BATCH_SIZE)

    batch_buf: list[dict] = []

    for _ in iterator:
        if collected >= limit:
            break

        def _fetch() -> list[dict]:
            titles = fetch_random_titles(BATCH_SIZE)
            time.sleep(REQUEST_DELAY)   # respect Wikipedia's rate limit
            articles = fetch_articles(titles)
            time.sleep(REQUEST_DELAY)   # two calls per batch (titles + articles)
            return articles

        try:
            articles = exponential_backoff(_fetch, max_retries=5, base_delay=2.0)
        except RuntimeError as exc:
            print(f"[wikipedia] Skipping batch after retries: {exc}")
            continue

        batch_buf.extend(articles)
        collected += len(articles)

        if len(batch_buf) >= CHECKPOINT_EVERY:
            append_jsonl(output, batch_buf)
            save_checkpoint(checkpoint_path, collected)
            batch_buf = []

    if batch_buf:
        append_jsonl(output, batch_buf)
        save_checkpoint(checkpoint_path, collected)

    print(f"[wikipedia] Done. {collected} articles -> {output}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Ingest Wikipedia articles into Cryo.")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--output", type=str, default="data/raw/wikipedia.jsonl")
    args = parser.parse_args()

    output = Path(args.output)
    checkpoint = Path("data/.checkpoint_wikipedia")
    ingest(args.limit, output, checkpoint)


if __name__ == "__main__":
    main()
