"""CryoClient — the Python SDK for the Cryo API.

Usage:
    from cryo_search import CryoClient

    cryo = CryoClient(api_key="cryo_sk_...")
    for hit in cryo.search("early web culture"):
        print(hit.url, hit.human_score)
"""

import time

import httpx

from cryo_search.types import (
    Answer,
    Citation,
    ContentsResponse,
    ContentsResult,
    DomainPage,
    SearchResult,
    Usage,
)

DEFAULT_BASE_URL = "https://api.cryoweb.xyz"
RETRYABLE_STATUS = {429, 502, 503}


class CryoError(Exception):
    """A structured API error: .type, .message, .status_code."""

    def __init__(self, status_code: int, error_type: str, message: str) -> None:
        self.status_code = status_code
        self.type = error_type
        self.message = message
        super().__init__(f"[{status_code} {error_type}] {message}")


class CryoClient:
    """Synchronous client for the Cryo API (search the verified pre-AI web)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 90.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    # ── Plumbing ──────────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        """Issue a request with retry on 429/5xx, honoring Retry-After."""
        for attempt in range(self._max_retries + 1):
            resp = self._http.request(method, path, json=json)
            if resp.status_code < 400:
                return resp.json()
            if resp.status_code in RETRYABLE_STATUS and attempt < self._max_retries:
                delay = float(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
                time.sleep(min(delay, 30))
                continue
            self._raise(resp)
        raise CryoError(500, "retries_exhausted", "Request failed after retries")

    def _raise(self, resp: httpx.Response) -> None:
        try:
            err = resp.json().get("error", {})
        except Exception:
            err = {}
        raise CryoError(
            resp.status_code,
            err.get("type", "http_error"),
            err.get("message", resp.text[:200]),
        )

    # ── Endpoints ─────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        num_results: int = 10,
        year_min: int = 2000,
        year_max: int = 2021,
        domain: str | None = None,
        content_type: str | None = None,
    ) -> list[SearchResult]:
        """Hybrid search over the frozen pre-2022 corpus."""
        body = {
            "query": query,
            "num_results": num_results,
            "year_min": year_min,
            "year_max": year_max,
        }
        if domain:
            body["domain"] = domain
        if content_type:
            body["content_type"] = content_type
        data = self._request("POST", "/v1/search", body)
        return [_search_result(r) for r in data["results"]]

    def contents(
        self,
        ids: list[str] | None = None,
        urls: list[str] | None = None,
        timestamp: str | None = None,
        include_links: bool = True,
    ) -> ContentsResponse:
        """Full page text by id or URL; unknown URLs are live-fetched from the archive."""
        body: dict = {"include_links": include_links}
        if ids:
            body["ids"] = ids
        if urls:
            body["urls"] = urls
        if timestamp:
            body["timestamp"] = timestamp
        data = self._request("POST", "/v1/contents", body)
        results = [
            ContentsResult(
                id=r["id"],
                url=r["url"],
                text=r["text"],
                published_year=r["published_year"],
                domain=r["domain"],
                source=r["source"],
                title=r.get("title"),
                links=r.get("links"),
                human_score=r.get("human_score"),
                cryo_certified=r.get("cryo_certified", False),
            )
            for r in data["results"]
        ]
        return ContentsResponse(results=results, errors=data.get("errors", []))

    def find_similar(
        self, id: str | None = None, url: str | None = None, num_results: int = 10
    ) -> list[SearchResult]:
        """Documents semantically similar to a reference document."""
        body: dict = {"num_results": num_results}
        if id:
            body["id"] = id
        if url:
            body["url"] = url
        data = self._request("POST", "/v1/find-similar", body)
        return [_search_result(r) for r in data["results"]]

    def list_domain(self, domain: str, limit: int = 50) -> list[DomainPage]:
        """Enumerate a domain's archived pre-2022 pages."""
        data = self._request("POST", "/v1/list-domain", {"domain": domain, "limit": limit})
        return [DomainPage(**p) for p in data["pages"]]

    def answer(self, query: str, num_sources: int = 6) -> Answer:
        """Ask the pre-AI web: a grounded answer with frozen, provable citations."""
        data = self._request("POST", "/v1/answer", {"query": query, "num_sources": num_sources})
        return Answer(
            answer=data["answer"],
            citations=[Citation(**c) for c in data["citations"]],
            model=data["model"],
            cached=data.get("cached", False),
        )

    def usage(self) -> Usage:
        """Current-month quota consumption for this key."""
        data = self._request("GET", "/v1/usage")
        return Usage(**data)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> "CryoClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"CryoClient(base_url={self._http.base_url!r})"


def _search_result(r: dict) -> SearchResult:
    return SearchResult(
        id=r["id"],
        url=r["url"],
        text=r["text"],
        published_year=r["published_year"],
        domain=r["domain"],
        title=r.get("title"),
        score=r.get("score"),
        content_type=r.get("content_type"),
        human_score=r.get("human_score"),
        cryo_certified=r.get("cryo_certified", False),
    )
