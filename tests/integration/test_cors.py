"""Integration tests for CORS preflight — the dashboard runs cross-origin in prod."""

ALLOWED_ORIGIN = "http://localhost:5173"  # in settings.allowed_origins for dev


async def test_preflight_allows_authorization_and_delete(client):
    """The Vercel dashboard sends Authorization on /v1 calls and DELETE for revokes."""
    resp = await client.options(
        "/v1/auth/keys",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200
    assert "DELETE" in resp.headers.get("access-control-allow-methods", "")
    allowed_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


async def test_preflight_rejects_unknown_origin(client):
    """Preflight from an origin outside the allowlist gets no CORS approval."""
    resp = await client.options(
        "/v1/search",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example"
