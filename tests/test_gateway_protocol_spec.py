"""Tests for gateway protocol spec documentation."""

from pathlib import Path


def test_gateway_protocol_spec_exists():
    spec_path = Path(__file__).resolve().parents[1] / "documents" / "PHASE3_GATEWAY_PROTOCOL_SPEC.md"
    assert spec_path.exists()
    content = spec_path.read_text(encoding="utf-8").strip()
    assert len(content) > 0
    assert "Gateway Mode Protocol Spec" in content
