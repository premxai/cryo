# Cryo — Eval Framework

## Why Eval Matters Here
This is a research project targeting Exa. The eval system IS part of the research
contribution. A table showing RLAIF improves over baseline is the proof that the
approach works. Don't skip this.

---

## 4-Dimension Scoring

Every search result is scored on:

| Dimension | Weight | What it measures |
|---|---|---|
| **Authenticity** | 40% | Is this genuinely human-written pre-AI content? |
| **Relevance** | 30% | Does this answer the query well? |
| **Quality** | 20% | Is this substantive, well-reasoned, worth reading? |
| **Provenance** | 10% | Is the timestamp credible, does content match the era? |

Total = weighted sum. Range: 0.0 to 1.0.

---

## 20 Benchmark Queries

Diverse topics, realistic queries a researcher/journalist/writer would use:

```json
[
  "machine learning best practices 2020",
  "python async programming guide",
  "climate change renewable energy solutions 2019",
  "startup fundraising advice seed round",
  "deep learning natural language processing survey",
  "remote work productivity tips 2021",
  "bitcoin blockchain technology explained",
  "mental health therapy techniques",
  "kubernetes docker deployment tutorial",
  "history of the internet web development",
  "data science career advice",
  "open source software contributing guide",
  "nutrition science diet research",
  "philosophy consciousness free will",
  "photography composition techniques",
  "economics inequality wealth distribution",
  "cybersecurity password security best practices",
  "urban planning city design",
  "music theory composition fundamentals",
  "writing fiction storytelling craft"
]
```

Save as `data/benchmark_queries.json`

---

## Ablation Study

Run all 3 retrieval systems on all 20 queries.
Score top-10 results per query per system.
Average scores across all queries.

### Expected Output Table
```markdown
## Cryo Ablation Study — Retrieval Method Comparison
Evaluated on 20 benchmark queries, top-10 results per query.
AI Judge: claude-sonnet-4-20250514

| Method          | Authenticity | Relevance | Quality | Provenance | Total | Δ vs BM25 |
|-----------------|-------------|-----------|---------|------------|-------|-----------|
| BM25 (baseline) | 0.xx        | 0.xx      | 0.xx    | 0.xx       | 0.xx  | —         |
| Embedding       | 0.xx        | 0.xx      | 0.xx    | 0.xx       | 0.xx  | +0.xx     |
| RLAIF (ours)    | 0.xx        | 0.xx      | 0.xx    | 0.xx       | 0.xx  | +0.xx     |

Key finding: RLAIF improves authenticity by X% over BM25 baseline.
```

---

## Eval Script Structure

```python
# eval/benchmark.py

import json
from backend.search import keyword_search, semantic_search
from backend.judge import RewardScorer

QUERIES = json.load(open("data/benchmark_queries.json"))
scorer = RewardScorer()

def evaluate_method(method_name: str, search_fn, queries: list) -> dict:
    """Run search method on all queries, return avg scores."""
    all_scores = []
    for query in queries:
        results = search_fn(query, limit=10)
        for doc in results:
            score = scorer.score(query, doc)
            all_scores.append(score)
    
    return {
        "method": method_name,
        "authenticity": mean([s.authenticity for s in all_scores]),
        "relevance": mean([s.relevance for s in all_scores]),
        "quality": mean([s.quality for s in all_scores]),
        "provenance": mean([s.provenance for s in all_scores]),
        "total": mean([s.total for s in all_scores]),
        "n_results": len(all_scores)
    }

# Run all three methods
results = [
    evaluate_method("BM25", keyword_search, QUERIES),
    evaluate_method("Embedding", base_semantic_search, QUERIES),
    evaluate_method("RLAIF", rlaif_semantic_search, QUERIES),
]

# Save to markdown
save_ablation_table(results, "eval/results/ablation_v1.md")
```

---

## Success Criteria

The project is a research success if:
- RLAIF total score > Embedding total score > BM25 total score
- RLAIF authenticity > 0.80 (proving the reward signal worked)
- Mean reward improves across PPO training epochs (learning is happening)
- All 20 benchmark queries return at least 5 relevant results

If RLAIF doesn't beat Embedding baseline:
- Diagnose: check if reward variance is too low (judge always scores ~same)
- Fix: increase reward range — add penalty for low authenticity, bonus for very high
- Retrain with more trajectories (increase from 500 to 2000 queries)

---

## How to Present This to Exa

In your GitHub README and cover letter, frame the eval as:

> "I designed a 4-dimension authenticity-aware eval framework and ran an ablation study
> comparing BM25, base embeddings, and RLAIF-fine-tuned embeddings on 20 diverse queries.
> The RLAIF model improved authenticity scores by X% over the BM25 baseline, demonstrating
> that authenticity can be used as a learnable reward signal for search ranking."

That's a research contribution. That's what they're hiring for.
