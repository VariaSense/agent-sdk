from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from agent_sdk.tool_packs.manifest import ToolManifest


class RegistryBackend(ABC):
    @abstractmethod
    def publish(self, manifest: ToolManifest) -> ToolManifest:
        raise NotImplementedError

    @abstractmethod
    def list_manifests(self, name: Optional[str] = None) -> List[ToolManifest]:
        raise NotImplementedError

    @abstractmethod
    def pull(self, name: str, version: Optional[str] = None) -> ToolManifest:
        raise NotImplementedError
