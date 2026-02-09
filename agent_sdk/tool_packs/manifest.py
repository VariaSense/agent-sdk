"""Tool pack manifest versioning and signing."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import hashlib
import hmac
import json
import os
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ToolManifest:
    name: str
    version: str
    tools: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _manifest_payload(manifest: ToolManifest) -> str:
    payload = {
        "name": manifest.name,
        "version": manifest.version,
        "tools": sorted(manifest.tools),
        "metadata": manifest.metadata,
    }
    return json.dumps(payload, sort_keys=True)


def sign_manifest(manifest: ToolManifest, secret: str) -> ToolManifest:
    payload = _manifest_payload(manifest)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return ToolManifest(
        name=manifest.name,
        version=manifest.version,
        tools=manifest.tools,
        metadata=manifest.metadata,
        signature=signature,
    )


def verify_manifest(manifest: ToolManifest, secret: str) -> bool:
    if not manifest.signature:
        return False
    expected = sign_manifest(
        ToolManifest(
            name=manifest.name,
            version=manifest.version,
            tools=manifest.tools,
            metadata=manifest.metadata,
        ),
        secret,
    ).signature
    return hmac.compare_digest(manifest.signature, expected or "")


def default_manifest_secret() -> Optional[str]:
    return os.getenv("AGENT_SDK_TOOL_MANIFEST_SECRET")
