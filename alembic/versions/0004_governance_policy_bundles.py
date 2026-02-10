"""Add governance policy bundle tables and assignments."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_governance_policy_bundles"
down_revision = "0003_org_residency_encryption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "policy_bundles",
        sa.Column("bundle_id", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("content_json", sa.JSON, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("bundle_id", "version"),
    )
    op.add_column("orgs", sa.Column("policy_bundle_id", sa.Text, nullable=True))
    op.add_column("orgs", sa.Column("policy_bundle_version", sa.Integer, nullable=True))
    op.add_column("orgs", sa.Column("policy_overrides_json", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("orgs", "policy_overrides_json")
    op.drop_column("orgs", "policy_bundle_version")
    op.drop_column("orgs", "policy_bundle_id")
    op.drop_table("policy_bundles")
