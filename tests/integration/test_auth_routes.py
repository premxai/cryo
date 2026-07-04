"""Integration tests for dashboard auth routes (mocked DB + email)."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
async def db_client(client):
    """Client with the DB dependency mocked out."""
    from backend.db import get_db
    from backend.main import app

    session = AsyncMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    yield client, session
    app.dependency_overrides.pop(get_db, None)


async def test_magic_link_request_generic_response(db_client):
    """Requesting a link stores a token and returns a generic message."""
    client, session = db_client
    with patch(
        "backend.api.auth_routes.send_magic_link", new=AsyncMock(return_value=True)
    ) as mock_send:
        resp = await client.post("/v1/auth/magic-link", json={"email": "dev@example.com"})
    assert resp.status_code == 200
    assert "email" in resp.json()["message"].lower()
    session.add.assert_called_once()
    mock_send.assert_awaited_once()
    # The emailed link carries the raw token, never the hash
    link = mock_send.await_args.args[1]
    assert "#/verify?token=" in link


async def test_magic_link_rejects_bad_email(db_client):
    client, _ = db_client
    resp = await client.post("/v1/auth/magic-link", json={"email": "not-an-email"})
    assert resp.status_code == 422


async def test_keys_require_session(client):
    """Key management without a session token → 401 invalid_session."""
    resp = await client.get("/v1/auth/keys")
    assert resp.status_code == 401
    assert resp.json()["error"]["type"] == "invalid_session"


async def test_keys_reject_api_key_as_session(client):
    """An API key is not a session token."""
    resp = await client.get(
        "/v1/auth/keys", headers={"Authorization": "Bearer cryo_sk_notasession"}
    )
    assert resp.status_code == 401
