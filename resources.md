# Cryo — Resources, APIs & Datasets

## Data Sources

### 1. FineWeb (Primary Corpus)
- **What:** Common Crawl pre-cleaned, 15T tokens, best quality web text
- **Why:** Already cleaned + deduplicated, pre-2022 subset available via crawl field
- **URL:** https://huggingface.co/datasets/HuggingFaceFW/fineweb
- **Usage:**
  ```python
  from datasets import load_dataset
  ds = load_dataset("HuggingFaceFW/fineweb", split="train", streaming=True)
  # Filter: sample["crawl"].startswith("CC-MAIN-2021") or earlier
  ```
- **Cost:** Free
- **Size:** Stream only what you need — stop at 100k for MVP

### 2. Wayback Machine CDX API (Live Fallback)
- **What:** Index of 800B archived pages, queryable instantly
- **Why:** Zero storage cost, Day 1 MVP, good fallback
- **URL:** http://web.archive.org/cdx/search/cdx
- **Usage:**
  ```python
  params = {
    "url": f"*{query}*",
    "output": "json",
    "to": "20211231",
    "limit": 20,
    "fl": "original,timestamp,statuscode",
    "filter": "statuscode:200"
  }
  # Fetch content: https://web.archive.org/web/{timestamp}/{url}
  ```
- **Rate limit:** ~1 req/sec, be polite
- **Cost:** Free

### 3. Wikipedia Dump (Cryo Certified Tier)
- **What:** Full English Wikipedia, 100% human-written, versioned
- **Why:** Highest trust content, use as "Cryo Certified" baseline
- **URL:** https://dumps.wikimedia.org/enwiki/20211201/
- **File:** enwiki-20211201-pages-articles.xml.bz2 (~21GB compressed)
- **Parse with:** `mwparserfromhell` library
- **Cost:** Free

### 4. HackerNews Archive (Algolia API)
- **What:** 30M posts + comments from 2006, pure human tech discourse
- **Why:** High quality, structured, timestamped, free API
- **URL:** https://hn.algolia.com/api/v1/search
- **Usage:**
  ```python
  params = {
    "query": query,
    "tags": "story",
    "numericFilters": "created_at_i<1640995200"  # before Jan 1 2022
  }
  GET https://hn.algolia.com/api/v1/search
  ```
- **Cost:** Free, no auth needed

---

## AI Detection APIs

### GPTZero (Primary)
- **URL:** https://api.gptzero.me/v2/predict/text
- **Auth:** Header `x-api-key: $GPTZERO_API_KEY`
- **Request:**
  ```json
  {"document": "text to analyze"}
  ```
- **Response key:** `completely_generated_prob` (0-1, higher = more AI)
- **Human score:** `1 - completely_generated_prob`
- **Free tier:** 150 req/day
- **Paid:** $10/month for 2000 req/day
- **Sign up:** https://gptzero.me

### Fallback: Build your own
- Fine-tune a small classifier on human vs AI text
- Dataset: HC3 on HuggingFace (human vs ChatGPT responses)
- Model: distilbert-base-uncased, 2-class classification
- Training time: ~1hr on single GPU

---

## Search Infrastructure

### Meilisearch (Keyword Search)
- **What:** Fast, easy full-text search engine
- **Docs:** https://www.meilisearch.com/docs
- **Docker:** `docker run -p 7700:7700 getmeili/meilisearch:latest`
- **Python client:** `pip install meilisearch`
- **Key operations:**
  ```python
  import meilisearch
  client = meilisearch.Client('http://localhost:7700')
  index = client.index('cryo_docs')
  index.add_documents(docs)           # index
  index.search('query', {'limit': 20}) # search
  ```

### Qdrant (Vector Search)
- **What:** Vector database for semantic search
- **Docs:** https://qdrant.tech/documentation/
- **Docker:** `docker run -p 6333:6333 qdrant/qdrant`
- **Python client:** `pip install qdrant-client`
- **Key operations:**
  ```python
  from qdrant_client import QdrantClient
  from qdrant_client.models import Distance, VectorParams, PointStruct
  
  client = QdrantClient("localhost", port=6333)
  client.create_collection("cryo_embeddings",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE))
  client.upsert("cryo_embeddings", points=[
    PointStruct(id=doc_id, vector=embedding, payload=metadata)
  ])
  results = client.search("cryo_embeddings", query_vector=embedding, limit=20)
  ```

---

## ML / Training

### sentence-transformers (Base Embedding Model)
- **Model:** all-MiniLM-L6-v2 (384 dims, fast, good quality)
- **Install:** `pip install sentence-transformers`
- **Usage:**
  ```python
  from sentence_transformers import SentenceTransformer
  model = SentenceTransformer('all-MiniLM-L6-v2')
  embeddings = model.encode(texts, batch_size=512, show_progress_bar=True)
  ```
- **HuggingFace:** https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

### TRL (PPO Training)
- **What:** HuggingFace library for RLHF/RLAIF training
- **Install:** `pip install trl`
- **Docs:** https://huggingface.co/docs/trl
- **Key class:** `trl.PPOTrainer`
- **PPO config starting point:**
  ```python
  from trl import PPOConfig, PPOTrainer
  config = PPOConfig(
    learning_rate=1e-5,
    batch_size=16,
    mini_batch_size=4,
    gradient_accumulation_steps=1,
    optimize_cuda_cache=True,
  )
  ```

### Anthropic Claude API (AI Judge)
- **Model:** claude-sonnet-4-20250514
- **Install:** `pip install anthropic`
- **Usage:**
  ```python
  import anthropic
  client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
  message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=200,
    messages=[{"role": "user", "content": prompt}]
  )
  response_text = message.content[0].text
  ```
- **Cost control:** Cache ALL calls. Never call twice for same (doc_id, query) pair.

---

## Infrastructure

### Railway (Backend Hosting)
- **URL:** https://railway.app
- **Free tier:** $5/month credit
- **Deploy:**
  ```bash
  npm install -g @railway/cli
  railway login
  railway init
  railway up
  railway variables set ANTHROPIC_API_KEY=...
  ```
- **Services to deploy:** FastAPI backend, PostgreSQL, Redis, Meilisearch, Qdrant

### Vercel (Frontend Hosting)
- **URL:** https://vercel.com
- **Free tier:** Unlimited hobby projects
- **Deploy:**
  ```bash
  npm install -g vercel
  cd frontend && vercel deploy
  ```

### Docker Compose (Local Dev)
- All services defined in docker-compose.yml at project root
- `docker-compose up -d` starts everything
- `docker-compose down` stops everything

---

## Python Dependencies
```txt
# requirements.txt
fastapi==0.115.0
uvicorn==0.30.0
httpx==0.27.0
meilisearch==0.31.0
qdrant-client==1.10.0
sentence-transformers==3.0.0
transformers==4.44.0
trl==0.9.0
torch==2.4.0
datasets==2.20.0
anthropic==0.34.0
psycopg2-binary==2.9.9
redis==5.0.8
pydantic==2.8.0
tqdm==4.66.0
python-dotenv==1.0.1
mwparserfromhell==0.6.6
```

---

## Useful References
- Exa (target company): https://exa.ai
- Exa search API docs: https://docs.exa.ai
- TRL PPO tutorial: https://huggingface.co/docs/trl/ppo_trainer
- FineWeb paper: https://huggingface.co/spaces/HuggingFaceFW/blogpost-fineweb-v1
- Constitutional AI (RLAIF paper): https://arxiv.org/abs/2212.08073
- Sentence transformers docs: https://www.sbert.net
