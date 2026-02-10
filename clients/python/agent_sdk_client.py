"""Python client SDK for Agent SDK API."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, Optional


CLIENT_SDK_VERSION = "0.1.0"


class AgentSDKClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        org_id: str = "default",
        client_version: str = CLIENT_SDK_VERSION,
        request_func=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.org_id = org_id
        self.client_version = client_version
        self._request = request_func or self._default_request

    def _default_request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-API-Key", self.api_key)
        req.add_header("X-Org-Id", self.org_id)
        req.add_header("X-Client-Version", self.client_version)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def run_task(self, task: str) -> Dict[str, Any]:
        return self._request("POST", "/run", {"task": task})

    def list_orgs(self) -> Dict[str, Any]:
        return self._request("GET", "/admin/orgs")

    def get_server_version(self) -> Optional[str]:
        response = self._request("GET", "/v1/health")
        return response.get("version")

    def check_compatibility(self) -> Dict[str, Any]:
        server_version = self.get_server_version()
        compatible = False
        if server_version:
            compatible = _major_version(server_version) == _major_version(self.client_version)
        return {
            "client_version": self.client_version,
            "server_version": server_version,
            "compatible": compatible,
        }


def _major_version(version: str) -> int:
    try:
        return int(version.split(".")[0])
    except Exception:
        return -1
