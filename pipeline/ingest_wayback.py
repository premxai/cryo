"""Ingest pre-2022 web content via the Wayback Machine CDX API.

Uses archive.org's CDX API to enumerate archived URLs for diverse non-tech
domains, then fetches actual page content from Wayback. Produces broadly
diverse documents: food, sports, music, health, travel, parenting, gaming, etc.

Usage:
    python pipeline/ingest_wayback.py --limit 300 --output data/raw/wayback_all.jsonl
    python pipeline/ingest_wayback.py --domains food,health --limit 200 --output data/raw/wayback_food.jsonl
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
    clean_html,
    count_words,
    format_timestamp,
    make_doc_id,
)

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

try:
    import trafilatura

    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

CDX_BASE = "https://web.archive.org/cdx/search/cdx"
WAYBACK_BASE = "https://web.archive.org/web"
CDX_DELAY = 1.0  # seconds between CDX calls
CONTENT_DELAY = 2.5  # seconds between content fetches
DOMAIN_PAUSE = 5.0  # seconds between domains
MIN_WORDS = 200  # minimum words to keep a document
CHECKPOINT_EVERY = 30
BACKOFF_ON_429 = 30.0  # start backoff at 30s on rate limit (not 1s)

# ── Domain catalogue ────────────────────────────────────────────────────────
DOMAIN_CATEGORIES: dict[str, list[str]] = {
    "food": [
        "allrecipes.com",
        "seriouseats.com",
        "bonappetit.com",
        "thekitchn.com",
        "food52.com",
    ],
    "health": [
        "healthline.com",
        "mayoclinic.org",
        "webmd.com",
        "sleepfoundation.org",
        "psychologytoday.com",
    ],
    "sports": [
        "si.com",
        "runnersworld.com",
        "bicycling.com",
        "theathletic.com",
    ],
    "music": [
        "pitchfork.com",
        "rollingstone.com",
        "guitarworld.com",
    ],
    "film": [
        "rogerebert.com",
        "avclub.com",
    ],
    "travel": [
        "lonelyplanet.com",
        "travelandleisure.com",
        "cntraveler.com",
    ],
    "parenting": [
        "parents.com",
        "babycenter.com",
    ],
    "gaming": [
        "polygon.com",
        "kotaku.com",
        "pcgamer.com",
    ],
    "news": [
        "theatlantic.com",
        "newyorker.com",
        "theguardian.com",
    ],
    "books": [
        "lithub.com",
        "goodreads.com",
    ],
    "finance": [
        "investopedia.com",
        "marketwatch.com",
    ],
    "science": [
        "scientificamerican.com",
        "nautil.us",
    ],
    "fashion": [
        "vogue.com",
        "gq.com",
    ],
}

ALL_DOMAINS = [d for domains in DOMAIN_CATEGORIES.values() for d in domains]


def _load_domain_checkpoint(checkpoint_path: Path) -> dict[str, int]:
    """Load per-domain doc counts from JSON checkpoint file."""
    if checkpoint_path.exists():
        try:
            return json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_domain_checkpoint(checkpoint_path: Path, state: dict[str, int]) -> None:
    """Save per-domain doc counts to JSON checkpoint file."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(state), encoding="utf-8")


