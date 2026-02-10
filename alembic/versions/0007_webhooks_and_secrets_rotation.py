"""Add webhook subscriptions and secret rotation policies."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0007_webhooks_and_secrets_rotation"
down_revision = "0006_projects_and_project_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("subscription_id", sa.Text, nullable=False),
        sa.Column("org_id", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("event_types_json", sa.JSON, nullable=True),
        sa.Column("secret", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, nullable=True),
        sa.Column("max_attempts", sa.Integer, nullable=True),
        sa.Column("backoff_seconds", sa.Float, nullable=True),
        sa.PrimaryKeyConstraint("subscription_id"),
    )
    op.create_table(
        "secret_rotation_policies",
        sa.Column("secret_id", sa.Text, nullable=False),
        sa.Column("org_id", sa.Text, nullable=True),
        sa.Column("rotation_days", sa.Integer, nullable=False),
        sa.Column("last_rotated_at", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("secret_id"),
    )


def downgrade() -> None:
    op.drop_table("secret_rotation_policies")
    op.drop_table("webhook_subscriptions")
