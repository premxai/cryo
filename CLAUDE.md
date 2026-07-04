# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is
Cryo is a search engine over a frozen, verified human corpus (pre-2022 web content).
It uses RLAIF (RL from AI Feedback) to train an embedding model where the reward signal
is **authenticity** — not just relevance. Built as a research prototype targeting Exa's
ML Research Engineer role.

The internet is being flooded with AI-generated content. Cryo preserves and surfaces
authentic human thought from before the flood. The RLAIF loop trains the retrieval
model to get better at finding genuinely human, high-quality content over time.

## Reference Docs (at repo root, not in a docs/ folder)
- Architecture: @architecture.md
- Build plan: @plan.md
- Production plan: @production_plan.md
- Resources + APIs: @resources.md
- Eval framework: @eval.md

---

## Milestones (the codebase is built in stages — grep docstrings for `M1`/`M2`/... markers)
- **M1 / M1.5** — BM25 keyword search + facets, suggest, health/readiness probes. *(shipped)*
- **M2** — `/score`: Claude "LLM council" authenticity reward scoring (`backend/judge.py`).
- **M3** — `/semantic-search`: sentence-transformers → Qdrant vector index (`pipeline/embed.py`).
- **M4** — RLAIF PPO fine-tuning of the embedding model (`training/`).

Endpoints marked M2+/M3+ may be partially implemented or fall back to BM25. Check the
function body before assuming a path is live.

---

## Architecture (the parts that span multiple files)

**Request flow:** `frontend/` (React) → FastAPI (`backend/main.py`) → `backend/search.py`.
`main.py` is thin — validation via `Annotated[Query, Depends()]`, error handling, and
observability. All real search logic lives in `search.py`.

**Search is hybrid BM25 + semantic re-rank (NOT two separate stores):**
- Meilisearch (`cryo_docs` index) does the BM25 keyword retrieval and owns all
  facets/filters/highlighting.
- `search.py` fetches `RERANK_CANDIDATES` (50) from Meilisearch, then re-ranks with
  **fastembed** (`BAAI/bge-small-en-v1.5`, CPU) using `0.5 × BM25_rank + 0.5 × cosine`.
  Re-ranking only happens on `sort=relevance`. The embed model is lazy-loaded and
  degrades gracefully to pure BM25 if unavailable.
- `semantic_search()` (the Qdrant + sentence-transformers path) exists for M3 but
  **falls back to Meilisearch BM25** whenever Qdrant or the model isn't present.

**Config is centralized** in `backend/config.py` (pydantic-settings `Settings`, loaded
from `.env`). Never read `os.environ` directly in app code — add a field to `Settings`.
Note `database_url` uses the `postgresql+asyncpg://` driver prefix.

**DB is async and dev-optional** (`backend/db.py`): SQLAlchemy 2.0 + asyncpg pool. A
missing DB is a **warning in development, fatal in production** (`settings.is_production`).
Same graceful-degradation pattern applies to Meilisearch at startup.

**Data pipeline** (`pipeline/`): many `ingest_*.py` sources (Wikipedia, HN, StackExchange,
Gutenberg, Wayback, Common Crawl) all share `ingest_utils.py` (doc-id hashing, HTML
cleaning, JSONL append, checkpointing, backoff) and write JSONL to `data/`. Then
`validate.py` → `index.py` (→ Meilisearch) and/or `embed.py` (→ Qdrant). `scorer.py`
adds GPTZero AI-detection scores.

**RLAIF reward** (`backend/judge.py` + `training/`): scores `(query, doc)` on 4 weighted
dimensions — authenticity 0.40, relevance 0.30, quality 0.20, provenance 0.10. Judge model
is **`claude-3-5-haiku-20241022`** (`settings.judge_model`). Scores are **file-cached**
under `data/cache/judge/` (Postgres cache is aspirational, not yet wired).

**Observability:** structlog (JSON logs, event names like `cryo.search.keyword`), a
per-request `X-Request-ID` middleware, Prometheus `/metrics`, and `/healthz/live`+`/ready`.

