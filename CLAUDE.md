# Cryo — Authenticated Human Web Search + RLAIF

## What This Project Is
Cryo is a search engine over a frozen, verified human corpus (pre-2022 web content).
It uses RLAIF (RL from AI Feedback) to train an embedding model where the reward signal
is authenticity — not just relevance. Built as a research prototype targeting Exa's
ML Research Engineer role.

## Why It Exists
The internet is being flooded with AI-generated content. Cryo preserves and surfaces
authentic human thought from before the flood. The RLAIF loop trains the retrieval
model to get better at finding genuinely human, high-quality content over time.

## Reference Docs
- Architecture: @docs/architecture.md
- Build plan: @docs/plan.md
- Resources + APIs: @docs/resources.md
- Eval framework: @docs/eval.md

---

## Tech Stack
- **Backend:** Python 3.11, FastAPI, Uvicorn
- **Search:** Meilisearch (keyword), Qdrant (vector/semantic)
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2 base, fine-tuned via RLAIF)
- **RLAIF training:** TRL (PPO), HuggingFace transformers
- **AI Judge:** Anthropic Claude API (claude-sonnet-4-20250514)
- **AI Detection:** GPTZero API
- **Data:** FineWeb (HuggingFace), Wayback CDX API, Wikipedia dumps
- **Database:** PostgreSQL (trajectories, cache), Redis (queue)
- **Frontend:** React + Vite, Tailwind CSS
- **Deploy:** Railway (backend + DBs), Vercel (frontend)
- **Package manager:** pip + venv for Python, npm for frontend

---

## Project Structure
```
cryo/
├── CLAUDE.md               ← you are here
├── docs/
│   ├── architecture.md
│   ├── plan.md
│   ├── resources.md
│   └── eval.md
├── pipeline/
│   ├── download.py         ← FineWeb/Wikipedia → local
│   ├── index.py            ← local docs → Meilisearch + Qdrant
│   └── scorer.py           ← AI detection scoring pipeline
├── backend/
│   ├── main.py             ← FastAPI app entry point
│   ├── search.py           ← Meilisearch + Qdrant query logic
│   ├── judge.py            ← Claude API reward scoring
│   └── models.py           ← Pydantic schemas
├── training/
│   ├── collect.py          ← trajectory collection
│   ├── reward.py           ← RLAIF reward computation
│   └── train.py            ← TRL PPO fine-tuning loop
├── eval/
│   ├── benchmark.py        ← 20 benchmark queries
│   └── ablation.py         ← BM25 vs embedding vs RLAIF comparison
└── frontend/
    └── src/
        ├── App.jsx
        ├── Search.jsx
        └── ResultCard.jsx
```

---

## Key Commands
```bash
# Backend
cd backend && uvicorn main:app --reload --port 8000

# Meilisearch (local dev)
docker run -p 7700:7700 getmeili/meilisearch:latest

# Qdrant (local dev)
docker run -p 6333:6333 qdrant/qdrant

# PostgreSQL (local dev)
docker run -p 5432:5432 -e POSTGRES_PASSWORD=cryo postgres

# Data pipeline
python pipeline/download.py --source fineweb --limit 100000
python pipeline/index.py --batch-size 1000

# Training
python training/collect.py --queries 500
python training/train.py --epochs 3

# Eval
python eval/benchmark.py --compare all

# Frontend
cd frontend && npm run dev
```

---

## Code Style
- Python: type hints everywhere, no bare `except`, use `async/await` for I/O
- Use `httpx` for async HTTP, not `requests`
- Pydantic models for all API request/response shapes
- React: functional components only, hooks only, no class components
- Tailwind for all styling — no inline styles, no CSS files
- Keep functions under 30 lines — split if longer
- Every function needs a docstring

---

## Environment Variables
```
ANTHROPIC_API_KEY=
GPTZERO_API_KEY=
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_KEY=
QDRANT_URL=http://localhost:6333
DATABASE_URL=postgresql://postgres:cryo@localhost:5432/cryo
REDIS_URL=redis://localhost:6379
```

---

## Rules
- Never mock data in the pipeline — use real data sources
- Cache ALL Claude API calls in PostgreSQL — never hit the API twice for same doc
- Always check if Meilisearch/Qdrant are running before indexing
- Run `python -m pytest` before marking any task done
- One feature per commit, clear commit messages
- If a step takes >10 minutes, add a progress bar (use `tqdm`)
- Do not over-engineer — ship working code, then refine
