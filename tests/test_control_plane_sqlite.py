"""Tests for SQLite-backed control plane."""

import os
import tempfile

from agent_sdk.storage.control_plane import SQLiteControlPlane
from agent_sdk.server.multi_tenant import QuotaLimits, ModelPolicy, APIKeyRecord
from agent_sdk.server.multi_tenant import User


def test_sqlite_control_plane_persists_org_and_quota():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "control_plane.db")
        store = SQLiteControlPlane(path)
        store.ensure_org("org_a", "Org A")
        store.set_quota("org_a", QuotaLimits(max_runs=5, max_sessions=2, max_tokens=1000))
        store.set_model_policy("org_a", ModelPolicy(allowed_models=["gpt-4"], fallback_models=["gpt-3.5"]))

        store2 = SQLiteControlPlane(path)
        org = store2.get_org("org_a")
        assert org is not None
        quota = store2.get_quota("org_a")
        assert quota.max_runs == 5
        policy = store2.get_model_policy("org_a")
        assert policy is not None
        assert policy.allowed_models == ["gpt-4"]


def test_sqlite_control_plane_api_keys_and_users():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "control_plane.db")
        store = SQLiteControlPlane(path)
        store.ensure_org("org_b", "Org B")
        user = User(user_id="user_x", org_id="org_b", name="User X")
        store.create_user("org_b", user)
        record = APIKeyRecord(
            key_id="key_x",
            org_id="org_b",
            key="sk_test",
            label="test",
            role="admin",
            scopes=["*"],
        )
        store.create_api_key(record)

        users = store.list_users("org_b")
        assert len(users) == 1
        keys = store.list_api_keys("org_b")
        assert len(keys) == 1
