"""Shared deprecation helpers for legacy SDK surfaces."""

from __future__ import annotations

import warnings


def warn_platform_ownership(old_path: str, new_path: str) -> None:
    warnings.warn(
        f"{old_path} is deprecated and retained only as a compatibility shim. "
        f"Use {new_path} for platform-owned behavior.",
        DeprecationWarning,
        stacklevel=2,
    )
