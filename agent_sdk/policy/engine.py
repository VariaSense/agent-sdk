from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from agent_sdk.policy.types import PolicyBundle, PolicyAssignment


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class PolicyEngine:
    """Default in-process policy engine with mockable storage."""

    def __init__(self, store):
        self._store = store

    def get_effective_policy(self, org_id: str) -> Dict[str, Any]:
        assignment: Optional[PolicyAssignment] = self._store.get_policy_assignment(org_id)
        if not assignment:
            return {}
        bundle: Optional[PolicyBundle] = self._store.get_policy_bundle(
            assignment.bundle_id, assignment.version
        )
        if not bundle:
            return assignment.overrides or {}
        if assignment.overrides:
            return _deep_merge(bundle.content, assignment.overrides)
        return bundle.content

    def evaluate_tool(self, org_id: str, tool_name: str, inputs: Optional[Dict[str, Any]] = None) -> PolicyDecision:
        policy = self.get_effective_policy(org_id)
        tools = policy.get("tools", {})
        deny = set(tools.get("deny", []) or [])
        allow = set(tools.get("allow", []) or [])
        if tool_name in deny:
            return PolicyDecision(False, f"tool '{tool_name}' is denied by policy")
        if allow and tool_name not in allow:
            return PolicyDecision(False, f"tool '{tool_name}' is not in allowlist")
        return PolicyDecision(True, "")

    def evaluate_egress(self, org_id: str, url: str) -> PolicyDecision:
        policy = self.get_effective_policy(org_id)
        egress = policy.get("egress", {})
        deny = egress.get("deny_domains", []) or []
        allow = egress.get("allow_domains", []) or []
        host = urlparse(url).hostname or ""
        if self._matches_domains(host, deny):
            return PolicyDecision(False, f"egress to '{host}' denied by policy")
        if allow and not self._matches_domains(host, allow):
            return PolicyDecision(False, f"egress to '{host}' not in allowlist")
        return PolicyDecision(True, "")

    def evaluate_model(self, org_id: str, model_id: Optional[str]) -> PolicyDecision:
        if not model_id:
            return PolicyDecision(True, "")
        policy = self.get_effective_policy(org_id)
        models = policy.get("models", {})
        deny = set(models.get("deny", []) or [])
        allow = set(models.get("allow", []) or [])
        if model_id in deny:
            return PolicyDecision(False, f"model '{model_id}' denied by policy")
        if allow and model_id not in allow:
            return PolicyDecision(False, f"model '{model_id}' not in allowlist")
        return PolicyDecision(True, "")

    def evaluate_cost(self, org_id: str, *, cost: Optional[float] = None, tokens: Optional[int] = None) -> PolicyDecision:
        policy = self.get_effective_policy(org_id)
        cost_policy = policy.get("cost", {})
        max_cost = cost_policy.get("max_cost_per_run")
        max_tokens = cost_policy.get("max_tokens_per_run")
        if cost is not None and max_cost is not None and cost > max_cost:
            return PolicyDecision(False, f"cost {cost} exceeds max {max_cost}")
        if tokens is not None and max_tokens is not None and tokens > max_tokens:
            return PolicyDecision(False, f"tokens {tokens} exceeds max {max_tokens}")
        return PolicyDecision(True, "")

    def evaluate_data_access(
        self,
        org_id: str,
        classification: str,
        action: str,
    ) -> PolicyDecision:
        policy = self.get_effective_policy(org_id)
        data_access = policy.get("data_access", {})
        deny_classes = set(data_access.get("deny_classifications", []) or [])
        allow_classes = set(data_access.get("allow_classifications", []) or [])
        deny_actions = set(data_access.get("deny_actions", []) or [])
        allow_actions = set(data_access.get("allow_actions", []) or [])
        if classification in deny_classes:
            return PolicyDecision(False, f"classification '{classification}' denied by policy")
        if allow_classes and classification not in allow_classes:
            return PolicyDecision(False, f"classification '{classification}' not in allowlist")
        if action in deny_actions:
            return PolicyDecision(False, f"action '{action}' denied by policy")
        if allow_actions and action not in allow_actions:
            return PolicyDecision(False, f"action '{action}' not in allowlist")
        return PolicyDecision(True, "")

    @staticmethod
    def _matches_domains(host: str, domains: list[str]) -> bool:
        if not host:
            return False
        for domain in domains:
            if host == domain:
                return True
            if host.endswith("." + domain):
                return True
        return False


def safety_preset(name: str) -> Dict[str, Any]:
    presets = {
        "strict": {
            "tools": {"deny": ["filesystem.write", "shell.exec"]},
            "egress": {"allow_domains": []},
            "models": {"allow": []},
            "data_access": {"allow_classifications": ["public"], "allow_actions": ["read"]},
        },
        "balanced": {
            "tools": {"deny": ["filesystem.write"]},
            "egress": {"allow_domains": ["api.openai.com"]},
            "models": {"allow": []},
            "data_access": {"allow_classifications": ["public", "internal"], "allow_actions": ["read"]},
        },
        "permissive": {
            "tools": {"allow": [], "deny": []},
            "egress": {"allow_domains": []},
            "models": {"allow": []},
            "data_access": {"allow_classifications": ["public", "internal", "restricted"], "allow_actions": ["read", "write"]},
        },
    }
    if name not in presets:
        raise ValueError("Unknown safety preset")
    return presets[name]


def validate_policy_content(content: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    tools = content.get("tools", {})
    if not isinstance(tools, dict):
        errors.append("tools must be an object")
    egress = content.get("egress", {})
    if not isinstance(egress, dict):
        errors.append("egress must be an object")
    models = content.get("models", {})
    if not isinstance(models, dict):
        errors.append("models must be an object")
    data_access = content.get("data_access", {})
    if data_access and not isinstance(data_access, dict):
        errors.append("data_access must be an object")
    return errors
