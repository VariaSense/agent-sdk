"""Add backup records table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_backup_records"
down_revision = "0004_governance_policy_bundles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backups",
        sa.Column("backup_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("storage_backend", sa.Text, nullable=False),
        sa.Column("storage_path", sa.Text, nullable=True),
        sa.Column("control_plane_backend", sa.Text, nullable=False),
        sa.Column("control_plane_path", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.PrimaryKeyConstraint("backup_id"),
    )


def downgrade() -> None:
    op.drop_table("backups")
