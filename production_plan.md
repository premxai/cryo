# Cryo — Ultimate Production-Ready Plan

> This supersedes `plan.md`. Every decision below is grounded in 2024-2025 production consensus
> across FastAPI, sentence-transformers, TRL, Qdrant, and Anthropic APIs.

---

## Overview: What "Production-Ready" Means for Cryo

The original 10-day plan ships a working prototype. This plan ships something you can
point real users at — with observability, security, zero-downtime deploys, CI/CD, and
a tested RLAIF loop. It adds ~8 phases on top of the prototype plan.

```
Phase 0  — Foundation & Tooling         (before any code)
Phase 1  — Data Pipeline                (Day 1-2, hardened)
Phase 2  — Search Infrastructure        (Day 2-3, production Qdrant/Meili)
Phase 3  — Backend API                  (Day 3-5, production FastAPI)
Phase 4  — Authenticity + Judge         (Day 5-6)
Phase 5  — Embedding + RLAIF Training   (Day 6-8)
Phase 6  — Eval Framework               (Day 8)
Phase 7  — Frontend                     (Day 9)
Phase 8  — Observability & Monitoring   (Day 9-10, parallel)
Phase 9  — Security Hardening           (Day 10, parallel)
Phase 10 — CI/CD Pipeline               (Day 10, parallel)
Phase 11 — Deploy                       (Day 11)
```

---

## Phase 0 — Foundation & Tooling

### 0.1 Project Scaffolding

```
cryo/
├── backend/
│   ├── main.py
│   ├── search.py
│   ├── judge.py
│   ├── models.py
│   ├── config.py          ← pydantic-settings config
│   └── db.py              ← async SQLAlchemy engine + session
├── pipeline/
│   ├── download.py
│   ├── index.py
│   ├── embed.py
│   └── scorer.py
├── training/
│   ├── collect.py
│   ├── reward.py
│   └── train.py
├── eval/
│   ├── benchmark.py
│   ├── ablation.py
│   └── results/
├── frontend/
│   └── src/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── quality/           ← golden-set regression tests
├── migrations/            ← Alembic migrations
│   └── alembic.ini
├── .github/
│   └── workflows/
│       └── ci.yml
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
├── pyproject.toml         ← replaces requirements.txt
├── uv.lock
├── .env.example
├── .dockerignore
├── .gitignore
└── CLAUDE.md
```

### 0.2 Dependency Management — Switch to uv + pyproject.toml

Replace `requirements.txt` with `pyproject.toml`. Use `uv` (10-100x faster than pip):

```bash
pip install uv
uv init
```

```toml
# pyproject.toml
[project]
name = "cryo"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "gunicorn>=22.0",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "httpx>=0.27",
    "structlog>=24.2",
    "slowapi>=0.1.9",
    "prometheus-fastapi-instrumentator>=2.0",
    "opentelemetry-sdk>=1.24",
    "opentelemetry-instrumentation-fastapi>=0.45b0",
    "arq>=0.25",
    "redis[hiredis]>=5.0",
    "meilisearch>=0.31",
    "qdrant-client>=1.10",
    "sentence-transformers>=3.0",
    "transformers>=4.44",
    "trl>=0.9",
    "torch>=2.4",
    "datasets>=2.20",
    "anthropic>=0.34",
    "tqdm>=4.66",
    "python-dotenv>=1.0.1",
    "mwparserfromhell>=0.6.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "httpx>=0.27",       # for TestClient
    "ruff>=0.4",
    "mypy>=1.10",
    "testcontainers>=4.0",
]
```

### 0.3 Config via pydantic-settings

