"""Ingest Common Crawl WET files into Cryo's JSONL format.

WET files contain pre-extracted plaintext — no HTML parsing needed.
Uses CC-MAIN-2021-43 (October 2021, last crawl before 2022).

Each WET file is ~150MB compressed / ~500MB uncompressed, ~5K–15K pages.
100 WET files → ~300K–1M quality docs. 500 files → 1.5M–5M docs.

Usage:
    python pipeline/ingest_commoncrawl.py --wet-files 100
    python pipeline/ingest_commoncrawl.py --wet-files 500 --resume
    python pipeline/ingest_commoncrawl.py --wet-files 200 --output data/raw/cc_b.jsonl
"""

import argparse
import contextlib
import gzip
import re
import tempfile
import time
from pathlib import Path

import httpx
from tqdm import tqdm

from pipeline.ingest_utils import (
    append_jsonl,
    count_words,
    extract_domain,
    load_checkpoint,
    make_doc_id,
    save_checkpoint,
)

# CC-MAIN-2021-43 = October 2021, last pre-2022 crawl
CC_CRAWL = "CC-MAIN-2021-43"
WET_INDEX_URL = f"https://data.commoncrawl.org/crawl-data/{CC_CRAWL}/wet.paths.gz"
CC_BASE_URL = "https://data.commoncrawl.org/"

MIN_WORDS = 150
MAX_WORDS = 50_000
BATCH_SIZE = 500
CHECKPOINT_PATH = Path("data/.checkpoint_commoncrawl")

# Common English function words — fast language heuristic
_EN_WORDS = {
    "the",
    "is",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "a",
    "an",
    "in",
    "of",
    "to",
    "it",
    "for",
}


def _is_english(text: str) -> bool:
    """Return True if text looks like English (overlap with function words)."""
    words = set(text.lower().split()[:300])
    return len(words & _EN_WORDS) >= 5


def _parse_warc_date(date_str: str) -> tuple[int, str]:
    """Parse WARC-Date string → (year, compact_timestamp).

    WARC-Date format: 2021-10-15T12:00:00Z
    """
    year = 2021
    ts = "20211015120000"
    if date_str and len(date_str) >= 4:
        with contextlib.suppress(ValueError):
            year = int(date_str[:4])
        ts = re.sub(r"[^0-9]", "", date_str)[:14].ljust(14, "0")
    return year, ts


def _process_record(header_lines: list[str], body_lines: list[str]) -> dict | None:
    """Convert a parsed WARC record into a Cryo doc.

    Returns None if the record should be skipped (wrong type, too short, non-English).
    """
    headers: dict[str, str] = {}
    for line in header_lines:
        if ":" in line:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()

    if headers.get("warc-type") != "conversion":
        return None

    uri = headers.get("warc-target-uri", "")
    if not uri.startswith("http"):
        return None

    body = "\n".join(body_lines).strip()
    if not body:
        return None

    wc = count_words(body)
    if wc < MIN_WORDS or wc > MAX_WORDS:
        return None

    if not _is_english(body):
        return None

    year, ts = _parse_warc_date(headers.get("warc-date", ""))
    if year > 2021:
        return None

    return {
        "id": make_doc_id(uri, ts),
        "url": uri,
        "text": body,
        "timestamp": ts,
        "year": year,
        "domain": extract_domain(uri),
        "word_count": wc,
        "content_type": "article",
    }


def parse_wet_file(path: Path) -> list[dict]:
    """Parse a gzip-compressed WET file into doc records.

    Uses a line-by-line state machine: no external WARC library needed.
    Memory-efficient: decompresses line by line via gzip.open streaming.
    """
    records: list[dict] = []
    header_lines: list[str] = []
    body_lines: list[str] = []
    in_body = False

    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line = raw_line.rstrip("\r\n")

                if line == "WARC/1.0":
                    # Flush previous record
                    if header_lines:
                        rec = _process_record(header_lines, body_lines)
                        if rec:
                            records.append(rec)
                    header_lines = []
                    body_lines = []
                    in_body = False
                    continue

                if not in_body:
                    if line == "":
                        in_body = True
                    else:
                        header_lines.append(line)
                else:
                    body_lines.append(line)

        # Flush last record
        if header_lines:
            rec = _process_record(header_lines, body_lines)
            if rec:
                records.append(rec)

    except Exception as exc:
        print(f"  [warn] gzip parse error: {exc}")

    return records


def fetch_wet_paths(limit: int) -> list[str]:
    """Download the WET paths index and return the first `limit` paths."""
    print(f"Fetching WET index: {WET_INDEX_URL}")
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(WET_INDEX_URL)
        resp.raise_for_status()

    content = gzip.decompress(resp.content).decode("utf-8")
    paths = [ln.strip() for ln in content.splitlines() if ln.strip()]
    print(f"Index has {len(paths):,} WET files — using first {limit:,}")
    return paths[:limit]


def download_wet_file(wet_path: str, dest: Path) -> bool:
    """Stream a WET file from Common Crawl into dest. Returns True on success."""
    url = CC_BASE_URL + wet_path
    try:
        with httpx.Client(timeout=600.0) as client, client.stream("GET", url) as resp:
            resp.raise_for_status()
            with dest.open("wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65_536):
                    f.write(chunk)
        return True
    except Exception as exc:
        print(f"  [warn] download failed ({wet_path}): {exc}")
        return False


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Ingest Common Crawl WET files into JSONL.")
    parser.add_argument(
        "--wet-files", type=int, default=100, help="Number of WET files to process (default 100)"
    )
    parser.add_argument("--output", default="data/raw/cc_2021.jsonl", help="Output JSONL path")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start_idx = load_checkpoint(CHECKPOINT_PATH) if args.resume else 0
    if start_idx:
        print(f"Resuming from WET file #{start_idx}")

    wet_paths = fetch_wet_paths(args.wet_files)
    total_docs = 0
    batch: list[dict] = []

    # Single temp file reused across all WET files
    with tempfile.NamedTemporaryFile(suffix=".warc.wet.gz", delete=False) as tmp:
        temp_path = Path(tmp.name)

    try:
        pbar = tqdm(
            wet_paths[start_idx:],
            desc="WET files",
            initial=start_idx,
            total=len(wet_paths),
            unit="file",
        )
        for i, wet_path in enumerate(wet_paths[start_idx:], start=start_idx):
            pbar.set_postfix(docs=f"{total_docs:,}")

            if not download_wet_file(wet_path, temp_path):
                pbar.update(1)
                time.sleep(2.0)  # brief pause after a failed download
                continue

            try:
                records = parse_wet_file(temp_path)
                batch.extend(records)
                total_docs += len(records)
            except Exception as exc:
                print(f"  [warn] parse error ({wet_path}): {exc}")

            if len(batch) >= BATCH_SIZE:
                append_jsonl(output_path, batch)
                batch = []

            save_checkpoint(CHECKPOINT_PATH, i + 1)
            pbar.update(1)

        pbar.close()

    finally:
        if batch:
            append_jsonl(output_path, batch)
        temp_path.unlink(missing_ok=True)

    print(f"\nDone. {total_docs:,} docs → {output_path}")
    print("Next: python pipeline/index.py --data-path data/raw/")


if __name__ == "__main__":
    main()
