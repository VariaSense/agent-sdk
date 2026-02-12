"""Environment parity checks across deployment targets."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List


def _load_keys(path: Path) -> List[str]:
    keys = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.append(key)
    return keys


def check_env_parity(env_dir: str) -> Dict[str, List[str]]:
    root = Path(env_dir)
    files = sorted(root.glob("*.env.example"))
    if not files:
        return {}
    key_sets = {file.name: set(_load_keys(file)) for file in files}
    all_keys = set().union(*key_sets.values())
    missing: Dict[str, List[str]] = {}
    for name, keys in key_sets.items():
        missing_keys = sorted(all_keys - keys)
        if missing_keys:
            missing[name] = missing_keys
    return missing
