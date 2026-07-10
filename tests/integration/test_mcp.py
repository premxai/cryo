"""Integration tests for the /mcp streamable-HTTP MCP server (mocked auth)."""

import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _fake_key():
    key = MagicMock()
    key.id = uuid.uuid4()
    key.monthly_quota = 1000
    key.rate_limit_per_minute = 60
    key.revoked_at = None
    return key


@asynccontextmanager
async def mcp_client():
    """ASGI client with the app lifespan running (MCP session manager needs it).

    Used as an in-test context manager (not a fixture): anyio cancel scopes in
    the MCP session manager must enter and exit in the same task.
    """
    with (
        patch("backend.db.init_db_pool", new_callable=AsyncMock),
        patch("backend.db.close_db_pool", new_callable=AsyncMock),
        patch("backend.auth.quota.init_redis", new_callable=AsyncMock),
        patch("backend.auth.quota.close_redis", new_callable=AsyncMock),
        patch("backend.search.verify_meilisearch", return_value=True),
    ):
        from backend.main import app
        from backend.mcp_server import mcp

        # StreamableHTTPSessionManager allows one .run() per instance — force a
        # fresh one per lifespan entry (the auth wrapper picks it up lazily).
        mcp._session_manager = None

        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac,
        ):
            yield ac


def _rpc(method: str, params: dict | None = None, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


async def test_mcp_requires_key():
    """No API key → 401 before reaching the MCP transport."""
    async with mcp_client() as client:
        resp = await client.post("/mcp/", json=_rpc("tools/list"), headers=MCP_HEADERS)
    assert resp.status_code == 401
    assert resp.json()["error"]["type"] == "invalid_api_key"


async def test_mcp_rejects_invalid_key():
    """Unknown key → 401 (validation mocked to None)."""
    async with mcp_client() as client:
        with patch("backend.mcp_server._validate_key", new=AsyncMock(return_value=None)):
            resp = await client.post(
                "/mcp/",
                json=_rpc("tools/list"),
                headers={**MCP_HEADERS, "Authorization": "Bearer cryo_sk_bad"},
            )
    assert resp.status_code == 401


async def test_mcp_tools_list():
    """Valid key → tools/list returns the three cryo tools."""
    async with mcp_client() as client:
        with patch("backend.mcp_server._validate_key", new=AsyncMock(return_value=_fake_key())):
            resp = await client.post(
                "/mcp/",
                json=_rpc("tools/list"),
                headers={**MCP_HEADERS, "Authorization": "Bearer cryo_sk_good"},
            )
    assert resp.status_code == 200
    tools = {t["name"] for t in resp.json()["result"]["tools"]}
    assert tools == {"cryo_search", "cryo_get_page", "cryo_find_similar"}


async def test_mcp_tool_call_search():
    """tools/call cryo_search runs the (mocked) search and returns structured content."""
    from backend.models import SearchResponse, SearchResult

    fake = SearchResponse(
        query="old web",
        results=[
            SearchResult(
                id="doc1",
                url="https://example.com/2019/the-old-web",
                text_preview="The <mark>old web</mark> was weird.",
                timestamp="20190101120000",
                year=2019,
                domain="example.com",
                score=0.9,
            )
        ],
        total=1,
        search_time_ms=5,
    )
    async with mcp_client() as client:
        with (
            patch("backend.mcp_server._validate_key", new=AsyncMock(return_value=_fake_key())),
            patch("backend.mcp_server.keyword_search", return_value=fake),
        ):
            resp = await client.post(
                "/mcp/",
                json=_rpc("tools/call", {"name": "cryo_search", "arguments": {"query": "old web"}}),
                headers={**MCP_HEADERS, "Authorization": "Bearer cryo_sk_good"},
            )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result.get("isError") is not True
    # dict returns arrive as JSON text content (structuredContent needs typed returns)
    structured = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    assert structured["total"] == 1
    assert structured["results"][0]["id"] == "doc1"
    assert "<mark>" not in structured["results"][0]["text"]
