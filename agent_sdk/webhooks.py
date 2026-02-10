from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib import request as urlrequest

from agent_sdk.observability.audit_logs import AuditLogEntry, AuditLogExporter


@dataclass(frozen=True)
class WebhookSubscription:
    subscription_id: str
    org_id: str
    url: str
    event_types: List[str]
    secret: Optional[str] = None
    created_at: Optional[str] = None
    active: bool = True
    max_attempts: int = 3
    backoff_seconds: float = 1.0


@dataclass
class WebhookDelivery:
    subscription_id: str
    event_type: str
    payload: Dict[str, Any]
    attempts: int = 0
    error: Optional[str] = None


class WebhookDispatcher:
    def __init__(self, subscriptions: List[WebhookSubscription]):
        self._subscriptions = subscriptions
        self._dlq: List[WebhookDelivery] = []

    def update_subscriptions(self, subscriptions: List[WebhookSubscription]) -> None:
        self._subscriptions = subscriptions

    def list_dlq(self) -> List[WebhookDelivery]:
        return list(self._dlq)

    def dispatch(self, event_type: str, payload: Dict[str, Any]) -> None:
        for sub in self._subscriptions:
            if not sub.active:
                continue
            if sub.event_types and event_type not in sub.event_types:
                continue
            delivery = WebhookDelivery(subscription_id=sub.subscription_id, event_type=event_type, payload=payload)
            success = self._deliver_with_retry(sub, delivery)
            if not success:
                self._dlq.append(delivery)

    def _deliver_with_retry(self, sub: WebhookSubscription, delivery: WebhookDelivery) -> bool:
        attempts = max(1, sub.max_attempts)
        for attempt in range(attempts):
            delivery.attempts = attempt + 1
            try:
                self._send(sub, delivery)
                return True
            except Exception as exc:
                delivery.error = str(exc)
                if attempt < attempts - 1:
                    time.sleep(max(sub.backoff_seconds, 0))
        return False

    def _send(self, sub: WebhookSubscription, delivery: WebhookDelivery) -> None:
        body = json.dumps(
            {
                "event_type": delivery.event_type,
                "payload": delivery.payload,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json", "X-Webhook-Event": delivery.event_type}
        if sub.secret:
            signature = hmac.new(sub.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            headers["X-Webhook-Signature"] = signature
        req = urlrequest.Request(sub.url, data=body, headers=headers, method="POST")
        with urlrequest.urlopen(req, timeout=5):
            pass


class WebhookAuditExporter(AuditLogExporter):
    def __init__(self, dispatcher: WebhookDispatcher):
        self._dispatcher = dispatcher

    def emit(self, entry: AuditLogEntry) -> None:
        self._dispatcher.dispatch("audit.log", entry.to_dict())
