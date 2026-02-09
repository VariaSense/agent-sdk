"""Prompt/policy version registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PromptPolicyVersion:
    policy_id: str
    version: int
    content: str
    description: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)


class PromptPolicyRegistry:
    def __init__(self) -> None:
        self._policies: Dict[str, List[PromptPolicyVersion]] = {}

    def create_version(self, policy_id: str, content: str, description: Optional[str] = None) -> PromptPolicyVersion:
        versions = self._policies.setdefault(policy_id, [])
        version_num = len(versions) + 1
        version = PromptPolicyVersion(
            policy_id=policy_id,
            version=version_num,
            content=content,
            description=description,
        )
        versions.append(version)
        return version

    def list_policies(self) -> List[str]:
        return sorted(self._policies.keys())

    def list_versions(self, policy_id: str) -> List[PromptPolicyVersion]:
        return list(self._policies.get(policy_id, []))

    def latest(self, policy_id: str) -> Optional[PromptPolicyVersion]:
        versions = self._policies.get(policy_id)
        if not versions:
            return None
        return versions[-1]
