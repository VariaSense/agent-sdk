import warnings

from agent_sdk.billing import generate_chargeback_report
from agent_sdk.observability.stream_envelope import RunMetadata, RunStatus
from agent_sdk.privacy import PrivacyExporter
from agent_sdk.server.multi_tenant import MultiTenantStore
from agent_sdk.storage.control_plane import SQLiteControlPlane
from agent_sdk.webhooks import WebhookDispatcher


def test_billing_shim_warns():
    runs = [
        RunMetadata(
            run_id="run_1",
            session_id="sess_1",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.COMPLETED,
            metadata={},
        )
    ]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        generate_chargeback_report(runs)
    assert any(item.category is DeprecationWarning for item in caught)


def test_privacy_shim_warns():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        PrivacyExporter()
    assert any(item.category is DeprecationWarning for item in caught)


def test_webhooks_shim_warns():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        WebhookDispatcher([])
    assert any(item.category is DeprecationWarning for item in caught)


def test_tenant_store_shim_warns():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        MultiTenantStore()
    assert any(item.category is DeprecationWarning for item in caught)


def test_control_plane_shim_warns(tmp_path):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        SQLiteControlPlane(str(tmp_path / "cp.db"))
    assert any(item.category is DeprecationWarning for item in caught)
