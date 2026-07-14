"""Integration tests for Clerk-authenticated dashboard routes."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.errors import APIError


@pytest.fixture
async def clerk_client(client):
    """Client with Clerk and database dependencies mocked."""
    from backend.auth.clerk import require_clerk_user
    from backend.auth.models import User
    from backend.db import get_db
    from backend.main import app

    user = User(
        id=uuid.uuid4(),
        email="dev@example.com",
        name="Dev User",
        auth_user_id="user_test",
    )
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    async def refresh(key):
        key.id = uuid.uuid4()
        key.created_at = datetime.now(UTC)

    session.refresh = AsyncMock(side_effect=refresh)

    async def override_db():
        yield session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_clerk_user] = override_user
    yield client, user, session
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_clerk_user, None)


async def test_whoami_returns_the_clerk_authenticated_account(clerk_client):
    """The dashboard can confirm the Clerk-authenticated account."""
    client, _, _ = clerk_client
    response = await client.get("/v1/auth/me")
    assert response.status_code == 200
    assert response.json() == {"email": "dev@example.com", "name": "Dev User"}


async def test_list_keys_is_scoped_to_the_clerk_user(clerk_client):
    """The authenticated dashboard lists only the current user's keys."""
    client, _, session = clerk_client
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    response = await client.get("/v1/auth/keys")
    assert response.status_code == 200
    assert response.json() == []
    assert session.execute.await_count == 1


async def test_create_key_uses_the_clerk_authenticated_account(clerk_client):
    """Creating a key associates it with the verified Clerk user."""
    client, user, session = clerk_client
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    response = await client.post("/v1/auth/keys", json={"name": "research-agent"})
    assert response.status_code == 200
    assert response.json()["key"].startswith("cryo_sk_")
    key = session.add.call_args.args[0]
    assert key.user_id == user.id
    assert key.name == "research-agent"
    session.commit.assert_awaited_once()


async def test_keys_require_session(client):
    """Key management without a Clerk session token returns 401."""
    response = await client.get("/v1/auth/keys")
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "invalid_session"


async def test_keys_reject_api_key_as_session(client):
    """An API key cannot be used in place of a Clerk session JWT."""
    with patch(
        "backend.auth.clerk._decode",
        side_effect=APIError(401, "invalid_session", "Sign in again to manage your keys"),
    ):
        response = await client.get(
            "/v1/auth/keys", headers={"Authorization": "Bearer cryo_sk_notasession"}
        )
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "invalid_session"
