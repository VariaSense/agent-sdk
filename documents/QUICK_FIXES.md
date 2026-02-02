# Quick Reference: Top 10 Production Improvements

## 1. Add Custom Exception Types
**File**: `agent_sdk/exceptions.py` (NEW)

```python
class AgentSDKException(Exception):
    """Base exception for all Agent SDK errors"""
    pass

class ConfigError(AgentSDKException):
    """Configuration is invalid or missing"""
    pass

class RateLimitError(AgentSDKException):
    """Rate limit exceeded"""
    pass

class ToolError(AgentSDKException):
    """Tool execution failed"""
    pass

class LLMError(AgentSDKException):
    """LLM API call failed"""
    pass

class ValidationError(AgentSDKException):
    """Input validation failed"""
    pass
```

**Impact**: Better error identification, proper exception handling, easier debugging

---

## 2. Add Structured Logging
**File**: `agent_sdk/logging_config.py` (NEW)

```python
import logging
import json
from typing import Any, Dict

def setup_logging(level: str = "INFO"):
    """Configure structured logging"""
    logger = logging.getLogger("agent_sdk")
    logger.setLevel(getattr(logging, level))
    
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def log_with_context(logger: logging.Logger, level: str, 
                     msg: str, context: Dict[str, Any]):
    """Log message with context"""
    log_entry = {
        "message": msg,
        "level": level,
        **context
    }
    getattr(logger, level.lower())(json.dumps(log_entry))
```

**Impact**: Track requests end-to-end, better debugging, production observability

---

## 3. Input Validation with Pydantic
**File**: `agent_sdk/validators.py` (NEW)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any

class RunTaskRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=10000)
    config: Optional[str] = None
    timeout: Optional[int] = Field(default=300, ge=1, le=3600)
    
    @validator('task')
    def task_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Task cannot be empty')
        return v.strip()

class ToolInputRequest(BaseModel):
    tool_name: str = Field(..., pattern=r'^[a-z_]+$')
    inputs: Dict[str, Any]
    
    @validator('tool_name')
    def valid_tool_name(cls, v):
        if not v.replace('_', '').isalnum():
            raise ValueError('Invalid tool name')
        return v