```python
# backend/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    gptzero_api_key: str
    meilisearch_url: str = "http://localhost:7700"
    meilisearch_key: str = "cryo_dev_key"
    qdrant_url: str = "http://localhost:6333"
    database_url: str = "postgresql+asyncpg://postgres:cryo@localhost:5432/cryo"
    redis_url: str = "redis://localhost:6379"
    env: str = "development"
    log_level: str = "INFO"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_cache_ttl_seconds: int = 86400

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

### 0.4 Alembic Setup

```bash
uv run alembic init migrations
```

All DB schema changes go through Alembic migrations — never `Base.metadata.create_all()` in production.

---

## Phase 1 — Data Pipeline (Hardened)

### 1.1 download.py (unchanged logic, hardened execution)

- Add `tqdm` progress bars ✓ (already in plan)
- Add checkpoint/resume: save last processed index to `data/.checkpoint`
- Wrap HuggingFace streaming in a `try/except` with exponential backoff (network drops mid-stream)
- Validate each doc before saving: `id`, `url`, `text`, `timestamp` must be present
- Log malformed/skipped docs count to structlog at end

### 1.2 Output validation

After download, run a quick validation pass:
```bash
python pipeline/validate.py --path data/raw/ --expected 100000
```
- Checks: file count, total docs, no empty text fields, year filter applied

---

## Phase 2 — Search Infrastructure (Production)

### 2.1 Meilisearch — Production Config

```yaml
# docker-compose.prod.yml
meilisearch:
  image: getmeili/meilisearch:v1.8
  environment:
    - MEILI_MASTER_KEY=${MEILISEARCH_KEY}
    - MEILI_ENV=production          # disables /stats leaking index details
    - MEILI_LOG_LEVEL=WARN
  volumes:
    - meilisearch_data:/meili_data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:7700/health"]
    interval: 30s
    timeout: 5s
    retries: 3
```

### 2.2 Qdrant — Zero-Downtime Re-indexing via Aliases

**Critical for RLAIF:** Every time you re-train the embedding model, you must re-index
all 100k docs. Never drop the live collection mid-search. Use aliases:

```python
# pipeline/reindex.py
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(settings.qdrant_url)

def reindex_with_alias(new_collection: str, embeddings, payloads):
    """Re-index into a new collection, then atomically swap alias."""
    # 1. Create new versioned collection
    client.create_collection(
        collection_name=new_collection,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        on_disk_payload=True,    # save RAM for large payloads
    )
    # 2. Create payload indexes for fast filtered search
    client.create_payload_index(new_collection, "year", "integer")
    client.create_payload_index(new_collection, "domain", "keyword")

    # 3. Bulk upsert (background job)
    # ...

    # 4. Atomic alias swap — zero downtime
    client.update_collection_aliases(change_aliases_operations=[
        {"delete_alias": {"alias_name": "cryo_embeddings"}},
        {"create_alias": {"collection_name": new_collection,
                          "alias_name": "cryo_embeddings"}},
    ])

# App code ALWAYS queries the alias, never the versioned name:
results = client.search("cryo_embeddings", query_vector=embedding, limit=20)
```

### 2.3 Qdrant Snapshots (Backup)

Add a daily snapshot job. Run as a cron or GitHub Actions scheduled workflow:
```bash
curl -X POST http://localhost:6333/collections/cryo_embeddings/snapshots
# Then upload snapshot to S3/Backblaze B2
```

---

## Phase 3 — Backend API (Production FastAPI)

### 3.1 Lifespan Context (replaces @on_event)

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
import structlog

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("cryo.startup", env=settings.env)
    await init_db_pool()
    load_embedding_model()   # load once, never per-request
    warmup_embedding_model() # 5 dummy calls to pre-allocate CUDA memory
    yield
    # Shutdown
    await close_db_pool()
    logger.info("cryo.shutdown")

app = FastAPI(title="Cryo API", lifespan=lifespan)
```

### 3.2 Embedding Model — Never Block the Event Loop

```python
# backend/embedder.py
import asyncio
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None

def load_embedding_model():
    global _model
    _model = SentenceTransformer(settings.embedding_model)

async def embed_async(texts: list[str]) -> list[list[float]]:
    """Run encode() in thread pool — never block async event loop."""
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(
        None, lambda: _model.encode(texts, normalize_embeddings=True)
    )
    return embeddings.tolist()
```

### 3.3 Embedding Cache (Redis, two-tier)

```python
import hashlib, redis.asyncio as redis, numpy as np

_redis: redis.Redis | None = None

async def get_or_embed(text: str) -> list[float]:
    """SHA-256 keyed Redis cache for embeddings."""
    key = "emb:" + hashlib.sha256(text.encode()).hexdigest()
    cached = await _redis.get(key)
    if cached:
        return np.frombuffer(cached, dtype=np.float32).tolist()
    emb = await embed_async([text])
    await _redis.setex(key, settings.embedding_cache_ttl_seconds,
                       np.array(emb[0], dtype=np.float32).tobytes())
    return emb[0]
```

