"""Add projects table and project-scoped API keys."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_projects_and_project_keys"
down_revision = "0005_backup_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("project_id", sa.Text, nullable=False),
        sa.Column("org_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("tags_json", sa.JSON, nullable=True),
        sa.PrimaryKeyConstraint("project_id"),
    )
    op.add_column("api_keys", sa.Column("project_id", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "project_id")
    op.drop_table("projects")
