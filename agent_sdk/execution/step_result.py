from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class StepResult:
    step_id: int
    success: bool
    output: Any
    error: Optional[str] = None
