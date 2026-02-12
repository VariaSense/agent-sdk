"""Add policy approvals and hierarchical quotas.

Revision ID: 0008_policy_approvals_and_quotas
Revises: 0007_webhooks_and_secrets_rotation
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_policy_approvals_and_quotas"
down_revision = "0007_webhooks_and_secrets_rotation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "policy_approvals",
        sa.Column("bundle_id", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("submitted_by", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("submitted_at", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("bundle_id", "version", "org_id"),
    )
    op.create_table(
        "project_quotas",
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=True),
        sa.Column("max_runs", sa.Integer(), nullable=True),
        sa.Column("max_sessions", sa.Integer(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("project_id"),
    )
    op.create_table(
        "api_key_quotas",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=True),
        sa.Column("max_runs", sa.Integer(), nullable=True),
        sa.Column("max_sessions", sa.Integer(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade():
    op.drop_table("api_key_quotas")
    op.drop_table("project_quotas")
    op.drop_table("policy_approvals")
