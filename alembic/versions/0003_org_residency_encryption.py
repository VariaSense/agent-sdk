"""Add org residency and encryption key fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_org_residency_encryption"
down_revision = "0002_user_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orgs", sa.Column("residency", sa.Text, nullable=True))
    op.add_column("orgs", sa.Column("encryption_key", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("orgs", "encryption_key")
    op.drop_column("orgs", "residency")
