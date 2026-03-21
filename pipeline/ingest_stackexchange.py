"""Ingest Stack Exchange Q&A into Cryo's JSONL format.

Uses the public Stack Exchange API v2.3 (no key for read-only, but limited to
300 req/day without key — add SE_API_KEY to .env for 10k/day).

Fetches high-voted, answered questions + accepted answers from stackoverflow.com.
All content is pre-2022 and written by humans.

Usage:
    python pipeline/ingest_stackexchange.py --limit 5000
    python pipeline/ingest_stackexchange.py --limit 2000 --site stackoverflow
"""

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import sys
    sys.path.insert(0, ".")
    from backend.config import settings
    SE_API_KEY = getattr(settings, "se_api_key", "")
except Exception:
    SE_API_KEY = ""

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

SE_BASE = "https://api.stackexchange.com/2.3"
PRE_2022_TS = 1640995200   # 2022-01-01 00:00:00 UTC
MIN_SCORE = 10
MIN_WORDS = 100
CHECKPOINT_EVERY = 200
PAGE_SIZE = 100


def se_get(endpoint: str, params: dict) -> dict:
    """GET request to Stack Exchange API. Returns parsed JSON (handles gzip)."""
    if SE_API_KEY:
        params["key"] = SE_API_KEY
    params["filter"] = "withbody"
    url = f"{SE_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": "CryoBot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        import gzip
        raw = resp.read()
        if resp.info().get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))


def ts_to_parts(unix_ts: int) -> tuple[int, int, int]:
    """Convert unix timestamp to (year, month, day)."""
    import time as t
    st = t.gmtime(unix_ts)
    return st.tm_year, st.tm_mon, st.tm_mday


def fetch_question_page(page: int, site: str) -> dict:
    """Fetch one page of high-voted answered pre-2022 questions."""
    return se_get("questions", {
        "order": "desc",
        "sort": "votes",
        "site": site,
        "pagesize": PAGE_SIZE,
        "page": page,
        "min": MIN_SCORE,
        "todate": PRE_2022_TS,
        "answers": "True",
    })


def fetch_accepted_answer(answer_id: int, site: str) -> str:
    """Fetch the body of an accepted answer."""
    data = se_get(f"answers/{answer_id}", {
        "site": site,
        "order": "desc",
        "sort": "activity",
    })
    items = data.get("items", [])
    if not items:
        return ""
    return clean_html(items[0].get("body", ""))


def question_to_doc(item: dict, site: str) -> dict | None:
    """Convert a Stack Exchange question item to a Cryo document."""
    creation_ts = item.get("creation_date", 0)
    year, month, day = ts_to_parts(creation_ts)
    if year > 2021:
        return None

    title = item.get("title", "").strip()
    body = clean_html(item.get("body", "")).strip()
    q_url = item.get("link", "")
    accepted_answer_id = item.get("accepted_answer_id")

    # Build text: title + question body
    parts = [f"Q: {title}", body]

    # Fetch accepted answer if available
    if accepted_answer_id:
        try:
            answer_text = exponential_backoff(
                lambda: fetch_accepted_answer(accepted_answer_id, site),
                max_retries=3,
                base_delay=1.0,
            )
            if answer_text and len(answer_text.split()) >= 30:
                parts.append(f"A: {answer_text}")
            time.sleep(0.2)  # SE API rate limit
        except RuntimeError:
            pass

    text = "\n\n".join(p for p in parts if p)
    wc = count_words(text)
    if wc < MIN_WORDS:
        return None

    timestamp = format_timestamp(year, month, day)
    domain = f"{site}.com" if "." not in site else site

    return {
        "id": make_doc_id(q_url, timestamp),
        "url": q_url,
        "text": text,
        "timestamp": timestamp,
        "year": year,
        "domain": domain,
        "word_count": wc,
        "content_type": "qa",
    }


def ingest(limit: int, output: Path, checkpoint_path: Path, site: str) -> None:
    """Main ingestion loop across paginated SE API results."""
    done = load_checkpoint(checkpoint_path)
    collected = done
    start_page = (done // PAGE_SIZE) + 1
    print(f"[se] Starting from checkpoint: {done} items, page {start_page}")

    max_pages = (limit // PAGE_SIZE) + 10
    pages = range(start_page, max_pages + 1)
    if HAS_TQDM:
        pages = tqdm(pages, desc=f"SE/{site} pages", unit="page")

    batch_buf: list[dict] = []

    for page in pages:
        if collected >= limit:
            break

        def _fetch(p=page) -> dict:
            data = fetch_question_page(p, site)
            time.sleep(0.5)
            return data

        try:
            data = exponential_backoff(_fetch, max_retries=5, base_delay=2.0)
        except RuntimeError as exc:
            print(f"[se] Skipping page {page}: {exc}")
            continue

        items = data.get("items", [])
        if not items:
            print(f"[se] No more items at page {page}.")
            break

        for item in items:
            if collected >= limit:
                break
            doc = question_to_doc(item, site)
            if doc:
                batch_buf.append(doc)
                collected += 1

        if len(batch_buf) >= CHECKPOINT_EVERY:
            append_jsonl(output, batch_buf)
            save_checkpoint(checkpoint_path, collected)
            batch_buf = []

        # Respect SE backoff signal
        backoff = data.get("backoff", 0)
        if backoff:
            print(f"[se] Backoff requested: {backoff}s")
            time.sleep(backoff)

    if batch_buf:
        append_jsonl(output, batch_buf)
        save_checkpoint(checkpoint_path, collected)

    print(f"[se] Done. {collected} items -> {output}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Ingest Stack Exchange into Cryo.")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--site", type=str, default="stackoverflow",
                        help="SE site name (stackoverflow, serverfault, etc.)")
    parser.add_argument("--output", type=str, default="data/raw/stackexchange.jsonl")
    args = parser.parse_args()

    output = Path(args.output)
    checkpoint = Path(f"data/.checkpoint_se_{args.site}")
    ingest(args.limit, output, checkpoint, args.site)


if __name__ == "__main__":
    main()
