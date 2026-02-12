"""SDK versioning and compatibility utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    reason: str
    current: str
    target: str


def _parse_version(version: str) -> Tuple[int, int, int]:
    parts = (version or "0.0.0").strip().split(".")
    major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return major, minor, patch


def check_compatibility(current: str, target: str) -> CompatibilityResult:
    cur_major, cur_minor, _ = _parse_version(current)
    tgt_major, tgt_minor, _ = _parse_version(target)
    if tgt_major != cur_major:
        return CompatibilityResult(False, "major version mismatch", current, target)
    if tgt_minor < cur_minor:
        return CompatibilityResult(True, "downgrade within major", current, target)
    if tgt_minor - cur_minor > 1:
        return CompatibilityResult(True, "minor jump; review breaking changes", current, target)
    return CompatibilityResult(True, "compatible", current, target)
