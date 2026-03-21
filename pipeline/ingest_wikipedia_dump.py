"""Ingest the full English Wikipedia XML dump into Cryo's JSONL format.

Streams the bz2-compressed dump from Wikimedia's servers (or a local file)
without loading the entire thing into memory. Skips redirects, disambiguation
pages, and stubs under MIN_WORDS. Articles longer than CHUNK_WORDS are split
into chunks so each chunk is independently searchable.

Download the dump first (22GB compressed):
    curl -C - -O https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2

Then run:
    python pipeline/ingest_wikipedia_dump.py --dump enwiki-latest-pages-articles.xml.bz2
    python pipeline/ingest_wikipedia_dump.py --dump enwiki-latest-pages-articles.xml.bz2 --limit 100000
    python pipeline/ingest_wikipedia_dump.py --dump enwiki-latest-pages-articles.xml.bz2 --output data/raw/wikipedia_dump.jsonl
"""

import argparse
import bz2
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from pipeline.ingest_utils import (
    append_jsonl,
    count_words,
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

MIN_WORDS = 100
CHUNK_WORDS = 1500  # articles longer than this get chunked
CHUNK_OVERLAP_WORDS = 50  # overlap between chunks for context
CHECKPOINT_EVERY = 5000
BATCH_SIZE = 500

# MediaWiki XML namespace
MW_NS = "http://www.mediawiki.org/xml/DTD/MediaWiki"
_NS = "{" + MW_NS + "}"

# Patterns for content to skip or clean
_REDIRECT_RE = re.compile(r"^#REDIRECT", re.IGNORECASE)
_DISAMBIG_RE = re.compile(r"\{\{disambig", re.IGNORECASE)

# MediaWiki markup cleanup patterns
_TEMPLATE_RE = re.compile(r"\{\{[^}]*\}\}")  # {{templates}}
_LINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")  # [[link|text]] → text
_EXTLINK_RE = re.compile(r"\[https?://\S+ ([^\]]+)\]")  # [url text] → text
_HTML_RE = re.compile(r"<[^>]+>")  # <html tags>
_HEADING_RE = re.compile(r"^=+\s*(.*?)\s*=+$", re.MULTILINE)  # == headings ==
_REF_RE = re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL | re.IGNORECASE)
_MULTIBLANK_RE = re.compile(r"\n{3,}")