### 3.4 Structured Logging (structlog)

```python
# backend/logging_config.py
import logging, structlog

def configure_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
    )
```

Add a request middleware to bind `request_id` to every log line:
```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response
```

### 3.5 Rate Limiting

```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis

@app.on_event("startup")
async def init_rate_limiter():
    r = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(r)

# Cost-based limits: semantic search costs 5x keyword search
@app.get("/search", dependencies=[Depends(RateLimiter(times=60, seconds=60))])
async def keyword_search(q: str, limit: int = 20): ...

@app.get("/semantic-search", dependencies=[Depends(RateLimiter(times=12, seconds=60))])
async def semantic_search(q: str, limit: int = 20): ...
```

### 3.6 Input Validation (Pydantic)

```python
# backend/models.py
from pydantic import BaseModel, Field, field_validator

class SearchQuery(BaseModel):
    q: str = Field(..., min_length=1, max_length=500)
    year_max: int = Field(default=2021, ge=2000, le=2021)
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("q")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        v = v.replace("\x00", "").strip()
        if not v:
            raise ValueError("Query is empty after sanitization")
        return v
```

### 3.7 Health Checks

```python
@app.get("/healthz/live")
async def liveness():
    return {"status": "ok"}

@app.get("/healthz/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception:
        raise HTTPException(503, detail="Database unavailable")
```

### 3.8 CORS — Lock Down in Production

```python
import os

origins = (
    ["*"] if settings.env == "development"
    else ["https://cryo.vercel.app", "https://yourdomain.com"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET"],   # Cryo is read-only
    allow_headers=["Content-Type"],
)
```

### 3.9 Global Error Handler

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("cryo.unhandled_exception", exc_info=exc, path=str(request.url))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

### 3.10 Async PostgreSQL (asyncpg + SQLAlchemy 2.0)

```python
# backend/db.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,    # validates connections before use
    pool_recycle=3600,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

---

## Phase 4 — Authenticity Scoring + Judge (Hardened)

### 4.1 GPTZero — Graceful Degradation

- Return `human_score: null` on API failure — don't break search
- Rate limit: add `asyncio.sleep(0.7)` between calls (150 req/day free tier)
- Cache in PostgreSQL on first score; never call twice for same `doc_id`

### 4.2 Claude Judge — Cost-Optimized

**Use claude-3-5-haiku-20241022 for bulk RLAIF scoring** (10x cheaper than Sonnet, sufficient for pairwise ranking):

```python
# backend/judge.py
JUDGE_MODEL = "claude-3-5-haiku-20241022"  # Haiku for bulk; Sonnet for final eval
```

**Use Anthropic Batches API for offline trajectory scoring** (50% cheaper than sync):

```python
import anthropic

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

def score_trajectories_batch(trajectory_pairs: list[dict]) -> str:
    """Submit batch job for offline trajectory scoring. Returns batch_id."""
    batch = client.beta.messages.batches.create(
        requests=[
            {
                "custom_id": f"traj-{t['doc_id']}-{hash(t['query'])}",
                "params": {
                    "model": JUDGE_MODEL,
                    "max_tokens": 100,   # only need JSON scores
                    "messages": [{"role": "user", "content": build_judge_prompt(t)}],
                }
            }
            for t in trajectory_pairs
        ]
    )
    return batch.id
```

**Use prompt caching** for the long judge system prompt (saves ~90% on system tokens):

```python
response = client.messages.create(
    model=JUDGE_MODEL,
    max_tokens=100,
    system=[{
        "type": "text",
        "text": LONG_JUDGE_SYSTEM_PROMPT,   # >1024 tokens
        "cache_control": {"type": "ephemeral"}
    }],
    messages=[{"role": "user", "content": user_prompt}]
)
```

**Cache ALL calls in PostgreSQL** — never hit Claude twice for same `(doc_id, query)`:

```python
async def score_with_cache(query: str, doc: dict, db: AsyncSession) -> RewardScore:
    cached = await db.execute(
        select(RewardScores).where(
            RewardScores.doc_id == doc["id"],
            RewardScores.query == query
        )
    )
    if row := cached.scalar_one_or_none():
        return RewardScore.from_orm(row)
    score = await call_claude_judge(query, doc)
    db.add(RewardScores(**score.dict(), doc_id=doc["id"], query=query))
    await db.commit()
    return score
