from __future__ import annotations

import json
import os
from typing import List, Optional

from agent_sdk.registry.base import RegistryBackend
from agent_sdk.tool_packs.manifest import ToolManifest


class LocalRegistry(RegistryBackend):
    """Filesystem-backed registry for tool pack manifests."""

    def __init__(self, root: str = "tool_registry") -> None:
        self._root = root
        os.makedirs(self._root, exist_ok=True)

    def _manifest_path(self, name: str, version: str) -> str:
        return os.path.join(self._root, name, f"{version}.json")

    def publish(self, manifest: ToolManifest) -> ToolManifest:
        path = self._manifest_path(manifest.name, manifest.version)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(manifest.to_dict(), handle, indent=2)
        return manifest

    def list_manifests(self, name: Optional[str] = None) -> List[ToolManifest]:
        manifests: List[ToolManifest] = []
        if name:
            names = [name]
        else:
            names = [n for n in os.listdir(self._root) if os.path.isdir(os.path.join(self._root, n))]
        for pack_name in names:
            pack_dir = os.path.join(self._root, pack_name)
            if not os.path.isdir(pack_dir):
                continue
            for filename in os.listdir(pack_dir):
                if not filename.endswith(".json"):
                    continue
                with open(os.path.join(pack_dir, filename), "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                manifests.append(ToolManifest(**payload))
        return manifests

    def pull(self, name: str, version: Optional[str] = None) -> ToolManifest:
        if version:
            path = self._manifest_path(name, version)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Manifest {name}@{version} not found")
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return ToolManifest(**payload)
        # pick latest lexicographically
        pack_dir = os.path.join(self._root, name)
        if not os.path.isdir(pack_dir):
            raise FileNotFoundError(f"Manifest {name} not found")
        versions = sorted(
            [f[:-5] for f in os.listdir(pack_dir) if f.endswith(".json")],
        )
        if not versions:
            raise FileNotFoundError(f"Manifest {name} has no versions")
        return self.pull(name, versions[-1])
