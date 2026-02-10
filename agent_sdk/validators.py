"""Input validation schemas using Pydantic"""

from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict
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
    tags: Optional[Dict[str, str]] = Field(default=None, description="Cost allocation tags")

    @field_validator("task")
    def task_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Task cannot be empty")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task": "Write a summary of the weather",
                "config": "config.yaml",
                "timeout": 300,
                "tags": {"project": "alpha", "environment": "staging"},
            }
        }
    )


class ToolCallRequest(BaseModel):
    """Validate tool call request"""

    tool_name: str = Field(..., pattern=r"^[a-z_][a-z0-9_]*$", description="Tool name")
    inputs: Dict[str, Any] = Field(
        default_factory=dict, description="Tool inputs"
    )

    @field_validator("inputs")
    def inputs_not_too_large(cls, v):
        if len(str(v)) > 100000:  # 100KB limit
            raise ValueError("Inputs exceed 100KB limit")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tool_name": "search_web",
                "inputs": {"query": "python asyncio"},
            }
        }
    )


class ModelConfigDict(BaseModel):
    """Validate model configuration"""

    name: str = Field(..., description="Model name")
    provider: str = Field(..., pattern=r"^[a-z0-9_]+$", description="LLM provider")
    model_id: str = Field(..., description="Model ID from provider")
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=128000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "gpt-4",
                "provider": "openai",
                "model_id": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2048,
            }
        }
    )


class AgentConfigDict(BaseModel):
    """Validate agent configuration"""

    model: str = Field(..., description="Model to use (references models dict)")

    model_config = ConfigDict(json_schema_extra={"example": {"model": "gpt-4"}})


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

    @field_validator("agents")
    def agents_reference_models(cls, v, info):
        models = info.data.get("models")
        if models:
            for agent_name, agent_config in v.items():
                if agent_config.model not in models:
                    raise ValueError(
                        f"Agent '{agent_name}' references undefined model '{agent_config.model}'"
                    )
        return v

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class ListToolsResponse(BaseModel):
    """Response for listing tools"""

    tools: List[Dict[str, Any]]
    count: int


class TaskResponse(BaseModel):
    """Response from task execution"""

    status: str = Field(..., pattern=r"^(success|error|pending)$")
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


class ChannelMessageRequest(BaseModel):
    """Inbound channel message payload."""

    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = None
    channel: str = Field(default="web", min_length=1, max_length=50)
    user_id: Optional[str] = None


class APIKeyCreateRequest(BaseModel):
    """Create a new API key for an org."""

    org_id: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=100)
    role: str = Field(default="developer", min_length=1, max_length=50)
    scopes: List[str] = Field(default_factory=list)
    expires_at: Optional[str] = None
    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1)
    ip_allowlist: List[str] = Field(default_factory=list)


class DeviceRegisterRequest(BaseModel):
    """Register a device for pairing."""

    name: str = Field(..., min_length=1, max_length=100)


class DevicePairRequest(BaseModel):
    """Pair a device with an agent."""

    device_id: str = Field(..., min_length=1, max_length=200)
    pairing_code: str = Field(..., min_length=1, max_length=50)
    agent_id: str = Field(..., min_length=1, max_length=200)


class ReplayEventsResponse(BaseModel):
    """Response for event replay endpoints."""

    events: List[Dict[str, Any]]
    count: int


class RunEventsDeleteRequest(BaseModel):
    """Request to delete run events."""

    before_seq: Optional[int] = Field(default=None, ge=0)


class ModelPolicyRequest(BaseModel):
    """Request to set tenant model policy."""

    org_id: str = Field(..., min_length=1, max_length=100)
    allowed_models: List[str] = Field(default_factory=list)
    fallback_models: List[str] = Field(default_factory=list)


class PolicyBundleCreateRequest(BaseModel):
    """Request to create a governance policy bundle."""

    bundle_id: str = Field(..., min_length=1, max_length=100)
    content: Dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = Field(default=None, max_length=200)
    version: Optional[int] = Field(default=None, ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bundle_id": "enterprise-default",
                "content": {
                    "tools": {"allow": ["filesystem.read"], "deny": ["filesystem.write"]},
                    "egress": {"allow_domains": ["example.com"]},
                    "models": {"allow": ["gpt-4"]},
                },
                "description": "Default governance policy bundle",
            }
        }
    )


class PolicyBundleAssignRequest(BaseModel):
    """Request to assign a policy bundle to a tenant."""

    org_id: str = Field(..., min_length=1, max_length=100)
    bundle_id: str = Field(..., min_length=1, max_length=100)
    version: int = Field(..., ge=1)
    overrides: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "org_id": "default",
                "bundle_id": "enterprise-default",
                "version": 1,
                "overrides": {"tools": {"allow": ["filesystem.read", "http.fetch"]}},
            }
        }
    )


class QuotaUpdateRequest(BaseModel):
    """Request to update quota limits."""

    org_id: str = Field(..., min_length=1, max_length=100)
    max_runs: Optional[int] = Field(default=None, ge=0)
    max_sessions: Optional[int] = Field(default=None, ge=0)
    max_tokens: Optional[int] = Field(default=None, ge=0)


class RetentionPolicyRequest(BaseModel):
    """Request to update retention policy."""

    org_id: str = Field(..., min_length=1, max_length=100)
    max_events: Optional[int] = Field(default=None, ge=1)
    max_run_age_days: Optional[int] = Field(default=None, ge=1)
    max_session_age_days: Optional[int] = Field(default=None, ge=1)


class ScheduleCreateRequest(BaseModel):
    """Request to create a scheduled run."""

    org_id: str = Field(..., min_length=1, max_length=100)
    task: str = Field(..., min_length=1, max_length=10000)
    cron: str = Field(..., min_length=1, max_length=100)
    enabled: bool = Field(default=True)


class UserCreateRequest(BaseModel):
    """Request to create a user."""

    org_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)


class ServiceAccountCreateRequest(BaseModel):
    """Request to create a service account."""

    org_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)


class AuthValidateRequest(BaseModel):
    """Request to validate an identity token."""

    token: str = Field(..., min_length=1, max_length=10000)


class ResidencyRequest(BaseModel):
    """Request to update org data residency."""

    org_id: str = Field(..., min_length=1, max_length=100)
    region: Optional[str] = Field(default=None, max_length=50)


class EncryptionKeyRequest(BaseModel):
    """Request to update org encryption key."""

    org_id: str = Field(..., min_length=1, max_length=100)
    key: Optional[str] = Field(default=None, max_length=500)


class PromptPolicyCreateRequest(BaseModel):
    """Request to create a prompt/policy version."""

    policy_id: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=20000)
    description: Optional[str] = Field(default=None, max_length=200)
