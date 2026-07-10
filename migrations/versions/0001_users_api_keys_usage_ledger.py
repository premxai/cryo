"""users, api_keys, usage_ledger

Revision ID: 0001
Revises:
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("name", sa.String(100), nullable=False, server_default="default"),
        sa.Column("monthly_quota", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="60"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("api_key_id", UUID(as_uuid=True), sa.ForeignKey("api_keys.id"), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("endpoint", sa.String(32), nullable=False),
        sa.Column("request_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint("api_key_id", "month", "endpoint", name="uq_usage_key_month_endpoint"),
    )
    op.create_index("ix_usage_ledger_api_key_id", "usage_ledger", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("usage_ledger")
    op.drop_table("api_keys")
    op.drop_table("users")
