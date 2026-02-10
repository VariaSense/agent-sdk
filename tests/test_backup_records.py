"""Tests for backup record storage in control plane."""

import os
import tempfile
from datetime import datetime, timezone

from agent_sdk.storage.control_plane import SQLiteControlPlane
from agent_sdk.server.multi_tenant import BackupRecord


def test_backup_record_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "control_plane.db")
        store = SQLiteControlPlane(path)
        record = BackupRecord(
            backup_id="backup_test",
            created_at=datetime.now(timezone.utc).isoformat(),
            label="test",
            storage_backend="sqlite",
            storage_path="/tmp/storage.db",
            control_plane_backend="sqlite",
            control_plane_path=path,
            metadata={"note": "ok"},
        )
        store.create_backup_record(record)
        records = store.list_backup_records()
        assert len(records) == 1
        fetched = store.get_backup_record("backup_test")
        assert fetched is not None
        assert fetched.label == "test"
