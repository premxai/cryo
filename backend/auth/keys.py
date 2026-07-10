"""API key generation, hashing, and the require_api_key FastAPI dependency."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import structlog
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.models import ApiKey
from backend.db import get_db
from backend.errors import APIError

logger = structlog.get_logger()

KEY_PREFIX = "cryo_sk_"
LAST_USED_UPDATE_INTERVAL = timedelta(minutes=1)  # avoid a DB write on every request


def generate_api_key() -> tuple[str, str, str]:
    """Create a new API key.

    Returns:
        (full_key, key_hash, display_prefix) — the full key is shown to the
        user exactly once; only the SHA-256 hash is persisted.
    """
    full_key = KEY_PREFIX + secrets.token_urlsafe(32)
    return full_key, hash_key(full_key), full_key[:12]


def hash_key(key: str) -> str:
    """SHA-256 hex digest of a presented key — used for O(1) indexed lookup."""
    return hashlib.sha256(key.encode()).hexdigest()


def extract_key_from_request(request: Request) -> str | None:
    """Pull the API key from Authorization: Bearer or x-api-key header."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.headers.get("x-api-key") or None


async def require_api_key(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiKey:
    """FastAPI dependency: authenticate the request and return its ApiKey record.

    Raises:
        APIError 401 when the key is missing, unknown, or revoked.
    """
    presented = extract_key_from_request(request)
    if presented is None:
        raise APIError(
            401, "missing_api_key", "Pass your API key as 'Authorization: Bearer cryo_sk_...'"
        )

    try:
        result = await db.execute(select(ApiKey).where(ApiKey.key_hash == hash_key(presented)))
    except APIError:
        raise
    except Exception as exc:
        logger.error("cryo.auth.db_unavailable", error=str(exc))
        raise APIError(
            503, "auth_unavailable", "Authentication backend is temporarily unavailable"
        ) from exc

    key = result.scalar_one_or_none()
    if key is None or key.revoked_at is not None:
        logger.warning("cryo.auth.invalid_key", prefix=presented[:12])
        raise APIError(401, "invalid_api_key", "API key is invalid or has been revoked")

    await _touch_last_used(db, key)
    request.state.api_key = key
    return key


async def _touch_last_used(db: AsyncSession, key: ApiKey) -> None:
    """Update last_used_at, at most once per LAST_USED_UPDATE_INTERVAL."""
    now = datetime.now(UTC)
    if key.last_used_at is not None and now - key.last_used_at < LAST_USED_UPDATE_INTERVAL:
        return
    key.last_used_at = now
    await db.commit()
