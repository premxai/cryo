"""user name + auth_user_id (external auth: Clerk)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("auth_user_id", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_users_auth_user_id", "users", ["auth_user_id"])
    op.create_index("ix_users_auth_user_id", "users", ["auth_user_id"])


def downgrade() -> None:
    op.drop_index("ix_users_auth_user_id", table_name="users")
    op.drop_constraint("uq_users_auth_user_id", "users", type_="unique")
    op.drop_column("users", "auth_user_id")
    op.drop_column("users", "name")
