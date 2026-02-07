"""Tests for tool allowlist enforcement."""

import os
import tempfile

from agent_sdk.tool_packs import builtin


def test_filesystem_allowlist_enforced():
    with tempfile.TemporaryDirectory() as tmpdir:
        allowed_file = os.path.join(tmpdir, "allowed.txt")
        os.environ["AGENT_SDK_FS_ALLOWLIST"] = tmpdir
        builtin._filesystem_write({"path": allowed_file, "content": "ok"})
        assert builtin._filesystem_read({"path": allowed_file}) == "ok"

        os.environ["AGENT_SDK_FS_ALLOWLIST"] = "/tmp/does-not-exist"
        try:
            builtin._filesystem_read({"path": allowed_file})
            assert False, "expected allowlist rejection"
        except ValueError as exc:
            assert "AGENT_SDK_FS_ALLOWLIST" in str(exc)


def test_http_allowlist_check():
    os.environ["AGENT_SDK_HTTP_ALLOWLIST"] = "example.com"
    assert builtin._is_url_allowed("https://example.com")
    assert builtin._is_url_allowed("https://api.example.com/path")
    assert not builtin._is_url_allowed("https://example.org")