```

---

## Phase 5 — Embedding + RLAIF Training (Production ML)

### 5.1 TRL PPO — Stable Config

Known pitfalls and how to avoid them:

| Pitfall | Fix |
|---|---|
| Starting PPO from base model | Always start from an SFT checkpoint |
| KL explosion | Use `use_score_scaling=True`, `score_clip=0.5`, `target_kl=0.1` |
| Event loop blocking | Run `model.encode()` in thread pool, not `async def` |
| Reward hacking | Log qualitative rollout samples every 10 steps to W&B |

```python
# training/train.py
from trl import PPOConfig, PPOTrainer

config = PPOConfig(
    model_name="./models/sft-checkpoint",   # start from SFT, not base
    learning_rate=1.4e-5,
    batch_size=64,
    mini_batch_size=8,
    ppo_epochs=4,
    init_kl_coef=0.2,
    target_kl=0.1,
    cliprange=0.2,
    vf_coef=0.1,
    max_grad_norm=0.5,
    use_score_scaling=True,
    use_score_norm=True,
    score_clip=0.5,
    log_with="wandb",    # real-time training monitoring
)
```

### 5.2 Checkpointing

```python
# Save every 50 PPO steps
if step % 50 == 0:
    trainer.save_pretrained(f"./models/checkpoints/step_{step}")
    # Keep only last 3 checkpoints to save disk
    prune_old_checkpoints("./models/checkpoints/", keep=3)
```

### 5.3 W&B — Training Monitoring

```python
import wandb

wandb.init(project="cryo-rlaif", config=config.to_dict(), tags=["ppo", "v1"])

# Log per step
wandb.log({
    "mean_reward": np.mean(rewards),
    "mean_kl": np.mean(kls),
    "policy_loss": policy_loss,
    "value_loss": value_loss,
    # Qualitative rollout table for reward hacking detection
    "rollouts": wandb.Table(
        columns=["step", "query", "doc_preview", "reward", "authenticity"],
        data=[[step, q, d[:200], r, a]
              for q, d, r, a in zip(queries, docs, rewards, auth_scores)]
    ),
}, step=step)
```

Set W&B alert: `mean_kl > 0.5` → Slack notification → pause training, roll back.

### 5.4 Re-indexing After Training — Zero Downtime

```python
# training/reindex.py
import time

def reindex_after_training(model_path: str):
    """Re-embed all docs with new model and atomically swap Qdrant alias."""
    version = f"cryo_v{int(time.time())}"
    reindex_with_alias(version, new_model_path=model_path)
    logger.info("cryo.reindex.complete", collection=version)
```

---

## Phase 6 — Eval Framework (Unchanged Logic, +Regression Tests)

### 6.1 Golden Set Regression Tests

Beyond the ablation study, maintain a golden set of 50 query/expected-doc pairs.
Run in CI on every model or index change:

```python
# tests/quality/test_regression.py
GOLDEN_SET = [
    ("machine learning tutorial python 2020", "doc_id_123", 3),
    # ... 49 more
]

@pytest.mark.parametrize("query,doc_id,max_rank", GOLDEN_SET)
def test_golden_set(query, doc_id, max_rank):
    results = semantic_search(query, limit=max_rank)
    assert doc_id in [r["id"] for r in results]
```

**Fail CI if MRR@10 drops more than 5% from the registered baseline.**

### 6.2 Property-Based Tests (Never Crash)

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=500))
def test_search_never_500(query):
    response = client.get("/search", params={"q": query})
    assert response.status_code in (200, 422, 429)
```

---

## Phase 7 — Frontend (Unchanged from original plan)

See `plan.md` Day 9. Additions:

- Use `VITE_API_URL` env var (not hardcoded `localhost:8000`) so Vercel build points to Railway URL
- Add error boundary component for search failures
- Add loading skeleton (not just a spinner) for better UX
- Debounce search input — don't fire on every keystroke

---

## Phase 8 — Observability & Monitoring

### 8.1 Prometheus Metrics

