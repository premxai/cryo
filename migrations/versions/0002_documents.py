"""documents full-text store

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(16), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.String(14), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("word_count", sa.BigInteger(), nullable=True),
        sa.Column("content_type", sa.String(24), nullable=True),
        sa.Column("source", sa.String(24), nullable=False, server_default="corpus"),
        sa.Column("links", JSONB(), nullable=True),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_documents_url", "documents", ["url"])


def downgrade() -> None:
    op.drop_table("documents")
