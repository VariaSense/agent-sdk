from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class PlanStep:
    id: int
    description: str
    tool: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

@dataclass
class Plan:
    task: str
    steps: List[PlanStep] = field(default_factory=list)
