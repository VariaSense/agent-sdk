from dataclasses import dataclass, field
from typing import Any, Dict
import time, uuid

@dataclass
class ObsEvent:
    event_type: str
    agent: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: time.time())
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
