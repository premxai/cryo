"""Clerk auth: verify Clerk-issued session JWTs and map them to Cryo users.

The frontend authenticates against Clerk (email/password) and sends the session
token as `Authorization: Bearer <jwt>`. Clerk signs session tokens with RS256;
we verify the signature against Clerk's published JWKS (no shared secret) and
upsert a local `users` row keyed by the Clerk `sub`, so the existing API-key
system keeps working unchanged.

The session token must carry `email` (and ideally `name`) claims — configure
these in the Clerk dashboard under Sessions → "Customize session token":
    { "email": "{{user.primary_email_address}}", "name": "{{user.full_name}}" }
"""

from typing import Annotated

import jwt
import structlog
from fastapi import Depends, Request
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.models import User
from backend.config import settings
from backend.db import get_db
from backend.errors import APIError

logger = structlog.get_logger()

# PyJWKClient caches keys internally; build once and reuse across requests.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Lazily construct the cached JWKS client for the configured Clerk instance."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.clerk_jwks)
    return _jwks_client


def _decode(token: str) -> dict:
    """Verify a Clerk session JWT and return its claims, or raise APIError(401)."""
    if not settings.clerk_jwks:
        raise APIError(503, "auth_not_configured", "Authentication is not configured")
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer or None,
            options={"verify_aud": False, "verify_iss": bool(settings.clerk_issuer)},
        )
    except jwt.ExpiredSignatureError as exc:
        raise APIError(401, "session_expired", "Your session has expired — sign in again") from exc
    except (jwt.InvalidTokenError, Exception) as exc:  # PyJWK errors are not InvalidTokenError
        logger.warning("cryo.auth.jwt_verify_failed", error=str(exc))
        raise APIError(401, "invalid_session", "Sign in again to manage your keys") from exc


async def require_clerk_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """FastAPI dependency: authenticate a Clerk JWT and return the Cryo User.

    Upserts on first sight — matches an existing legacy account by email, then
    attaches the Clerk id so subsequent logins resolve by `sub`.
    """
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token:
        raise APIError(401, "invalid_session", "Sign in again to manage your keys")

    claims = _decode(token)
    sub = claims.get("sub")
    email = (claims.get("email") or "").lower()
    if not sub or not email:
        raise APIError(
            401,
            "invalid_session",
            "Auth token is missing email — add email/name claims to the Clerk session token",
        )
    name = claims.get("name")

    result = await db.execute(select(User).where(User.auth_user_id == sub))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(email=email, name=name, auth_user_id=sub)
            db.add(user)
            logger.info("cryo.auth.user_created", email=email)
        else:
            user.auth_user_id = sub
            if name and not user.name:
                user.name = name
        await db.commit()
        await db.refresh(user)

    if not user.is_active:
        raise APIError(401, "invalid_session", "Account not found or deactivated")
    return user
