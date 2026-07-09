# Cryo Corpus Methodology

How documents enter the Cryo corpus, what "pre-2022" and "authentically human"
mean operationally, how authenticity scores are produced, and — importantly —
what this methodology does *not* guarantee. This document is written to be
audited: every claim maps to code in this repository.

## 1. What Cryo is

A frozen, verified corpus of web content published before 2022 — before
generative AI text saturated the web — with a per-document authenticity score.
Served as a search/retrieval API (`/v1`), an MCP tool server (`/mcp`), and as
exportable datasets (`pipeline/export_dataset.py`).

## 2. Sources and the freeze guarantee

Every ingestion path enforces the pre-2022 boundary at the source:

| Source | Enforcement | Code |
|---|---|---|
| FineWeb (Common Crawl) | Only crawl IDs `CC-MAIN-2013` … `CC-MAIN-2021` accepted | `pipeline/download.py` (`VALID_CRAWL_PREFIXES`) |
| Wayback Machine (bulk) | CDX query bounded `to=20211231`, HTTP 200 + text/html only | `pipeline/ingest_wayback.py` (`fetch_cdx_urls`) |
| Wayback Machine (live, `/v1/contents`) | Requested timestamps clamped to `20211231`; post-freeze snapshots rejected even when the archive offers them | `backend/services/wayback.py` (`clamp_timestamp`, `parse_availability`) |
| HackerNews | Algolia API bounded `created_at_i < 1640995200` (2022-01-01 UTC) | `pipeline/ingest_hn.py` |
| Wikipedia, StackExchange, Gutenberg | Pre-2022 dumps / date-bounded API queries | `pipeline/ingest_*.py` |

Documents are content-addressed: `id = sha(url + timestamp)` truncated to 16
hex chars (`pipeline/ingest_utils.make_doc_id`), so a given capture is stable
across re-ingestion. Full text is stored in PostgreSQL (`documents` table);
the Meilisearch index holds a 2,000-character searchable slice.

**Corpus growth is append-only.** Live fetches through `/v1/contents` write
through to the store permanently (`backend/services/contents.py`); existing
documents are never rewritten.

## 3. Authenticity scoring

Each document is scored by an LLM judge (`backend/judge.py`,
`RewardScorer.score_document`) on three dimensions, without reference to any
search query:

- **authenticity** — is this genuinely human-written (not AI-generated,
  machine-translated boilerplate, or scraped spam)?
- **quality** — is it substantive and coherent?
- **provenance** — is the claimed timestamp credible; do style and content
  match the era?

Weights (renormalized from the search-time reward weights, excluding
relevance): authenticity 0.57, quality 0.29, provenance 0.14 (`DOC_WEIGHTS`).

The judge model is pinned in config (`settings.judge_model`, currently
`claude-3-5-haiku-20241022`). Every response is cached on disk keyed by
`(doc_id, __doc__)` — a document is never scored twice, and fallback scores
(used when the API is unavailable) are **never cached**, so degraded runs
cannot contaminate stored scores.

Scores are persisted per document (`human_score` = the judge's authenticity
dimension, `judge_scores` = all dimensions + weighted total, `scored_at`) via
`pipeline/score_corpus.py`, and surfaced on every API result. Documents with
`human_score >= 0.85` are labeled `cryo_certified`.

## 4. What this does NOT guarantee (read this section first if buying)

1. **The authenticity score is an LLM judgment, not ground truth.** A language
   model estimating whether text is human-written is a probabilistic signal
   with known failure modes (formulaic human writing scores low; polished
   pre-2022 marketing copy can read as "AI-like"). Treat scores as a ranking
   signal and filtering threshold, not a certificate.
2. **Single-signal scoring (for now).** An independent statistical AI-detector
   (GPTZero integration exists in `pipeline/scorer.py`) is built but not yet
   part of the shipped scores. Until it is, `human_score` is one model's
   opinion, not an ensemble.
3. **Timestamps are trusted from the archive.** A pre-2022 crawl or Wayback
   capture timestamp is strong evidence content existed then, but pages can
   embed older/newer claimed publication dates than their capture date. The
   provenance dimension estimates this; it does not prove it.
4. **Pre-2022 ≠ zero machine text.** Template boilerplate, machine translation,
   and GPT-2/3-era generated text existed before 2022. The freeze bounds
   *generative-AI-era* contamination; the authenticity score addresses the
   rest probabilistically.
5. **Current scale.** The scored corpus is a research-grade sample (thousands
   of documents), not yet a pretraining-scale dataset. Composition per export
   is documented in the accompanying `stats.json`.

## 5. Reproducing / auditing

```bash
# score any unscored documents (resumable, cached)
python pipeline/score_corpus.py

# export the scored sample + composition stats
python pipeline/export_dataset.py

# inspect any single document end-to-end
curl -X POST <api>/v1/contents -H "Authorization: Bearer <key>" \
  -d '{"ids": ["<doc_id>"]}'   # returns text, source, human_score
```

Each exported row carries the full provenance chain: `url`, capture
`timestamp`, ingestion `source`, all judge dimensions, and `scored_at`. The
judge prompt is in `backend/judge.py::_build_doc_prompt` — auditable and
versioned with this repository.
