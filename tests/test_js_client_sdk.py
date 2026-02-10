"""Tests for JS client SDK file presence."""

from pathlib import Path


def test_js_client_exists():
    path = Path("clients/js/index.js")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "AgentSDKClient" in content
    assert "checkCompatibility" in content
