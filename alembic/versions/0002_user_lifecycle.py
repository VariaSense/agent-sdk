"""Add user lifecycle fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_user_lifecycle"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("active", sa.Boolean, nullable=True))
    op.add_column("users", sa.Column("is_service_account", sa.Boolean, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "is_service_account")
    op.drop_column("users", "active")
