from dataclasses import dataclass, field
from typing import Any, Dict
import uuid

@dataclass
class Message:
    id: str
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

def make_message(role: str, content: str, metadata=None) -> Message:
    return Message(
        id=str(uuid.uuid4()),
        role=role,
        content=content,
        metadata=metadata or {},
    )
