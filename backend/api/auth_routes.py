"""Dashboard key management, scoped to a Clerk-authenticated user.

User signup/login (email/password) is handled by Clerk on the frontend; here we
only verify the Clerk JWT and manage the account's API keys.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.clerk import require_clerk_user
from backend.auth.keys import generate_api_key
from backend.auth.models import ApiKey, User
from backend.config import settings
from backend.db import get_db
from backend.errors import APIError

logger = structlog.get_logger()

router = APIRouter(prefix="/v1/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class AccountInfo(BaseModel):
    """The signed-in account, echoed back to the dashboard."""

    email: str
    name: str | None


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


# ── Account ───────────────────────────────────────────────────────────────────


@router.get("/me", response_model=AccountInfo, summary="Who am I")
async def whoami(user: Annotated[User, Depends(require_clerk_user)]) -> AccountInfo:
    """Confirm the Clerk session and return the account profile."""
    return AccountInfo(email=user.email, name=user.name)


# ── Key management (Clerk-scoped) ─────────────────────────────────────────────


@router.get("/keys", response_model=list[KeyInfo], summary="List your API keys")
async def list_keys(
    user: Annotated[User, Depends(require_clerk_user)],
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
    user: Annotated[User, Depends(require_clerk_user)],
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
    user: Annotated[User, Depends(require_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Revoke a key you own (immediate — the key stops authenticating)."""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    key = result.scalar_one_or_none()
    if key is None:
        raise APIError(404, "key_not_found", "No such key on this account")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(UTC)
        await db.commit()
        logger.info("cryo.auth.key_revoked", user=str(user.id), prefix=key.key_prefix)
    return {"message": "Key revoked"}