```

**Impact**: Prevent invalid inputs, better error messages, type safety

---

## 4. API Authentication
**File**: `agent_sdk/security.py` (NEW)

```python
from fastapi import HTTPException, Depends, Header
from typing import Optional
import os

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key from header"""
    expected_key = os.getenv("API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="API key not configured")
    
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return x_api_key

# Usage in FastAPI:
# @app.post("/run", dependencies=[Depends(verify_api_key)])
# async def run_task(req: RunTaskRequest):
#     ...
```

**Impact**: Prevent unauthorized access, secure production deployments

---

## 5. Environment Configuration
**File**: `.env.example` (NEW)

```
# Agent SDK Configuration
AGENT_SDK_ENV=production
AGENT_SDK_LOG_LEVEL=INFO
AGENT_SDK_CONFIG_PATH=config.yaml

# API Configuration
API_KEY=your-secret-key-here
API_HOST=0.0.0.0
API_PORT=9000

# LLM Configuration
OPENAI_API_KEY=sk-...
LLM_PROVIDER=openai
LLM_MODEL=gpt-4

# Rate Limiting
RATE_LIMIT_CALLS=100
RATE_LIMIT_TOKENS=10000
RATE_LIMIT_WINDOW=60

# Database (for persistence)
DATABASE_URL=sqlite:///agent_sdk.db

# Observability
LOG_FORMAT=json
METRICS_ENABLED=true
```

**Impact**: No hardcoded secrets, easy configuration per environment

---

## 6. Dockerfile for Production
**File**: `Dockerfile` (NEW)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml requirements.txt* ./
RUN pip install --no-cache-dir -e .

# Copy application
COPY agent_sdk/ ./agent_sdk/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health').read()"

EXPOSE 9000

CMD ["agent-sdk", "serve", "http", "--host", "0.0.0.0", "--port", "9000"]
```

**Impact**: Consistent deployments, easier orchestration

---

## 7. Health Check Endpoint
**File**: Modify `agent_sdk/server/app.py`

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

def create_app(config_path: str = "config.yaml"):
    app = FastAPI()
    
    # Health check
    @app.get("/health")
    async def health():
        return JSONResponse(
            status_code=200,
            content={"status": "healthy", "version": "0.1.0"}
        )
    
    @app.get("/ready")
    async def readiness():
        """Readiness check - verify configuration loaded"""
        try:
            # Verify config is loaded, LLM is accessible, etc.
            return JSONResponse(status_code=200, content={"ready": True})
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"ready": False, "error": str(e)}
            )
    
    # ... rest of endpoints
```

**Impact**: Kubernetes/orchestrator can manage pod lifecycle

---

## 8. Retry Logic for LLM Calls
**File**: `agent_sdk/core/retry.py` (NEW)

```python
import asyncio
from typing import TypeVar, Callable, Any
import time

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    *args,
    **kwargs
) -> Any:
    """Retry function with exponential backoff"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = base_delay * (2 ** attempt)
                print(f"Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
    
    raise last_error or Exception("Max retries exceeded")

# Usage:
# response = await retry_with_backoff(llm.generate, 3, 1.0, messages, config)
```

**Impact**: Better resilience against transient failures

---

## 9. Thread-Safe Rate Limiter
**File**: Modify `agent_sdk/config/rate_limit.py`

```python
from threading import Lock
import time

class RateLimiter:
    def __init__(self, rules: List[RateLimitRule]):
        self.rules = rules
        self.call_history: Dict[str, deque] = defaultdict(deque)
        self.token_history: Dict[str, deque[Tuple[float, int]]] = defaultdict(deque)
        self._lock = Lock()  # ADD THIS
    
    def check(self, agent: str, model: str, tokens: int, tenant: str = "default"):
        with self._lock:  # WRAP IN LOCK
            now = time.time()
            for rule in self.rules:
                key = self._key(rule, agent, model, tenant)
                
                # Clean old entries
                while self.call_history[key] and now - self.call_history[key][0] > rule.window_seconds:
                    self.call_history[key].popleft()
                while self.token_history[key] and now - self.token_history[key][0][0] > rule.window_seconds:
                    self.token_history[key].popleft()
                
                # Check limits
                if rule.max_calls is not None and len(self.call_history[key]) >= rule.max_calls:
                    raise RateLimitError(f"Rate limit exceeded: {rule.name} (calls)")
                
                if rule.max_tokens is not None:
                    used = sum(t for _, t in self.token_history[key])
                    if used + tokens > rule.max_tokens:
                        raise RateLimitError(f"Rate limit exceeded: {rule.name} (tokens)")
            
            # Record
            for rule in self.rules:
                key = self._key(rule, agent, model, tenant)
                self.call_history[key].append(now)
                self.token_history[key].append((now, tokens))
```

**Impact**: Prevent race conditions in concurrent environments

---

## 10. Test Structure
**File**: `tests/conftest.py` (NEW)

```python
import pytest
from agent_sdk import AgentContext, Tool, GLOBAL_TOOL_REGISTRY
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.config.model_config import ModelConfig

@pytest.fixture
def mock_llm():
    return MockLLMClient()

@pytest.fixture
def model_config():
    return ModelConfig(
        name="test-gpt4",
        provider="openai",
        model_id="gpt-4",
        temperature=0.7,
        max_tokens=2048
    )

@pytest.fixture
def agent_context(model_config):
    return AgentContext(
        tools={},
        model_config=model_config,
        events=None,
        rate_limiter=None
    )

@pytest.fixture
def sample_tool():
    tool = Tool(
        name="test_echo",
        description="Echo back input",
        func=lambda args: args.get("text", "")
    )
    GLOBAL_TOOL_REGISTRY.register(tool)
    yield tool
    # Cleanup
    if tool.name in GLOBAL_TOOL_REGISTRY.tools:
        del GLOBAL_TOOL_REGISTRY.tools[tool.name]
```

**File**: `tests/test_agent.py` (NEW)

```python
import pytest
from agent_sdk.core.agent import Agent
from agent_sdk.core.messages import make_message

class TestAgent(Agent):
    def step(self, incoming):
        return make_message("agent", f"Processed: {incoming.content}")

def test_agent_step(agent_context):
    agent = TestAgent("test_agent", agent_context)
    msg = make_message("user", "Hello")
    response = agent.step(msg)
    
    assert response.role == "agent"
    assert "Processed" in response.content
    assert response.id is not None
```

**Impact**: Regression prevention, confidence in deployments

---

## 11. Configuration Schema Validation
**File**: `agent_sdk/config/loader.py` (MODIFY)

```python
import yaml
from pydantic import BaseModel, ValidationError

class ModelConfigDict(BaseModel):
    name: str
    provider: str
    model_id: str
    temperature: float = 0.2
    max_tokens: int = 1024

class AgentConfigDict(BaseModel):
    model: str  # must reference a defined model

class ConfigSchema(BaseModel):
    models: dict[str, ModelConfigDict]
    agents: dict[str, AgentConfigDict]
    rate_limits: list = []

def load_config(path: str, llm_client):
    try:
        with open(path, "r") as f:
            raw_cfg = yaml.safe_load(f)
        
        # Validate schema
        validated_cfg = ConfigSchema(**raw_cfg)
        
        # Rest of loading logic
    except ValidationError as e:
        raise ConfigError(f"Invalid configuration: {e}")
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")
```

**Impact**: Catch configuration errors at startup, not runtime

---

## Implementation Checklist

- [ ] Phase 1: Exception types + Logging + Input validation (2-3 days)
- [ ] Phase 2: API Auth + Environment config (1 day)
- [ ] Phase 3: Dockerfile + Health checks + Retry logic (2 days)
- [ ] Phase 4: Rate limiter thread safety + Tests (3 days)
- [ ] Phase 5: Configuration validation + Documentation (2 days)
- [ ] Phase 6: Review, fix issues, optimize (2 days)

**Total**: ~2 weeks to production-grade