def _get(url: str, timeout: int = 20) -> bytes:
    """Perform a GET request and return raw bytes."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CryoBot/1.0 (research; contact cryo-research@example.com)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _get_with_backoff(url: str, max_retries: int = 5) -> bytes | None:
    """GET with exponential backoff on 429/503/network errors."""
    delay = BACKOFF_ON_429
    for attempt in range(max_retries):
        try:
            return _get(url)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503):
                wait = delay * (2**attempt)
                print(f"[wayback] Rate limited ({exc.code}), waiting {wait:.0f}s...")
                time.sleep(wait)
            else:
                return None
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2**attempt)
            else:
                return None
    return None


# URL path patterns that indicate junk/non-article content
_JUNK_PATH_RE = re.compile(
    r"(^/?$"  # homepage
    r"|utm_"  # tracking URLs
    r"|[?#]"  # query strings / anchors
    r"|\.(css|js|json|xml|rss|ico|png|jpg|gif|pdf|zip)$"  # static assets
    r"|/tag/"  # tag pages
    r"|/category/"  # category pages
    r"|/page/\d+"  # pagination
    r"|/author/"  # author pages
    r"|/search/"  # search pages
    r"|/wp-content/"  # WordPress assets
    r"|/%20"  # URL encoding artifacts
    r")",
    re.IGNORECASE,
)


def _is_article_url(url: str) -> bool:
    """Return True if the URL looks like an article/content page (not a homepage/junk)."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    path = parsed.path
    # Must have a path with at least 2 meaningful segments
    segments = [s for s in path.split("/") if s]
    if len(segments) < 1:
        return False
    # Path must be reasonably long (actual article URLs have descriptive slugs)
    if len(path) < 8:
        return False
    # Filter junk patterns
    if _JUNK_PATH_RE.search(path) or _JUNK_PATH_RE.search(url):
        return False
    # Last path segment should look like a slug (letters/numbers/dashes)
    last = segments[-1]
    if not re.match(r"^[\w\-]+$", last):
        return False
    # Reject paths where majority of segments are pure numbers (product IDs, pagination)
    numeric_segs = sum(1 for s in segments if s.isdigit())
    if numeric_segs > 1:
        return False
    # Reject hostname:port URLs (Wayback proxy artifact)
    if ":" in urllib.parse.urlparse(url).netloc.split("@")[-1]:
        return False
    # Article URLs usually have a descriptive slug with hyphens
    return not len(last) < 5


def fetch_cdx_urls(domain: str, limit: int = 300) -> list[tuple[str, str]]:
    """Return (original_url, timestamp) pairs from CDX API for a domain."""
    params = urllib.parse.urlencode(
        {
            "url": f"{domain}/*",
            "output": "json",
            "from": "20150101",
            "to": "20211231",
            "fl": "original,timestamp",
            "filter": ["statuscode:200", "mimetype:text/html"],
            "limit": str(limit),
            "collapse": "urlkey",
        },
        doseq=True,
    )
    url = f"{CDX_BASE}?{params}"
    raw = _get_with_backoff(url)
    if not raw:
        return []
    try:
        rows = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    if not rows:
        return []
    # Row 0 is headers: ["original", "timestamp"]
    return [(r[0], r[1]) for r in rows[1:] if len(r) >= 2]


def strip_wayback_toolbar(html: str) -> str:
    """Remove Wayback Machine's injected toolbar from HTML."""
    html = re.sub(
        r"<!-- BEGIN WAYBACK TOOLBAR INSERT -->.*?<!-- END WAYBACK TOOLBAR INSERT -->",
        "",
        html,
        flags=re.DOTALL,
    )
    return html


def extract_text_trafilatura(html: str) -> str | None:
    """Extract main text using trafilatura (strips nav, ads, boilerplate)."""
    if not HAS_TRAFILATURA:
        return None
    result = trafilatura.extract(html, include_comments=False, include_tables=False)
    return result


def extract_text_fallback(html: str) -> str:
    """Fallback text extraction: clean HTML then keep lines with >= 8 words."""
    raw = clean_html(html)
    lines = raw.splitlines()
    good_lines = [ln.strip() for ln in lines if len(ln.split()) >= 8]
    return "\n".join(good_lines)


def fetch_wayback_content(original_url: str, timestamp: str) -> str | None:
    """Fetch page content from Wayback, strip toolbar, extract text."""
    wayback_url = f"{WAYBACK_BASE}/{timestamp}/{original_url}"
    raw = _get_with_backoff(wayback_url, max_retries=3)
    if not raw:
        return None

    # Detect charset from Content-Type header — approximation via meta tag
    try:
        html = raw.decode("utf-8", errors="replace")
    except Exception:
        html = raw.decode("latin-1", errors="replace")

    html = strip_wayback_toolbar(html)

    text = extract_text_trafilatura(html)
    if not text or len(text.split()) < MIN_WORDS:
        text = extract_text_fallback(html)

    return text if text else None


def ts_to_date(timestamp: str) -> tuple[int, int, int]:
    """Parse Wayback timestamp (YYYYMMDDHHmmss) to (year, month, day)."""
    try:
        year = int(timestamp[:4])
        month = int(timestamp[4:6])
        day = int(timestamp[6:8])
        return year, month, day
    except (ValueError, IndexError):
        return 2020, 1, 1


def url_to_domain(url: str) -> str:
    """Extract hostname from a URL."""
    try:
        netloc = urllib.parse.urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return "unknown"


