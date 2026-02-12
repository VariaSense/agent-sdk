"""Tests for secret rotation automation helpers."""

from datetime import datetime, timezone, timedelta

from agent_sdk.secrets_rotation import find_due_policies, emit_rotation_due
from agent_sdk.server.multi_tenant import SecretRotationPolicy


class DummyAuditLogger:
    def __init__(self):
        self.entries = []

    def emit(self, entry):
        self.entries.append(entry)


class DummyWebhookDispatcher:
    def __init__(self):
        self.events = []

    def dispatch(self, event_type, payload):
        self.events.append((event_type, payload))


def test_find_due_policies():
    now = datetime(2026, 2, 12, tzinfo=timezone.utc)
    policies = [
        SecretRotationPolicy(
            secret_id="s1",
            org_id="default",
            rotation_days=7,
            last_rotated_at=(now - timedelta(days=10)).isoformat(),
        ),
        SecretRotationPolicy(
            secret_id="s2",
            org_id="default",
            rotation_days=30,
            last_rotated_at=(now - timedelta(days=5)).isoformat(),
        ),
    ]
    due = find_due_policies(policies, now=now)
    assert [p.secret_id for p in due] == ["s1"]


def test_emit_rotation_due_records_events():
    now = datetime(2026, 2, 12, tzinfo=timezone.utc)
    policy = SecretRotationPolicy(
        secret_id="s1",
        org_id="default",
        rotation_days=7,
        last_rotated_at=(now - timedelta(days=10)).isoformat(),
    )
    audit_logger = DummyAuditLogger()
    webhook_dispatcher = DummyWebhookDispatcher()
    count = emit_rotation_due([policy], audit_logger, webhook_dispatcher)
    assert count == 1
    assert audit_logger.entries[0].action == "secrets.rotation.due"
    assert webhook_dispatcher.events[0][0] == "secret.rotation_due"
