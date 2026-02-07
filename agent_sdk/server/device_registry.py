"""Device registration and pairing flow for gateway mode."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional
import secrets


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DeviceRecord:
    device_id: str
    name: str
    pairing_code: str
    created_at: str = field(default_factory=_now_iso)
    paired: bool = False
    agent_id: Optional[str] = None


class DeviceRegistry:
    def __init__(self):
        self._devices: Dict[str, DeviceRecord] = {}

    def register_device(self, name: str) -> DeviceRecord:
        device_id = f"dev_{secrets.token_hex(8)}"
        pairing_code = secrets.token_hex(3)
        record = DeviceRecord(device_id=device_id, name=name, pairing_code=pairing_code)
        self._devices[device_id] = record
        return record

    def pair_device(self, device_id: str, pairing_code: str, agent_id: str) -> bool:
        record = self._devices.get(device_id)
        if record is None:
            return False
        if record.pairing_code != pairing_code:
            return False
        record.paired = True
        record.agent_id = agent_id
        return True

    def get_device(self, device_id: str) -> Optional[DeviceRecord]:
        return self._devices.get(device_id)

    def list_devices(self) -> Dict[str, DeviceRecord]:
        return dict(self._devices)
