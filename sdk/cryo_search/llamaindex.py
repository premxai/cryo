"""LlamaIndex tool adapters — `pip install "cryo-search[llamaindex]"`.

Usage:
    from cryo_search import CryoClient
    from cryo_search.llamaindex import cryo_tools

    tools = cryo_tools(CryoClient(api_key="cryo_sk_..."))
"""

try:
    from llama_index.core.tools import FunctionTool
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        'LlamaIndex adapters need llama-index-core: pip install "cryo-search[llamaindex]"'
    ) from exc

from cryo_search.client import CryoClient


def cryo_tools(client: CryoClient) -> list["FunctionTool"]:
    """Cryo's search + answer as LlamaIndex FunctionTools."""

    def cryo_search(query: str) -> str:
        """Search verified pre-2022 human web content (no AI-generated text)."""
        results = client.search(query, num_results=5)
        return "\n".join(f"- {r.url} [{r.published_year}]: {r.text[:200]}" for r in results)

    def cryo_answer(query: str) -> str:
        """Answer a question from archived pre-2022 pages with provable citations."""
        result = client.answer(query)
        cites = "\n".join(f"[{c.index}] {c.archive_url}" for c in result.citations)
        return f"{result.answer}\n\nSources:\n{cites}"

    return [
        FunctionTool.from_defaults(fn=cryo_search),
        FunctionTool.from_defaults(fn=cryo_answer),
    ]