```python
# backend/main.py
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Histogram, Counter

search_latency = Histogram(
    "cryo_search_latency_seconds", "Search latency by type",
    ["search_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)
zero_results = Counter("cryo_zero_results_total", "Queries with no results")

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

### 8.2 Grafana Dashboard — Key Panels

| Panel | Metric | Alert Threshold |
|---|---|---|
| p99 Search Latency | `cryo_search_latency_seconds{quantile="0.99"}` | > 2s |
| Error Rate | `rate(http_requests_total{status=~"5.."}[5m])` | > 0.5% |
| Zero Results Rate | `rate(cryo_zero_results_total[5m])` | > 20% of queries |
| Embedding Cache Hit Rate | Custom metric | < 30% |
| Qdrant Memory Usage | Host metric | > 80% RAM |
| Mean RLAIF Reward | From W&B export | Drops 10% |

Use **Grafana Cloud** (free tier covers Cryo's scale) or self-host with the docker-compose.

### 8.3 Alerting

```yaml
# Minimum viable alerting for production
Alerts:
  - P1: service completely down (liveness check fails)
  - P2: error rate > 1% for 5 minutes
  - P2: p99 latency > 3s
  - P3: zero-results rate spike (> 2x normal)
  - P3: KL divergence > 0.5 during training
```

Use **Better Uptime** (free tier) for uptime monitoring + Slack notifications.

---

## Phase 9 — Security Hardening

### 9.1 Dockerfile — Production-Grade

```dockerfile
# ---- Stage 1: build dependencies ----
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install uv==0.4.0
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- Stage 2: runtime ----
FROM python:3.11-slim AS runtime

# Non-root user (mandatory for production)
RUN groupadd --gid 1001 cryo && \
    useradd --uid 1001 --gid cryo --no-create-home cryo

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=cryo:cryo ./backend ./backend

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

USER cryo
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz/live')"

CMD ["gunicorn", "backend.main:app",
     "--workers", "2",
     "--worker-class", "uvicorn.workers.UvicornWorker",
     "--bind", "0.0.0.0:8000",
     "--timeout", "30",
     "--access-logfile", "-",
     "--error-logfile", "-"]
```

```
# .dockerignore
.git
.env*
__pycache__
*.pyc
.pytest_cache
data/
models/
tests/
*.md
```

### 9.2 Secrets — Doppler (Recommended)

For Railway + Vercel, use **Doppler** (free tier):
```bash
brew install dopplerhq/cli/doppler
doppler login
doppler setup   # links to your Doppler project
doppler run -- uvicorn backend.main:app   # injects secrets at runtime
```

Never commit `.env` files. Never bake secrets into Docker images.

### 9.3 Secret Scanning in CI

```yaml
# .github/workflows/ci.yml
- name: Scan for secrets
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 9.4 Dependency Vulnerability Scanning

```bash
uv run pip-audit  # scans all deps for known CVEs
```

Add to CI — fail build on high-severity vulnerabilities.

### 9.5 Cloudflare (Free WAF)

Put Cloudflare in front of the Railway backend:
- Blocks volumetric attacks before they reach your app
- Free DDoS protection
- Hides your Railway origin URL
- Bot detection for scraper abuse

---

## Phase 10 — CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: "pip" }
      - run: pip install ruff mypy
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy backend/ --ignore-missing-imports

  test:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: "pip" }
      - run: pip install uv && uv sync --frozen
      - run: uv run pytest tests/unit tests/integration -v --cov=backend --cov-report=xml --cov-fail-under=75
      - uses: codecov/codecov-action@v4

  quality-regression:
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - run: pip install uv && uv sync --frozen
      - run: uv run pytest tests/quality/ -v   # golden set + MRR check

  docker:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          context: .
          push: ${{ github.ref == 'refs/heads/main' }}
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy:
    runs-on: ubuntu-latest
    needs: [docker, quality-regression]
    if: github.ref == 'refs/heads/main'
    environment: production      # requires manual approval in GitHub UI
    steps:
      - name: Deploy to Railway
        run: curl -X POST "${{ secrets.RAILWAY_DEPLOY_WEBHOOK }}"
      - name: Deploy frontend to Vercel
        run: npx vercel deploy --prod --token=${{ secrets.VERCEL_TOKEN }}
