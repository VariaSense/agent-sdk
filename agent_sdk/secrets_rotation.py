"""Secret rotation automation helpers."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterable, List

from agent_sdk.observability.audit_logs import AuditLogEntry, AuditLogger
from agent_sdk.server.multi_tenant import SecretRotationPolicy
from agent_sdk.webhooks import WebhookDispatcher


def _parse_last_rotated(policy: SecretRotationPolicy) -> datetime | None:
    if not policy.last_rotated_at:
        return None
    try:
        return datetime.fromisoformat(policy.last_rotated_at)
    except ValueError:
        return None


def find_due_policies(
    policies: Iterable[SecretRotationPolicy],
    now: datetime | None = None,
) -> List[SecretRotationPolicy]:
    current = now or datetime.now(timezone.utc)
    due: List[SecretRotationPolicy] = []
    for policy in policies:
        last = _parse_last_rotated(policy)
        if last is None:
            continue
        age_days = (current - last).days
        if age_days >= policy.rotation_days:
            due.append(policy)
    return due


def emit_rotation_due(
    policies: Iterable[SecretRotationPolicy],
    audit_logger: AuditLogger,
    webhook_dispatcher: WebhookDispatcher,
) -> int:
    count = 0
    for policy in policies:
        payload = asdict(policy)
        audit_logger.emit(
            AuditLogEntry(
                action="secrets.rotation.due",
                actor="system",
                org_id=policy.org_id,
                target_type="secret_rotation",
                target_id=policy.secret_id,
                metadata=payload,
            )
        )
        webhook_dispatcher.dispatch("secret.rotation_due", payload)
        count += 1
    return count
