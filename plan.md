# Cryo — Build Plan

## Goal
Ship a working research prototype of Cryo in 10 days using Claude Code.
Each day = one focused session = one working component.
Start a fresh Claude Code session each day with `/clear`.

---

## The Big Picture
```
Day 1-2  → Data + Search (corpus exists, queries work)
Day 3    → Authenticity scoring (AI detection layer)
Day 4    → Reward model (AI judge for RLAIF)
Day 5    → Embedding model + semantic search
Day 6-7  → RLAIF training loop (PPO)
Day 8    → Eval framework + ablation study
Day 9    → Frontend UI
Day 10   → Polish, README, deploy
```

---

## Day 1 — Data Pipeline

**Goal:** 100k real pre-2022 documents indexed and searchable locally.

**Prompt to give Claude Code:**
```
Build pipeline/download.py that:
1. Loads FineWeb dataset from HuggingFace in streaming mode
   dataset = load_dataset("HuggingFaceFW/fineweb", split="train", streaming=True)
2. Filters to only docs where crawl field starts with "CC-MAIN-2021" or earlier
3. Cleans each doc: strip HTML tags, normalize whitespace, remove docs under 100 words
4. Saves to data/raw/ as JSONL files in batches of 10k
5. Stops after 100k documents
6. Shows progress bar with tqdm
Each doc should have: id, url, text, timestamp, year, domain, word_count
```

**Done when:** `data/raw/` has ~10 JSONL files totaling 100k docs.

---

## Day 2 — Indexing + Basic Search API

**Goal:** Documents indexed in Meilisearch, FastAPI returns search results.

**Prompt to give Claude Code:**
```
Build two things:

1. pipeline/index.py that:
   - Reads JSONL files from data/raw/
   - Indexes into Meilisearch at localhost:7700
   - Index name: "cryo_docs"
   - Searchable fields: text, url, domain
   - Filterable fields: year, domain
   - Batch size: 1000 docs per request
   - Shows progress bar

2. backend/main.py + backend/search.py that:
   - FastAPI app with GET /search?q=&year_max=2021&limit=20
   - Queries Meilisearch
   - Returns: [{id, url, text_preview, timestamp, year, domain}]
   - Test with: curl "localhost:8000/search?q=machine+learning"
```

**Done when:** curl returns real results with timestamps.

---

## Day 3 — Authenticity Scoring

**Goal:** Every search result has a human_confidence score.

**Prompt to give Claude Code:**
```
Build pipeline/scorer.py and backend/judge.py that:

1. For each document, call GPTZero API to get AI detection score
   POST https://api.gptzero.me/v2/predict/text
   Headers: x-api-key: $GPTZERO_API_KEY
   Body: {"document": doc.text}
   Returns: completely_generated_prob (0-1, higher = more AI)
   human_score = 1 - completely_generated_prob

2. Cache scores in PostgreSQL table:
   CREATE TABLE doc_scores (
     doc_id TEXT PRIMARY KEY,
     human_score FLOAT,
     scored_at TIMESTAMP,
     raw_response JSONB
   )

3. Add human_score to search results from /search endpoint
   - Only score on first request, use cache after that
   - If GPTZero fails, return human_score: null (don't break search)

4. Add GET /score?doc_id= endpoint to score a single doc on demand
```

**Done when:** Search results include human_score field, scores are cached.

---

## Day 4 — AI Judge (Reward Model)

**Goal:** Claude scores search results on 4 dimensions for RLAIF.

**Prompt to give Claude Code:**
```
Build backend/judge.py with a RewardScorer class that:

Takes: query (str), doc (dict with url, text, timestamp, human_score)
Returns: RewardScore(authenticity, relevance, quality, provenance, total)

Uses Claude API (claude-sonnet-4-20250514) with this prompt:
---
You are evaluating search results for Cryo, a search engine for authentic pre-AI human content.

Query: {query}
Document URL: {url}
Document timestamp: {timestamp}
Document text: {text[:1000]}
GPTZero human score: {human_score}

Rate this document 0.0 to 1.0 on each dimension:
1. authenticity: Is this genuinely human-written? (use GPTZero score + writing style)
2. relevance: Does this document answer the query well?
3. quality: Is this substantive, well-reasoned, worth reading?
4. provenance: Is the timestamp credible? Does the content match the era?

Respond ONLY with valid JSON:
{"authenticity": 0.0, "relevance": 0.0, "quality": 0.0, "provenance": 0.0}
---

Compute total reward:
total = (0.4 * authenticity) + (0.3 * relevance) + (0.2 * quality) + (0.1 * provenance)

Cache all scores in PostgreSQL:
CREATE TABLE reward_scores (
  doc_id TEXT,
  query TEXT,
  authenticity FLOAT,
  relevance FLOAT,
  quality FLOAT,
  provenance FLOAT,
  total FLOAT,
  scored_at TIMESTAMP,
  PRIMARY KEY (doc_id, query)
)
```

**Done when:** RewardScorer returns valid scores, caches in DB.

---

## Day 5 — Embedding Model + Semantic Search

**Goal:** Semantic search endpoint using sentence-transformers.

**Prompt to give Claude Code:**
```
Add semantic search to Cryo:

1. pipeline/embed.py:
   - Load sentence-transformers model: all-MiniLM-L6-v2
   - Embed all 100k docs in batches of 512
   - Store in Qdrant collection "cryo_embeddings"
   - Each point: id=doc_id, vector=embedding, payload={url, timestamp, year}
   - Show progress bar, save checkpoint every 10k docs

2. backend/search.py — add semantic_search function:
   - Embed query using same model
   - Search Qdrant top-50 results
   - Fetch full doc text from Meilisearch by ID
   - Return ranked results

3. backend/main.py — add GET /semantic-search?q=&limit=20 endpoint

4. Test: both /search and /semantic-search work and return different result orderings
```

