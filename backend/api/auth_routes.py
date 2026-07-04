"""Dashboard auth + key management: magic-link signup, session-scoped key CRUD."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.keys import generate_api_key, hash_key
from backend.auth.models import ApiKey, MagicLinkToken, User
from backend.auth.sessions import create_session_token, require_session
from backend.config import settings
from backend.db import get_db
from backend.errors import APIError
from backend.services.email import send_magic_link

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class MagicLinkRequest(BaseModel):
    """POST /v1/auth/magic-link body."""

    email: EmailStr


class VerifyRequest(BaseModel):
    """POST /v1/auth/verify body."""

    token: str = Field(..., min_length=16, max_length=128)


class SessionResponse(BaseModel):
    """A signed dashboard session."""

    session_token: str
    email: str


class KeyInfo(BaseModel):
    """A key as shown in the dashboard (never the full secret)."""

    id: uuid.UUID
    key_prefix: str
    name: str
    monthly_quota: int
    rate_limit_per_minute: int
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class NewKeyResponse(BaseModel):
    """Returned once at creation — the only time the full key is visible."""

    key: str
    info: KeyInfo


class CreateKeyRequest(BaseModel):
    """POST /v1/auth/keys body."""

    name: str = Field(default="default", max_length=100)


# ── Magic-link flow ───────────────────────────────────────────────────────────


@router.post("/magic-link", summary="Email a sign-in link")
async def request_magic_link(
    body: MagicLinkRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Create a single-use token and email the sign-in link.

    Always returns 200 with a generic message — never reveals whether an
    account exists.
    """
    raw_token = secrets.token_urlsafe(32)
    db.add(
        MagicLinkToken(
            token_hash=hash_key(raw_token),
            email=body.email.lower(),
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.magic_link_ttl_minutes),
        )
    )
    await db.commit()

    link = f"{settings.public_base_url}/#/verify?token={raw_token}"
    await send_magic_link(body.email, link)
    logger.info("cryo.auth.magic_link_requested", email=body.email)
    return {"message": "Check your email for a sign-in link"}


@router.post("/verify", response_model=SessionResponse, summary="Exchange a magic link for a session")
async def verify_magic_link(
    body: VerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    """Validate a magic-link token, upsert the user, and mint a session token."""
    result = await db.execute(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == hash_key(body.token))
    )
    token = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if token is None or token.used_at is not None or token.expires_at < now:
        raise APIError(401, "invalid_magic_link", "This sign-in link is invalid or expired")
    token.used_at = now

    user_result = await db.execute(select(User).where(User.email == token.email))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(email=token.email)
        db.add(user)
        await db.flush()
        logger.info("cryo.auth.user_created", email=token.email)
    await db.commit()

    return SessionResponse(session_token=create_session_token(user.id), email=user.email)


# ── Key management (session-scoped) ───────────────────────────────────────────


@router.get("/keys", response_model=list[KeyInfo], summary="List your API keys")
async def list_keys(
    user: Annotated[User, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[KeyInfo]:
    """All keys (including revoked) for the signed-in account."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc())
    )
    return [KeyInfo.model_validate(k, from_attributes=True) for k in result.scalars().all()]


@router.post("/keys", response_model=NewKeyResponse, summary="Create a new API key")
async def create_key(
    body: CreateKeyRequest,
    user: Annotated[User, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NewKeyResponse:
    """Mint a key on the free tier. The full key is returned exactly once."""
    active = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None))
    )
    if len(active.scalars().all()) >= 5:
        raise APIError(400, "too_many_keys", "Limit of 5 active keys — revoke one first")

    full_key, key_hash, prefix = generate_api_key()
    key = ApiKey(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=prefix,
        name=body.name,
        monthly_quota=settings.free_tier_monthly_quota,
        rate_limit_per_minute=settings.free_tier_rate_per_minute,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    logger.info("cryo.auth.key_created", user=str(user.id), prefix=prefix)
    return NewKeyResponse(key=full_key, info=KeyInfo.model_validate(key, from_attributes=True))


@router.delete("/keys/{key_id}", summary="Revoke an API key")
async def revoke_key(
    key_id: uuid.UUID,
    user: Annotated[User, Depends(require_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Revoke a key you own (immediate — the key stops authenticating)."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise APIError(404, "key_not_found", "No such key on this account")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        await db.commit()
        logger.info("cryo.auth.key_revoked", user=str(user.id), prefix=key.key_prefix)
    return {"message": "Key revoked"}
