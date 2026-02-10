"""Initial schema for storage and control plane."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

try:
    from sqlalchemy.dialects import postgresql
except ImportError:  # pragma: no cover
    postgresql = None

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql" and postgresql is not None:
        return postgresql.JSONB
    return sa.JSON


def upgrade() -> None:
    json_type = _json_type()

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text),
        sa.Column("user_id", sa.Text),
        sa.Column("created_at", sa.Text),
        sa.Column("updated_at", sa.Text),
        sa.Column("tags_json", json_type),
        sa.Column("metadata_json", json_type),
    )

    op.create_table(
        "runs",
        sa.Column("run_id", sa.Text, primary_key=True),
        sa.Column("session_id", sa.Text),
        sa.Column("agent_id", sa.Text),
        sa.Column("org_id", sa.Text),
        sa.Column("status", sa.Text),
        sa.Column("model", sa.Text),
        sa.Column("created_at", sa.Text),
        sa.Column("started_at", sa.Text),
        sa.Column("ended_at", sa.Text),
        sa.Column("tags_json", json_type),
        sa.Column("metadata_json", json_type),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Text),
        sa.Column("session_id", sa.Text),
        sa.Column("org_id", sa.Text),
        sa.Column("stream", sa.Text),
        sa.Column("event", sa.Text),
        sa.Column("payload_json", json_type),
        sa.Column("timestamp", sa.Text),
        sa.Column("seq", sa.Integer),
        sa.Column("status", sa.Text),
        sa.Column("metadata_json", json_type),
    )

    op.create_table(
        "orgs",
        sa.Column("org_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text),
        sa.Column("created_at", sa.Text),
        sa.Column("quotas_json", json_type),
        sa.Column("model_policy_json", json_type),
        sa.Column("retention_json", json_type),
    )

    op.create_table(
        "users",
        sa.Column("user_id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text),
        sa.Column("name", sa.Text),
        sa.Column("created_at", sa.Text),
    )

    op.create_table(
        "api_keys",
        sa.Column("key_id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text),
        sa.Column("key", sa.Text),
        sa.Column("label", sa.Text),
        sa.Column("role", sa.Text),
        sa.Column("scopes_json", json_type),
        sa.Column("created_at", sa.Text),
        sa.Column("active", sa.Boolean),
        sa.Column("expires_at", sa.Text),
        sa.Column("rotated_at", sa.Text),
        sa.Column("rate_limit_per_minute", sa.Integer),
        sa.Column("ip_allowlist_json", json_type),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("orgs")
    op.drop_table("events")
    op.drop_table("runs")
    op.drop_table("sessions")
