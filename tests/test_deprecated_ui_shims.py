import warnings


def test_admin_ui_shim_warns():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from agent_sdk.server.admin_ui import ADMIN_HTML  # noqa: F401
    assert any(item.category is DeprecationWarning for item in caught)


def test_dashboard_shim_warns():
    class DummyBus:
        def emit(self, event):
            return None

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from agent_sdk.dashboard.server import DashboardServer

        DashboardServer(DummyBus())
    assert any(item.category is DeprecationWarning for item in caught)