```

**Key CI decisions:**
- `ruff` replaces flake8 + black + isort (same lint, 100x faster)
- Docker layer caching via `type=gha` — cuts rebuild from 5min to 30s
- Manual approval gate on production deploy (GitHub Environments)
- Quality regression tests only run on `main` (too slow for every PR)

---

## Phase 11 — Deploy

### 11.1 Railway — Backend + Databases

```bash
npm install -g @railway/cli
railway login
railway init

# Deploy backend
railway up

# Set all secrets (or sync from Doppler)
railway variables set ANTHROPIC_API_KEY=... GPTZERO_API_KEY=... ...

# Add managed services in Railway UI:
# + PostgreSQL (managed)
# + Redis (managed)
# For Meilisearch + Qdrant: deploy as Railway services from Docker images
```

Railway managed PostgreSQL and Redis are recommended over self-hosted containers —
they handle backups, SSL, and connection pooling automatically.

### 11.2 Vercel — Frontend

```bash
cd frontend
npm run build
npx vercel deploy --prod

# Set environment variable
vercel env add VITE_API_URL   # set to Railway backend URL
```

### 11.3 Domain + Cloudflare

1. Buy domain (Namecheap / Cloudflare Registrar)
2. Point DNS to Vercel (frontend) and Railway (backend, via custom domain)
3. Enable Cloudflare proxy on Railway backend
4. Force HTTPS on both

### 11.4 Pre-Deploy Checklist

- [ ] All secrets in Railway/Doppler, not in code
- [ ] `.env.example` has all required vars with descriptions
- [ ] `alembic upgrade head` runs as Railway deploy step (not in app startup)
- [ ] Health check endpoints verified
- [ ] CORS `allow_origins` set to production frontend URL only
- [ ] Rate limiting active and tested
- [ ] Qdrant collection alias exists (`cryo_embeddings`)
- [ ] Meilisearch `ENV=production` set
- [ ] W&B project accessible
- [ ] GitHub Actions CI passing
- [ ] Cloudflare in front of API

---

## Updated Dependency Versions (2025)

```toml
# These supersede the original requirements.txt versions
fastapi = ">=0.115"
uvicorn = ">=0.30"          # [standard] for websockets
gunicorn = ">=22.0"         # NEW: required for production
pydantic = ">=2.7"
pydantic-settings = ">=2.3" # NEW: replaces manual env loading
sqlalchemy = ">=2.0.30"     # [asyncio] — NEW: replaces psycopg2-binary
asyncpg = ">=0.29"          # NEW: async PostgreSQL driver
alembic = ">=1.13"          # NEW: database migrations
structlog = ">=24.2"        # NEW: structured JSON logging
slowapi = ">=0.1.9"         # NEW: rate limiting
prometheus-fastapi-instrumentator = ">=2.0"  # NEW: metrics
arq = ">=0.25"              # NEW: async background tasks
redis = ">=5.0"             # [hiredis] for performance
anthropic = ">=0.34"        # keep — note: use Haiku for bulk
trl = ">=0.9"               # keep — but use with SFT checkpoint
```

---

## What Changed vs. the Original 10-Day Plan

| Original Plan | Production Plan |
|---|---|
| `uvicorn --reload` in production | Gunicorn + UvicornWorker, N workers |
| `requirements.txt` + pip | `pyproject.toml` + `uv` lockfile |
| `Base.metadata.create_all()` | Alembic migrations |
| `psycopg2-binary` (sync) | `asyncpg` + SQLAlchemy 2.0 async |
| No logging | `structlog` JSON + request_id correlation |
| No rate limiting | `fastapi-limiter` + Redis, cost-based limits |
| CORS: `allow_origins=["*"]` | Explicit origin whitelist |
| Claude Sonnet for all scoring | Haiku for bulk RLAIF, Sonnet for final eval |
| Sync API calls to Claude | Batches API for offline trajectory scoring |
| Drop collection to re-index | Qdrant alias swap — zero downtime |
| No model loading guard | Load once at startup, run_in_executor for inference |
| No tests mentioned | Unit + integration + golden-set regression in CI |
| Manual deploy | GitHub Actions CI/CD with approval gate |
| No secrets mgmt | Doppler, non-root Docker, secret scanning |
| No monitoring | Prometheus + Grafana + Better Uptime alerting |
| Railway default Docker | Multi-stage, non-root Dockerfile |
| No backups | Qdrant snapshots + Railway managed DB backups |
