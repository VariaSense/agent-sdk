"""Python client SDK for Agent SDK API."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, Optional


class AgentSDKClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        org_id: str = "default",
        request_func=None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.org_id = org_id
        self._request = request_func or self._default_request

    def _default_request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-API-Key", self.api_key)
        req.add_header("X-Org-Id", self.org_id)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def run_task(self, task: str) -> Dict[str, Any]:
        return self._request("POST", "/run", {"task": task})

    def list_orgs(self) -> Dict[str, Any]:
        return self._request("GET", "/admin/orgs")
