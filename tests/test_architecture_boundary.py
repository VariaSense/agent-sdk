from pathlib import Path


def test_sdk_never_imports_agent_platform():
    root = Path(__file__).resolve().parents[1] / "agent_sdk"
    allowed = {
        "billing.py",
        "privacy.py",
        "webhooks.py",
        "_deprecation.py",
        "server/admin_ui.py",
        "server/app.py",
        "server/multi_tenant.py",
        "storage/control_plane.py",
        "dashboard/server.py",
    }
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root).as_posix()
        if "agent_platform" in text and rel not in allowed:
            offenders.append(path.relative_to(root).as_posix())
    assert offenders == []
