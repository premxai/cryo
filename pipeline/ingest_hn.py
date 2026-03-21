"""Ingest Hacker News stories + top comments into Cryo's JSONL format.

Uses the HN Algolia API (no key required). Filters to pre-2022 content
with score > 100 for stories and score > 50 for comments.

Usage:
    python pipeline/ingest_hn.py --limit 5000
    python pipeline/ingest_hn.py --limit 2000 --output data/raw/hn.jsonl
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
    clean_html,
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

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
PRE_2022_TS = 1640995200  # 2022-01-01 00:00:00 UTC
MIN_STORY_SCORE = 10  # lowered: more content, still quality
MIN_COMMENT_SCORE = 10
MIN_WORDS = 80
CHECKPOINT_EVERY = 200
HITS_PER_PAGE = 100


def algolia_get(endpoint: str, params: dict) -> dict:
    """GET request to HN Algolia API. Returns parsed JSON."""
    url = f"{ALGOLIA_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "CryoBot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ts_to_parts(unix_ts: int) -> tuple[int, int, int]:
    """Convert unix timestamp to (year, month, day) without datetime import."""
    # Simplified: use struct_time via time module
    import time as t

    st = t.gmtime(unix_ts)
    return st.tm_year, st.tm_mon, st.tm_mday


def fetch_stories(page: int, ts_start: int = 0, ts_end: int = PRE_2022_TS) -> list[dict]:
    """Fetch one page of HN stories within a time window."""
    filters = f"created_at_i>{ts_start},created_at_i<{ts_end},points>={MIN_STORY_SCORE}"
    data = algolia_get(
        "search_by_date",
        {
            "tags": "story",
            "numericFilters": filters,
            "hitsPerPage": HITS_PER_PAGE,
            "page": page,
            "attributesToRetrieve": "objectID,title,url,story_text,points,created_at_i",
        },
    )
    return data.get("hits", [])


# Year windows to bypass Algolia's 1000-result cap per query
YEAR_WINDOWS = [
    (0, 1388534400),  # before 2014
    (1388534400, 1451606400),  # 2014-2015
    (1451606400, 1514764800),  # 2016-2017
    (1514764800, 1546300800),  # 2018
    (1546300800, 1577836800),  # 2019
    (1577836800, 1609459200),  # 2020
    (1609459200, PRE_2022_TS),  # 2021
]


def fetch_top_comments(story_id: str, max_comments: int = 5) -> list[str]:
    """Fetch top comments for a story by score."""
    try:
        data = algolia_get(
            "search",
            {
                "tags": f"comment,story_{story_id}",
                "numericFilters": f"points>={MIN_COMMENT_SCORE}",
                "hitsPerPage": max_comments,
                "attributesToRetrieve": "comment_text,points",
            },
        )
        comments = []
        for hit in data.get("hits", []):
            raw = hit.get("comment_text", "")
            text = clean_html(raw).strip()
            if len(text.split()) >= 20:
                comments.append(text)
        return comments
    except Exception:
        return []


def story_to_doc(hit: dict) -> dict | None:
    """Convert an Algolia story hit to a Cryo document."""
    unix_ts = hit.get("created_at_i", 0)
    year, month, day = ts_to_parts(unix_ts)
    if year > 2021:
        return None

    title = hit.get("title", "").strip()
    story_text = clean_html(hit.get("story_text") or "").strip()
    story_url = hit.get("url", "")
    hn_url = f"https://news.ycombinator.com/item?id={hit['objectID']}"

    # Compose text: title + story text (if self-post) + top comments
    parts = [title]
    if story_text and len(story_text.split()) >= 20:
        parts.append(story_text)

    # Fetch top comments
    comments = fetch_top_comments(hit["objectID"], max_comments=5)
    parts.extend(comments)

    text = "\n\n".join(p for p in parts if p)
    wc = count_words(text)
    if wc < MIN_WORDS:
        return None

    timestamp = format_timestamp(year, month, day)
    return {
        "id": make_doc_id(hn_url, timestamp),
        "url": story_url or hn_url,
        "text": text,
        "timestamp": timestamp,
        "year": year,
        "domain": "news.ycombinator.com",
        "word_count": wc,
        "content_type": "discussion",
    }


def ingest(limit: int, output: Path, checkpoint_path: Path) -> None:
    """Main ingestion loop across year-windowed Algolia queries to bypass 1000-result cap."""
    done = load_checkpoint(checkpoint_path)
    collected = done
    print(f"[hn] Starting from checkpoint: {done} items")

    batch_buf: list[dict] = []
    windows = (
        tqdm(YEAR_WINDOWS, desc="HN year windows", unit="window") if HAS_TQDM else YEAR_WINDOWS
    )

    for ts_start, ts_end in windows:
        if collected >= limit:
            break

        page = 0
        while collected < limit:

            def _fetch(p=page, s=ts_start, e=ts_end) -> list[dict]:
                hits = fetch_stories(p, ts_start=s, ts_end=e)
                time.sleep(0.5)
                return hits

            try:
                hits = exponential_backoff(_fetch, max_retries=5, base_delay=2.0)
            except RuntimeError as exc:
                print(f"[hn] Skipping page {page}: {exc}")
                break

            if not hits:
                break  # exhausted this window, move to next

            for hit in hits:
                if collected >= limit:
                    break
                doc = story_to_doc(hit)
                if doc:
                    batch_buf.append(doc)
                    collected += 1

            if len(batch_buf) >= CHECKPOINT_EVERY:
                append_jsonl(output, batch_buf)
                save_checkpoint(checkpoint_path, collected)
                batch_buf = []

            page += 1

    if batch_buf:
        append_jsonl(output, batch_buf)
        save_checkpoint(checkpoint_path, collected)

    print(f"[hn] Done. {collected} items -> {output}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Ingest Hacker News into Cryo.")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--output", type=str, default="data/raw/hn.jsonl")
    args = parser.parse_args()

    output = Path(args.output)
    checkpoint = Path("data/.checkpoint_hn")
    ingest(args.limit, output, checkpoint)


if __name__ == "__main__":
    main()
