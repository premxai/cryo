# cryo-search

Python SDK for [Cryo](https://github.com/premxai/cryo) — the verified pre-AI web as an API.
Every result is provably frozen before 2022 and scored for human authenticity.

## Install

```bash
pip install cryo-search
```

## Quickstart

```python
from cryo_search import CryoClient

cryo = CryoClient(api_key="cryo_sk_YOUR_KEY")

# Search the frozen corpus
for hit in cryo.search("early web culture", num_results=5):
    print(hit.url, hit.published_year, hit.human_score)

# Read a full page (live-fetched from the archive if not stored yet)
page = cryo.contents(urls=["http://paulgraham.com/ds.html"]).results[0]
print(len(page.text), page.links)

# What did a site publish before 2022?
for p in cryo.list_domain("paulgraham.com", limit=20):
    print(p.timestamp[:8], p.url)

# Ask the pre-AI web — every citation predates generative AI
result = cryo.answer("what did people think about remote work?")
print(result.answer)
for c in result.citations:
    print(f"  [{c.index}] {c.archive_url}")
```

## Agent frameworks

```python
# pip install "cryo-search[langchain]"
from cryo_search.langchain import CryoSearchTool, CryoAnswerTool

# pip install "cryo-search[llamaindex]"
from cryo_search import CryoClient
from cryo_search.llamaindex import cryo_tools
```

Rate limits are retried automatically (honoring `Retry-After`). Errors raise
`CryoError` with `.type`, `.message`, and `.status_code`.

Get a free API key at the Cryo dashboard. MCP server available at `/mcp/` for
Claude and other MCP-native agents.