def clean_wikitext(text: str) -> str:
    """Convert MediaWiki markup to plain text."""
    text = _REF_RE.sub("", text)
    text = _TEMPLATE_RE.sub("", text)
    text = _LINK_RE.sub(r"\1", text)
    text = _EXTLINK_RE.sub(r"\1", text)
    text = _HTML_RE.sub("", text)
    text = _HEADING_RE.sub(r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    text = _MULTIBLANK_RE.sub("\n\n", text)
    return text.strip()


def should_skip(title: str, text: str) -> bool:
    """Return True for redirects, disambiguation pages, and very short articles."""
    if ":" in title and not title.startswith("Talk:"):
        # Skip Wikipedia: File: Category: Template: etc. namespaces
        ns = title.split(":")[0]
        if ns in (
            "Wikipedia",
            "File",
            "Category",
            "Template",
            "Portal",
            "Help",
            "Draft",
            "Module",
            "TimedText",
            "MediaWiki",
        ):
            return True
    if _REDIRECT_RE.match(text.strip()):
        return True
    return bool(_DISAMBIG_RE.search(text[:500]))


def chunk_article(title: str, text: str, url: str, timestamp: str, year: int) -> list[dict]:
    """Split a cleaned article into searchable chunks."""
    words = text.split()
    if len(words) <= CHUNK_WORDS:
        wc = len(words)
        if wc < MIN_WORDS:
            return []
        return [
            {
                "id": make_doc_id(url, timestamp),
                "url": url,
                "text": f"{title}\n\n{text}",
                "timestamp": timestamp,
                "year": year,
                "domain": "en.wikipedia.org",
                "word_count": wc,
                "content_type": "encyclopedia",
            }
        ]

    # Chunk long articles
    docs = []
    step = CHUNK_WORDS - CHUNK_OVERLAP_WORDS
    for i, start in enumerate(range(0, len(words), step)):
        chunk_words = words[start : start + CHUNK_WORDS]
        if len(chunk_words) < MIN_WORDS:
            break
        chunk_text = " ".join(chunk_words)
        chunk_url = f"{url}#section{i}" if i > 0 else url
        prefix = f"{title}\n\n" if i == 0 else f"{title} (continued)\n\n"
        docs.append(
            {
                "id": make_doc_id(chunk_url, timestamp),
                "url": url,
                "text": prefix + chunk_text,
                "timestamp": timestamp,
                "year": year,
                "domain": "en.wikipedia.org",
                "word_count": len(chunk_words),
                "content_type": "encyclopedia",
            }
        )
    return docs


def iter_articles(dump_path: Path):
    """Yield (title, text, timestamp) tuples from a Wikipedia XML dump.

    Supports both .bz2 compressed and plain .xml files.
    Uses iterparse to avoid loading the whole file into memory.
    """
    opener = bz2.open if dump_path.suffix == ".bz2" else open

    with opener(dump_path, "rt", encoding="utf-8", errors="replace") as fh:
        context = ET.iterparse(fh, events=("end",))
        title = text = timestamp = None

        for _event, elem in context:
            tag = elem.tag

            # Strip namespace prefix for comparison
            local = tag.rsplit("}", 1)[-1] if "}" in tag else tag

            if local == "title":
                title = elem.text or ""
            elif local == "text":
                text = elem.text or ""
            elif local == "timestamp":
                timestamp = elem.text or "2020-01-01T00:00:00Z"
            elif local == "page":
                if title and text:
                    yield title, text, timestamp
                title = text = timestamp = None
                elem.clear()


def ingest(dump_path: Path, output: Path, checkpoint_path: Path, limit: int | None = None) -> None:
    """Stream the dump and write Cryo JSONL docs."""
    done = load_checkpoint(checkpoint_path)
    collected = done
    articles_seen = 0

    print(f"[wiki-dump] Starting. Checkpoint: {done} docs saved.")
    if not dump_path.exists():
        print(f"[wiki-dump] ERROR: dump file not found: {dump_path}")
        print("[wiki-dump] Download with:")
        print(
            "  curl -C - -O https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2"
        )
        sys.exit(1)

    batch: list[dict] = []
    pbar = None
    if HAS_TQDM:
        total = limit if limit else None
        pbar = tqdm(desc="Wikipedia articles", unit="doc", total=total)
        if done > 0:
            pbar.update(done)

    for title, raw_text, timestamp in iter_articles(dump_path):
        articles_seen += 1

        if should_skip(title, raw_text):
            continue

        clean = clean_wikitext(raw_text)
        if count_words(clean) < MIN_WORDS:
            continue

        # Parse year from timestamp (YYYY-MM-DDThh:mm:ssZ)
        try:
            year = int(timestamp[:4])
        except (ValueError, TypeError):
            year = 2020
        if year > 2021:
            year = 2021  # clamp to pre-2022

        month = int(timestamp[5:7]) if len(timestamp) >= 7 else 1
        day = int(timestamp[8:10]) if len(timestamp) >= 10 else 1
        ts = format_timestamp(year, month, day)

        slug = title.replace(" ", "_")
        url = f"https://en.wikipedia.org/wiki/{slug}"

        docs = chunk_article(title, clean, url, ts, year)
        for doc in docs:
            batch.append(doc)
            collected += 1
            if pbar:
                pbar.update(1)

            if len(batch) >= BATCH_SIZE:
                append_jsonl(output, batch)
                batch = []

            if collected % CHECKPOINT_EVERY == 0:
                save_checkpoint(checkpoint_path, collected)
                print(f"[wiki-dump] {collected:,} docs ({articles_seen:,} articles seen)...")

            if limit and collected >= limit:
                break

        if limit and collected >= limit:
            break

    if batch:
        append_jsonl(output, batch)
    save_checkpoint(checkpoint_path, collected)

    if pbar:
        pbar.close()

    print(f"[wiki-dump] Done. {collected:,} docs from {articles_seen:,} articles -> {output}")


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest full English Wikipedia XML dump into Cryo JSONL."
    )
    parser.add_argument(
        "--dump",
        type=str,
        default="enwiki-latest-pages-articles.xml.bz2",
        help="Path to Wikipedia XML dump (.xml or .bz2)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw/wikipedia_dump.jsonl",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many docs (None = full dump)",
    )
    args = parser.parse_args()

    dump = Path(args.dump)
    output = Path(args.output)
    checkpoint = Path("data/.checkpoint_wikipedia_dump")
    ingest(dump, output, checkpoint, args.limit)


if __name__ == "__main__":
    main()