def ingest_domain(
    domain: str,
    per_domain_limit: int,
    output: Path,
    domain_state: dict[str, int],
    checkpoint_path: Path,
) -> int:
    """Ingest one domain. Returns number of docs added this run."""
    already_done = domain_state.get(domain, 0)
    if already_done >= per_domain_limit:
        return 0

    print(f"[wayback] {domain}: fetching CDX index...")
    pairs = fetch_cdx_urls(domain, limit=per_domain_limit * 3)
    time.sleep(CDX_DELAY)

    if not pairs:
        print(f"[wayback] {domain}: no CDX results")
        return 0

    collected = already_done
    batch_buf: list[dict] = []

    for original_url, timestamp in pairs:
        if collected >= per_domain_limit:
            break

        if not _is_article_url(original_url):
            continue

        text = fetch_wayback_content(original_url, timestamp)
        time.sleep(CONTENT_DELAY)

        if not text:
            continue

        wc = count_words(text)
        if wc < MIN_WORDS:
            continue

        year, month, day = ts_to_date(timestamp)
        if year > 2021:
            year = 2021  # clamp to pre-2022

        doc_timestamp = format_timestamp(year, month, day)
        doc = {
            "id": make_doc_id(original_url, doc_timestamp),
            "url": original_url,
            "text": text,
            "timestamp": doc_timestamp,
            "year": year,
            "domain": url_to_domain(original_url) or domain,
            "word_count": wc,
            "content_type": "article",
        }

        batch_buf.append(doc)
        collected += 1

        if len(batch_buf) >= CHECKPOINT_EVERY:
            append_jsonl(output, batch_buf)
            domain_state[domain] = collected
            _save_domain_checkpoint(checkpoint_path, domain_state)
            batch_buf = []

    if batch_buf:
        append_jsonl(output, batch_buf)
        domain_state[domain] = collected
        _save_domain_checkpoint(checkpoint_path, domain_state)

    added = collected - already_done
    print(f"[wayback] {domain}: +{added} docs (total {collected})")
    return added


def ingest(
    domains: list[str],
    total_limit: int,
    output: Path,
    checkpoint_path: Path,
) -> None:
    """Main ingestion loop across all specified domains."""
    domain_state = _load_domain_checkpoint(checkpoint_path)
    already_total = sum(domain_state.get(d, 0) for d in domains)
    print(f"[wayback] Checkpoint: {already_total} docs across {len(domains)} domains")

    per_domain = max(10, total_limit // len(domains))
    grand_total = already_total

    domain_iter = tqdm(domains, desc="Wayback domains", unit="domain") if HAS_TQDM else domains

    for domain in domain_iter:
        if grand_total >= total_limit:
            break
        remaining = total_limit - grand_total
        limit = min(per_domain, remaining)
        added = ingest_domain(domain, limit, output, domain_state, checkpoint_path)
        grand_total += added
        time.sleep(DOMAIN_PAUSE)

    print(f"[wayback] Done. {grand_total} total docs -> {output}")


def parse_domains(arg: str | None) -> list[str]:
    """Parse --domains argument into list of domain strings."""
    if not arg:
        return ALL_DOMAINS
    result: list[str] = []
    for token in arg.split(","):
        token = token.strip()
        if token in DOMAIN_CATEGORIES:
            result.extend(DOMAIN_CATEGORIES[token])
        elif token:
            result.append(token)
    return result or ALL_DOMAINS


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Ingest pre-2022 web content via Wayback Machine.")
    parser.add_argument(
        "--domains",
        type=str,
        default=None,
        help="Comma-separated categories (food,health,sports,...) or domains. Default: all.",
    )
    parser.add_argument(
        "--limit", type=int, default=300, help="Total docs to collect across all domains."
    )
    parser.add_argument("--output", type=str, default="data/raw/wayback_all.jsonl")
    args = parser.parse_args()

    domains = parse_domains(args.domains)
    output = Path(args.output)
    checkpoint = Path("data/.checkpoint_wayback_domains")

    if not HAS_TRAFILATURA:
        print("[wayback] trafilatura not installed — using fallback text extraction.")
        print("[wayback] Install with: pip install trafilatura")

    ingest(domains, args.limit, output, checkpoint)


if __name__ == "__main__":
    main()
