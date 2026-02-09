"""Tests for PII redaction pipeline."""

import os
import tempfile

from agent_sdk.observability.audit_logs import AuditLogEntry, create_audit_loggers
from agent_sdk.observability.redaction import RedactionPolicy, Redactor
from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    RunStatus,
    SessionMetadata,
    StreamChannel,
    StreamEnvelope,
)
from agent_sdk.server.run_store import RunEventStore
from agent_sdk.storage.sqlite import SQLiteStorage


def test_redaction_applies_to_persisted_events():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "redaction.db")
        storage = SQLiteStorage(db_path)
        storage.create_session(SessionMetadata(session_id="sess_redact"))
        storage.create_run(
            RunMetadata(
                run_id="run_redact",
                session_id="sess_redact",
                agent_id="agent",
                status=RunStatus.RUNNING,
            )
        )

        policy = RedactionPolicy(enabled=True)
        redactor = Redactor(policy)
        run_store = RunEventStore(storage=storage, redactor=redactor)

        run_store.append_event(
            "run_redact",
            StreamEnvelope(
                run_id="run_redact",
                session_id="sess_redact",
                stream=StreamChannel.ASSISTANT,
                event="message",
                payload={
                    "text": "Contact me at test@example.com or 415-555-1234",
                    "ssn": "123-45-6789",
                },
                seq=1,
                status=RunStatus.RUNNING.value,
                metadata={"note": "email test@example.com"},
            ),
        )

        events = storage.list_events("run_redact")
        assert events
        payload = events[0].payload
        assert "test@example.com" not in payload["text"]
        assert "[REDACTED]" in payload["text"]
        assert payload["ssn"] == "[REDACTED]"
        assert events[0].metadata["note"] == "email [REDACTED]"


def test_audit_log_redaction():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "audit.jsonl")
        policy = RedactionPolicy(enabled=True)
        redactor = Redactor(policy)
        logger = create_audit_loggers(path=path, redactor=redactor)
        logger.emit(
            AuditLogEntry(
                action="api_key.created",
                actor="tester",
                org_id="default",
                target_type="api_key",
                metadata={"email": "audit@example.com"},
            )
        )
        lines = open(path, "r", encoding="utf-8").read().splitlines()
        assert lines
        assert "audit@example.com" not in lines[0]
        assert "[REDACTED]" in lines[0]
