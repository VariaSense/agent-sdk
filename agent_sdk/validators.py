"""Input validation schemas using Pydantic"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from agent_sdk.exceptions import ValidationError


class RunTaskRequest(BaseModel):
    """Validate task execution request"""

    task: str = Field(
        ..., min_length=1, max_length=10000, description="Task description"
    )
    config: Optional[str] = Field(None, description="Path to config file")
    timeout: Optional[int] = Field(
        default=300, ge=1, le=3600, description="Timeout in seconds"
    )

    @validator("task")
    def task_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Task cannot be empty")
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "task": "Write a summary of the weather",
                "config": "config.yaml",
                "timeout": 300,
            }
        }


class ToolCallRequest(BaseModel):
    """Validate tool call request"""

    tool_name: str = Field(..., regex=r"^[a-z_][a-z0-9_]*$", description="Tool name")
    inputs: Dict[str, Any] = Field(
        default_factory=dict, description="Tool inputs"
    )

    @validator("inputs")
    def inputs_not_too_large(cls, v):
        if len(str(v)) > 100000:  # 100KB limit
            raise ValueError("Inputs exceed 100KB limit")
        return v

    class Config:
        schema_extra = {
            "example": {
                "tool_name": "search_web",
                "inputs": {"query": "python asyncio"},
            }
        }


class ModelConfigDict(BaseModel):
    """Validate model configuration"""

    name: str = Field(..., description="Model name")
    provider: str = Field(..., regex=r"^[a-z0-9_]+$", description="LLM provider")
    model_id: str = Field(..., description="Model ID from provider")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=128000)

    class Config:
        schema_extra = {
            "example": {
                "name": "gpt-4",
                "provider": "openai",
                "model_id": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2048,
            }
        }


class AgentConfigDict(BaseModel):
    """Validate agent configuration"""

    model: str = Field(..., description="Model to use (references models dict)")

    class Config:
        schema_extra = {"example": {"model": "gpt-4"}}


class ConfigSchema(BaseModel):
    """Validate complete SDK configuration"""

    models: Dict[str, ModelConfigDict] = Field(
        ..., description="Available models"
    )
    agents: Dict[str, AgentConfigDict] = Field(
        ..., description="Agent configurations"
    )
    rate_limits: List[Dict[str, Any]] = Field(
        default_factory=list, description="Rate limiting rules"
    )

    @validator("agents")
    def agents_reference_models(cls, v, values):
        if "models" in values:
            models = values["models"]
            for agent_name, agent_config in v.items():
                if agent_config.model not in models:
                    raise ValueError(
                        f"Agent '{agent_name}' references undefined model '{agent_config.model}'"
                    )
        return v

    class Config:
        schema_extra = {
            "example": {
                "models": {
                    "gpt4": {
                        "name": "gpt-4",
                        "provider": "openai",
                        "model_id": "gpt-4",
                    }
                },
                "agents": {"planner": {"model": "gpt4"}},
                "rate_limits": [],
            }
        }


class ListToolsResponse(BaseModel):
    """Response for listing tools"""

    tools: List[Dict[str, Any]]
    count: int


class TaskResponse(BaseModel):
    """Response from task execution"""

    status: str = Field(..., regex=r"^(success|error|pending)$")
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = 0


class HealthResponse(BaseModel):
    """Response from health check endpoint"""

    status: str
    version: str


class ReadyResponse(BaseModel):
    """Response from readiness check endpoint"""

    ready: bool
    error: Optional[str] = None