**Done when:** Semantic search returns meaningfully different results than keyword search.

---

## Day 6-7 — RLAIF Training Loop

**Goal:** PPO fine-tunes the embedding model using reward scores.

**Prompt to give Claude Code (Day 6):**
```
Build training/collect.py that:
1. Takes a list of 500 diverse queries from data/queries.txt
2. For each query: runs semantic search → gets top 20 docs
3. Scores each doc with RewardScorer from backend/judge.py
4. Saves trajectories to PostgreSQL:
   CREATE TABLE trajectories (
     id SERIAL PRIMARY KEY,
     query TEXT,
     doc_id TEXT,
     doc_text TEXT,
     reward FLOAT,
     authenticity FLOAT,
     relevance FLOAT,
     quality FLOAT,
     collected_at TIMESTAMP
   )
5. Run on 100 queries first to test, then full 500
```

**Prompt to give Claude Code (Day 7):**
```
Build training/train.py that:
1. Loads trajectories from PostgreSQL
2. Fine-tunes all-MiniLM-L6-v2 using TRL PPO trainer
   - Query embedding = "query" in PPO
   - Doc embedding = "response" in PPO  
   - reward_scores.total = reward signal
3. Saves fine-tuned model to models/cryo-embeddings-v1/
4. Updates Qdrant collection with new embeddings
5. Logs training metrics: mean_reward per epoch, reward improvement

Use trl.PPOTrainer with default config first, tune hyperparams after.
```

**Done when:** Training completes, mean_reward improves across epochs.

---

## Day 8 — Eval Framework

**Goal:** Prove RLAIF improves search quality with an ablation table.

**Prompt to give Claude Code:**
```
Build eval/benchmark.py + eval/ablation.py:

1. Create data/benchmark_queries.json with 20 diverse queries:
   ["machine learning best practices 2020",
    "python async programming tutorial",
    "climate change solutions 2019",
    ... 17 more covering different topics]

2. For each query, run 3 retrieval methods:
   - BM25: keyword search via Meilisearch
   - Embedding: semantic search with base all-MiniLM-L6-v2
   - RLAIF: semantic search with fine-tuned cryo-embeddings-v1

3. Score top-10 results from each method using RewardScorer
   Metrics per method:
   - mean_total_reward
   - mean_authenticity
   - mean_relevance  
   - mean_quality
   - mean_human_score (GPTZero)

4. Output a markdown table:
   | Method     | Authenticity | Relevance | Quality | Human Score | Total |
   |------------|-------------|-----------|---------|-------------|-------|
   | BM25       | 0.xx        | 0.xx      | 0.xx    | 0.xx        | 0.xx  |
   | Embedding  | 0.xx        | 0.xx      | 0.xx    | 0.xx        | 0.xx  |
   | RLAIF      | 0.xx        | 0.xx      | 0.xx    | 0.xx        | 0.xx  |

Save results to eval/results/ablation_v1.md
```

**Done when:** Table shows RLAIF > Embedding > BM25 on authenticity + total.

---

## Day 9 — Frontend

**Goal:** Clean, minimal search UI that feels archival and cold.

**Prompt to give Claude Code:**
```
Build React frontend in frontend/src/:

Design language: cold, archival, minimal — like a frozen artifact
- Background: very dark navy (#0a0f1a)
- Text: cool white (#e8edf5)  
- Accent: icy blue (#4a9eff)
- Font: Inter or JetBrains Mono for timestamps
- NO rounded corners — everything sharp, geometric

Components:
1. App.jsx — layout wrapper
2. Search.jsx — centered search bar, Cryo logo above it, tagline below:
   "The human web. Preserved."
3. ResultCard.jsx — shows:
   - URL (truncated, icy blue)
   - Timestamp badge (e.g. "Mar 2019") in monospace
   - Human score bar (green → red based on score)
   - Text preview (2-3 lines)
   - Small authenticity badge if human_score > 0.85: "✓ Cryo Certified"

Connect to FastAPI at localhost:8000
Use /semantic-search for results
Show loading state while fetching
```

**Done when:** Search works end to end in browser, looks clean.

---

## Day 10 — Polish + Deploy + README

**Prompt to give Claude Code:**
```
Final polish and deploy:

1. Write README.md with:
   - What Cryo is (2 paragraphs)
   - Architecture diagram in ASCII or Mermaid
   - Ablation results table from eval/results/ablation_v1.md
   - Setup instructions (docker-compose up, pip install, npm install)
   - What's next section (5 future directions)

2. Create docker-compose.yml that starts:
   - Meilisearch
   - Qdrant  
   - PostgreSQL
   - Redis
   All with correct ports and volumes.

3. Deploy backend to Railway:
   - railway init
   - railway up
   - Set all env vars

4. Deploy frontend to Vercel:
   - vercel deploy
   - Point API calls to Railway URL

5. Create .env.example with all required env vars (no values)
```

**Done when:** Live URL exists, README is clean, GitHub repo is public.

---

## Common Fixes
- If Meilisearch returns empty: check index name is exactly "cryo_docs"
- If GPTZero 429 error: add `time.sleep(0.7)` between calls
- If TRL PPO fails: reduce batch_size to 4, learning_rate to 1e-5
- If Qdrant slow: reduce embedding batch size to 128
- If Claude API slow: add `max_tokens=200` to judge calls (we only need JSON)
