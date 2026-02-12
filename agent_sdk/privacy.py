"""Privacy export helpers for GDPR/CCPA requests."""

from __future__ import annotations

import json
import os
import zipfile
from dataclasses import asdict
from typing import Optional

from agent_sdk.storage.base import StorageBackend


class PrivacyExporter:
    def __init__(self, export_dir: str = "privacy_exports") -> None:
        self._export_dir = export_dir
        os.makedirs(self._export_dir, exist_ok=True)

    def export_org_bundle(
        self,
        storage: StorageBackend,
        org_id: str,
        user_id: Optional[str] = None,
        audit_log_path: Optional[str] = None,
    ) -> str:
        sessions = [s for s in storage.list_sessions(limit=10000) if s.org_id == org_id]
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        session_ids = {s.session_id for s in sessions}
        runs = [r for r in storage.list_runs(org_id=org_id, limit=100000) if r.session_id in session_ids]

        bundle_path = os.path.join(self._export_dir, f"privacy_{org_id}.zip")
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("sessions.json", json.dumps([asdict(s) for s in sessions], indent=2))
            archive.writestr("runs.json", json.dumps([asdict(r) for r in runs], indent=2))
            for run in runs:
                events = [e.to_dict() for e in storage.list_events(run.run_id, limit=10000)]
                archive.writestr(
                    f"events/{run.run_id}.json",
                    json.dumps(events, indent=2),
                )
            if audit_log_path and os.path.exists(audit_log_path):
                with open(audit_log_path, "r", encoding="utf-8") as handle:
                    archive.writestr("audit_logs.jsonl", handle.read())
        return bundle_path