**SaaS API layer (`/v1` + `/mcp`)** — the productized, authenticated surface:
- `backend/auth/`: `cryo_sk_` API keys (SHA-256 hash stored, full key shown once),
  per-key Redis fixed-window rate limits + monthly quotas (`quota.py`), durable
  `usage_ledger` in PG, HMAC dashboard sessions (`sessions.py`). Redis follows the
  same dev-optional/prod-fatal startup pattern as the DB.
- `backend/api/v1.py`: POST `/v1/search`, `/v1/contents` (full text from the PG
  `documents` table, live Wayback fallback with write-through + link extraction),
  `/v1/find-similar` (salient-term BM25 recall + fastembed rerank), GET `/v1/usage`.
  Errors are always `{"error": {type, message, request_id}}` via `backend/errors.APIError`.
- `backend/api/auth_routes.py`: magic-link signup (Resend; dev mode logs the link)
  + session-scoped key CRUD. `backend/services/`: wayback/contents/similar/email.
- `backend/mcp_server.py`: FastMCP (streamable HTTP, stateless) mounted at `/mcp`
  behind an API-key ASGI wrapper; tools `cryo_search`/`cryo_get_page`/`cryo_find_similar`.
  The session manager must run inside the app lifespan.
- Schema changes go through **Alembic** (`migrations/`, config reads `Settings`);
  legacy unauthenticated endpoints stay for the demo frontend, hidden from prod docs.

---

## Key Commands

Python uses **`uv`** (see `pyproject.toml`). Dependencies are split into a base group plus
`ml` (torch/transformers/trl/anthropic) and `dev` (pytest/ruff/mypy) extras.

```bash
# Install (base + dev; add ,ml for training work)
uv sync --extra dev            # or: uv pip install -e ".[dev]"

# Local infra — all four services
docker-compose up -d           # meilisearch, qdrant, postgres, redis
# ...or run just Meilisearch from the bundled binary (Windows):
bin/meilisearch.exe --master-key cryo_dev_key

# Backend — run from REPO ROOT (imports use the `backend.` package)
uvicorn backend.main:app --reload --port 8000

# Data pipeline (writes JSONL to data/, then index)
python pipeline/download.py --source fineweb --limit 100000
python pipeline/validate.py
python pipeline/index.py --batch-size 1000     # → Meilisearch
python pipeline/embed.py                        # → Qdrant (M3)
python pipeline/load_documents_pg.py            # → PG documents (for /v1/contents)

# SaaS API
python -m alembic upgrade head                  # apply DB migrations
python pipeline/issue_key.py dev@example.com    # mint an API key (beta path)

# Training (M4)
python training/collect.py
python training/train.py --epochs 3

# Eval
python eval/benchmark.py

# Tests (asyncio_mode=auto; integration tests mock external services)
python -m pytest
python -m pytest tests/unit/test_models.py::test_name -v   # single test
uv run ruff check . && uv run mypy backend                 # lint + types

# Frontend
cd frontend && npm run dev       # Vite on :5173
npm run lint                     # eslint, --max-warnings 0
```

---

## Code Style
- Python: type hints everywhere, no bare `except`, `async/await` for I/O, `httpx` (not
  `requests`). Every function needs a docstring. Ruff line length 100 (E501 ignored).
- Pydantic models (`backend/models.py`) for all API request/response shapes.
- React: functional components + hooks only, no class components.
- Tailwind for all styling — no inline styles, no CSS files.
- Keep functions under ~30 lines — split if longer.

## Rules
- Never mock data in the pipeline — use real data sources.
- Cache ALL Claude/GPTZero API calls — never hit the API twice for the same doc.
- Always check Meilisearch/Qdrant are reachable before indexing (see `index.py` guard).
- Run `python -m pytest` before marking any task done.
- One feature per commit, clear commit messages.
- If a step takes >10 minutes, add a `tqdm` progress bar.
- Do not over-engineer — ship working code, then refine.
