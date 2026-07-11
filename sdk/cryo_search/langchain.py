"""LangChain tool adapters — `pip install "cryo-search[langchain]"`.

Usage:
    from cryo_search.langchain import CryoSearchTool, CryoAnswerTool

    tools = [CryoSearchTool(api_key="cryo_sk_..."), CryoAnswerTool(api_key="cryo_sk_...")]
"""

try:
    from langchain_core.tools import BaseTool
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        'LangChain adapters need langchain-core: pip install "cryo-search[langchain]"'
    ) from exc

from cryo_search.client import CryoClient


def _client_for(tool: "BaseTool") -> CryoClient:
    if tool._client is None:
        tool._client = CryoClient(api_key=tool.api_key, base_url=tool.base_url)
    return tool._client


class CryoSearchTool(BaseTool):
    """Search the verified pre-2022 human web (no AI-generated content)."""

    name: str = "cryo_search"
    description: str = (
        "Search an archive of verified pre-2022 human-written web content. "
        "Use for historical facts, pre-AI-era opinions, or when you need sources "
        "that provably predate generative AI. Input: a search query string."
    )
    api_key: str
    base_url: str = "https://api.cryoweb.xyz"
    num_results: int = 5
    _client: CryoClient | None = None

    def _run(self, query: str) -> str:
        results = _client_for(self).search(query, num_results=self.num_results)
        if not results:
            return "No results in the frozen archive."
        lines = []
        for r in results:
            score = f" (human score {r.human_score:.2f})" if r.human_score is not None else ""
            lines.append(f"- {r.url} [{r.published_year}]{score}\n  {r.text[:200]}")
        return "\n".join(lines)


class CryoAnswerTool(BaseTool):
    """Ask the pre-AI web: grounded answers with frozen, provable citations."""

    name: str = "cryo_answer"
    description: str = (
        "Answer a question using ONLY archived pre-2022 web pages. Every citation "
        "is an immutable snapshot that predates generative AI — use when source "
        "provenance matters. Input: a question string."
    )
    api_key: str
    base_url: str = "https://api.cryoweb.xyz"
    _client: CryoClient | None = None

    def _run(self, query: str) -> str:
        result = _client_for(self).answer(query)
        cites = "\n".join(
            f"  [{c.index}] {c.url} (frozen {c.timestamp[:8]}) {c.archive_url}"
            for c in result.citations
        )
        return f"{result.answer}\n\nSources:\n{cites}"
