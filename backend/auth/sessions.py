"""HMAC-signed dashboard session tokens (no server-side session storage)."""

import hashlib
import hmac
import time
import uuid
from typing import Annotated

import structlog
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.models import User
from backend.config import settings
from backend.db import get_db
from backend.errors import APIError

logger = structlog.get_logger()

SESSION_PREFIX = "cryo_sess_"


def _sign(payload: str) -> str:
    """HMAC-SHA256 signature over the payload using the app session secret."""
    return hmac.new(settings.session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(user_id: uuid.UUID) -> str:
    """Mint a signed session token: cryo_sess_{user_id}.{expires_ts}.{sig}."""
    expires = int(time.time()) + settings.session_ttl_hours * 3600
    payload = f"{user_id}.{expires}"
    return f"{SESSION_PREFIX}{payload}.{_sign(payload)}"


def verify_session_token(token: str) -> uuid.UUID | None:
    """Return the user id for a valid, unexpired session token — else None."""
    if not token.startswith(SESSION_PREFIX):
        return None
    try:
        user_part, expires_part, sig = token[len(SESSION_PREFIX):].rsplit(".", 2)
    except ValueError:
        return None
    payload = f"{user_part}.{expires_part}"
    if not hmac.compare_digest(_sign(payload), sig):
        return None
    if int(expires_part) < time.time():
        return None
    try:
        return uuid.UUID(user_part)
    except ValueError:
        return None


async def require_session(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """FastAPI dependency: authenticate a dashboard session and return the User."""
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    user_id = verify_session_token(token)
    if user_id is None:
        raise APIError(401, "invalid_session", "Sign in again to manage your keys")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user is None:
        raise APIError(401, "invalid_session", "Account not found or deactivated")
    return user
