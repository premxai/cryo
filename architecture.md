# Cryo — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────┐
│                     CRYO SYSTEM                      │
│                                                      │
│  ┌──────────┐    ┌───────────┐    ┌──────────────┐  │
│  │  React   │───▶│  FastAPI  │───▶│ Meilisearch  │  │
│  │ Frontend │    │  Backend  │    │ (BM25 search)│  │
│  └──────────┘    │           │    └──────────────┘  │
│                  │           │    ┌──────────────┐  │
│                  │           │───▶│   Qdrant     │  │
│                  │           │    │(vector search│  │
│                  │           │    │ RLAIF model) │  │
│                  │           │    └──────────────┘  │
│                  │           │    ┌──────────────┐  │
│                  │           │───▶│  PostgreSQL  │  │
│                  └───────────┘    │ (cache+traj) │  │
│                        │          └──────────────┘  │
│                        ▼                             │
│                  ┌───────────┐                       │
│                  │Claude API │                       │
│                  │(AI Judge) │                       │
│                  └───────────┘                       │
└─────────────────────────────────────────────────────┘
```

---

## RLAIF Training Loop

```
1. COLLECT TRAJECTORIES
   ┌─────────┐     ┌──────────────┐     ┌──────────┐
   │  Query  │────▶│ RLAIF model  │────▶│  Top 20  │
   │  batch  │     │ (Qdrant)     │     │  docs    │
   └─────────┘     └──────────────┘     └──────────┘
                                              │
2. SCORE WITH AI JUDGE                        ▼
   ┌─────────────────┐              ┌──────────────────┐
   │   Claude API    │◀─────────────│  (query, doc)    │
   │   reward model  │              │  pairs           │
   └─────────────────┘              └──────────────────┘
           │
           ▼ reward scores (authenticity, relevance, quality, provenance)
3. PPO UPDATE
   ┌─────────────────────────────────────┐
   │  TRL PPOTrainer                     │
   │  input:  query embeddings           │
   │  output: doc embeddings             │
   │  reward: total_reward (0-1)         │
   │  updates: sentence-transformer      │
   │           weights                   │
   └─────────────────────────────────────┘
           │
           ▼ better embedding model
4. RE-INDEX QDRANT
   Updated model → re-embed all 100k docs → update Qdrant
   Next search iteration is better
```

---

## Reward Function

```python
total_reward = (
    0.40 * authenticity  +  # Is it human-written? (GPTZero + Claude)
    0.30 * relevance     +  # Does it answer the query?
    0.20 * quality       +  # Is it substantive + well-written?
    0.10 * provenance       # Is the timestamp credible?
)
```

Authenticity has highest weight — this is Cryo's core differentiator.

---

## Data Flow

```
FineWeb (HuggingFace)
        │
        ▼ pipeline/download.py
data/raw/*.jsonl (100k docs)
        │
        ├──▶ pipeline/index.py ──▶ Meilisearch (keyword search)
        │
        └──▶ pipeline/embed.py ──▶ Qdrant (vector search)
                                         ▲
                               training/train.py
                               (RLAIF fine-tuning)
                                         ▲
                               training/collect.py
                               (trajectory collection)
                                         ▲
                               backend/judge.py
                               (Claude API scoring)
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/search` | GET | BM25 keyword search over frozen corpus |
| `/semantic-search` | GET | Vector search with RLAIF embedding model |
| `/score` | GET | Score a single doc for authenticity |
| `/health` | GET | Service health check |

### Search Response Shape
```json
{
  "query": "machine learning 2020",
  "results": [
    {
      "id": "doc_abc123",
      "url": "https://example.com/article",
      "text_preview": "First 300 chars of text...",
      "timestamp": "2020-03-15T10:30:00Z",
      "year": 2020,
      "domain": "example.com",
      "human_score": 0.94,
      "cryo_certified": true,
      "reward_scores": {
        "authenticity": 0.92,
        "relevance": 0.88,
        "quality": 0.85,
        "provenance": 0.90,
        "total": 0.89
      }
    }
  ],
  "total": 847,
  "search_time_ms": 23
}
```

---

## Ablation Study Design

Three retrieval systems compared on same 20 benchmark queries:

| System | Retrieval | Model |
|---|---|---|
| BM25 | Meilisearch keyword | None (baseline) |
| Embedding | Qdrant vector search | all-MiniLM-L6-v2 (base) |
| RLAIF | Qdrant vector search | cryo-embeddings-v1 (fine-tuned) |

Each system scored by AI judge on: authenticity, relevance, quality, provenance, total.

**Hypothesis:** RLAIF model > Embedding > BM25 on authenticity and total score.
This is the research contribution — proving authenticity-reward RLAIF improves retrieval.

---

## Key Design Decisions

**Why Meilisearch over Elasticsearch?**
Simpler setup, faster for MVP, good enough for 100k docs. Switch to ES at 10M+ docs.

**Why sentence-transformers over OpenAI embeddings?**
We need to fine-tune the model via PPO. Can't fine-tune OpenAI's API models.
all-MiniLM-L6-v2 is fast (384 dims), open-source, fine-tunable.

**Why PPO over DPO/SFT?**
PPO is the standard for RLHF/RLAIF. Produces a reward-maximizing policy.
DPO requires preference pairs — harder to collect for retrieval.

**Why Claude as the judge?**
Best available model for nuanced authenticity + quality assessment.
Constitutional AI alignment means it understands epistemic quality.
Cache all calls — cost stays low.

**Why 40% weight on authenticity?**
This is Cryo's core value prop. Other search engines optimize for relevance.
We optimize for authenticity FIRST, relevance second. That's the differentiator.
