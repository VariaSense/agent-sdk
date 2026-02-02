# Implementation Checklist: Files to Create & Modify

## Phase 1: Foundation (Week 1)

### New Files to Create

#### 1. `agent_sdk/exceptions.py`
```python
"""Custom exception types for Agent SDK"""

class AgentSDKException(Exception):
    """Base exception for all Agent SDK errors"""
    def __init__(self, message: str, code: str = None, context: dict = None):
        self.message = message
        self.code = code
        self.context = context or {}
        super().__init__(message)

class ConfigError(AgentSDKException):
    """Raised when configuration is invalid or missing"""
    pass

class RateLimitError(AgentSDKException):
    """Raised when rate limit is exceeded"""
    pass

class ToolError(AgentSDKException):
    """Raised when tool execution fails"""
    pass

class LLMError(AgentSDKException):
    """Raised when LLM API call fails"""
    pass

class ValidationError(AgentSDKException):
    """Raised when input validation fails"""
    pass

class TimeoutError(AgentSDKException):
    """Raised when operation times out"""
    pass
```
**Status**: ⬜ TODO  
**Priority**: 🔴 CRITICAL  
**Lines**: ~40  

---

#### 2. `agent_sdk/logging_config.py`
```python
"""Structured logging configuration"""

import logging
import json
import sys
from typing import Any, Dict, Optional
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON structured logging formatter"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "context"):
            log_data.update(record.context)
        
        return json.dumps(log_data)

def setup_logging(
    name: str = "agent_sdk",
    level: str = "INFO",
    format_json: bool = False
) -> logging.Logger:
    """Configure logger for Agent SDK"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    handler = logging.StreamHandler(sys.stdout)
    
    if format_json:
        handler.setFormatter(JSONFormatter())
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger

def add_context(logger: logging.Logger, context: Dict[str, Any]):
    """Add context to logger record"""
    class ContextFilter(logging.Filter):
        def filter(self, record):
            record.context = context
            return True
    
    logger.addFilter(ContextFilter())
```
**Status**: ⬜ TODO  
**Priority**: 🔴 CRITICAL  
**Lines**: ~60  

---

#### 3. `agent_sdk/validators.py`
```python
"""Input validation schemas using Pydantic"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, Dict, Any, List

class RunTaskRequest(BaseModel):
    """Validate task execution request"""
    task: str = Field(..., min_length=1, max_length=10000, description="Task description")
    config: Optional[str] = Field(None, description="Path to config file")
    timeout: Optional[int] = Field(default=300, ge=1, le=3600, description="Timeout in seconds")
    
    @validator('task')
    def task_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Task cannot be empty')
        return v.strip()

class ToolCallRequest(BaseModel):
    """Validate tool call request"""
    tool_name: str = Field(..., regex=r'^[a-z_][a-z0-9_]*$', description="Tool name")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Tool inputs")
    
    @validator('inputs')
    def inputs_not_too_large(cls, v):
        if len(str(v)) > 100000:  # 100KB limit
            raise ValueError('Inputs too large')
        return v

class ConfigValidation(BaseModel):
    """Validate SDK configuration"""
    model_name: str = Field(..., regex=r'^[a-z0-9_-]+$')
    provider: str = Field(..., regex=r'^[a-z0-9_]+$')
    model_id: str
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=128000)

class ListToolsResponse(BaseModel):
    """Response for listing tools"""
    tools: List[Dict[str, Any]]
    count: int

class TaskResponse(BaseModel):
    """Response from task execution"""
    status: str = Field(..., regex=r'^(success|error|pending)$')
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float
```
**Status**: ⬜ TODO  
**Priority**: 🔴 CRITICAL  
**Lines**: ~70  

---

#### 4. `agent_sdk/security.py`
```python
"""Security utilities: authentication, authorization, secrets"""

import os
import hashlib
import hmac
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Header
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class APIKeyManager:
    """Manage API keys for authentication"""
    
    def __init__(self):
        self.valid_keys = set()
        self._load_keys()
    
    def _load_keys(self):
        """Load API keys from environment"""
        api_key = os.getenv("API_KEY")
        if api_key:
            self.valid_keys.add(api_key)
    
    def verify_key(self, key: str) -> bool:
        """Verify if key is valid"""
        if not key:
            return False
        return key in self.valid_keys

async def verify_api_key(
    x_api_key: Optional[str] = Header(None)
) -> str:
    """FastAPI dependency for API key verification"""
    if not x_api_key:
        logger.warning("Request without API key")
        raise HTTPException(
            status_code=401,
            detail="Missing API key in X-API-Key header"
        )
    
    api_key_manager = APIKeyManager()
    if not api_key_manager.verify_key(x_api_key):
        logger.warning(f"Invalid API key attempted")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    logger.info("Request authenticated successfully")
    return x_api_key

class InputSanitizer:
    """Sanitize inputs to prevent injection"""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 10000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            raise ValueError("Expected string")
        
        if len(value) > max_length:
            raise ValueError(f"String exceeds max length of {max_length}")
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        return value.strip()

class PII_Filter:
    """Filter out PII from logs"""
    PII_PATTERNS = {
        "api_key": r"sk-[a-zA-Z0-9]+",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    }
    
    @staticmethod
    def filter_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove PII from dictionary"""
        import re
        filtered = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Redact sensitive fields
                if any(sensitive in key.lower() for sensitive in ["password", "key", "token", "secret"]):
                    filtered[key] = "[REDACTED]"
                else:
                    filtered[key] = value
            elif isinstance(value, dict):
                filtered[key] = PII_Filter.filter_dict(value)
            else:
                filtered[key] = value
        
        return filtered
```
**Status**: ⬜ TODO  
**Priority**: 🔴 CRITICAL  
**Lines**: ~90  

---

### Existing Files to Modify

#### Modify: `agent_sdk/config/rate_limit.py`
**Change**: Add thread safety with Lock

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
        with self._lock:  # WRAP THIS
            # ... rest of implementation
```
**Status**: ⬜ TODO  
**Priority**: 🟠 HIGH  
**Lines Modified**: ~5  

---

#### Modify: `agent_sdk/server/app.py`
**Change**: Add authentication, validation, health checks

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agent_sdk.security import verify_api_key
from agent_sdk.validators import RunTaskRequest, TaskResponse
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

def create_app(config_path: str = "config.yaml"):
    app = FastAPI(title="Agent SDK", version="0.1.0")
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health check
    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": "0.1.0"}
    
    @app.get("/ready")
    async def readiness():
        try:
            # Verify config loaded, etc
            return {"ready": True}
        except Exception as e:
            logger.error(f"Readiness check failed: {e}")
            raise HTTPException(status_code=503, detail="Not ready")
    
    # Task execution with auth + validation
    @app.post("/run", response_model=TaskResponse, dependencies=[Depends(verify_api_key)])
    async def run_task(req: RunTaskRequest):
        try:
            msgs = await runtime.run_async(req.task)
            return TaskResponse(
                status="success",
                result={"messages": [m.__dict__ for m in msgs]},
                execution_time_ms=0
            )
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Task execution failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Task execution failed")
    
    return app
```
**Status**: ⬜ TODO  
**Priority**: 🔴 CRITICAL  
**Lines Modified**: ~40  

---

### New Configuration Files

#### 4. `.env.example`
```
# Environment
AGENT_SDK_ENV=development
AGENT_SDK_LOG_LEVEL=INFO
LOG_FORMAT=json

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

# Configuration Files
CONFIG_PATH=config.yaml
```
**Status**: ⬜ TODO  
**Priority**: 🟠 HIGH  

---

#### 5. `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application
COPY agent_sdk/ ./agent_sdk/

# Expose port
EXPOSE 9000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health').read()"

# Run application
CMD ["agent-sdk", "serve", "http"]
```
**Status**: ⬜ TODO  
**Priority**: 🔴 CRITICAL  

---

#### 6. `docker-compose.yml`
```yaml
version: '3.8'

services:
  agent-sdk:
    build: .
    ports:
      - "9000:9000"
    environment:
      AGENT_SDK_ENV: development
      AGENT_SDK_LOG_LEVEL: DEBUG
      API_KEY: dev-key-123
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
```
**Status**: ⬜ TODO  
**Priority**: 🟠 HIGH  

---

### Test Files

#### 7. `tests/__init__.py`
```python
"""Test suite for Agent SDK"""
```

#### 8. `tests/conftest.py`
```python
"""Shared test configuration and fixtures"""

import pytest
from agent_sdk import AgentContext, Tool, GLOBAL_TOOL_REGISTRY
from agent_sdk.config.model_config import ModelConfig
from agent_sdk.llm.mock import MockLLMClient

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
```

#### 9. `tests/test_exceptions.py`
```python
"""Test custom exceptions"""

import pytest
from agent_sdk.exceptions import (
    RateLimitError,
    ConfigError,
    ToolError,
    ValidationError
)

def test_rate_limit_error():
    with pytest.raises(RateLimitError):
        raise RateLimitError("Exceeded limit")

def test_config_error():
    with pytest.raises(ConfigError):
        raise ConfigError("Invalid config", code="CONFIG_INVALID")
```

#### 10. `tests/test_validators.py`
```python
"""Test input validators"""

import pytest
from pydantic import ValidationError
from agent_sdk.validators import RunTaskRequest

def test_valid_task_request():
    req = RunTaskRequest(task="Do something")
    assert req.task == "Do something"

def test_empty_task_fails():
    with pytest.raises(ValidationError):
        RunTaskRequest(task="")

def test_task_too_long_fails():
    with pytest.raises(ValidationError):
        RunTaskRequest(task="x" * 10001)
```

#### 11. `tests/test_security.py`
```python
"""Test security utilities"""

import os
import pytest
from agent_sdk.security import APIKeyManager, InputSanitizer

def test_api_key_verification():
    os.environ["API_KEY"] = "test-key"
    manager = APIKeyManager()
    assert manager.verify_key("test-key")
    assert not manager.verify_key("wrong-key")

def test_input_sanitization():
    result = InputSanitizer.sanitize_string("  hello world  ")
    assert result == "hello world"
```

**Status**: ⬜ TODO  
**Priority**: 🔴 CRITICAL  

---

### Update `pyproject.toml`

Add test and dev dependencies:

```toml
[project]
# ... existing ...

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "black>=23.0",
    "mypy>=1.0",
    "pylint>=2.16",
    "pre-commit>=3.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "--cov=agent_sdk --cov-report=html --cov-report=term"

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
```

**Status**: ⬜ TODO  
**Priority**: 🟠 HIGH  

---

## Summary by Priority

### 🔴 CRITICAL (Do First - Week 1)
- [ ] `agent_sdk/exceptions.py` - Exception types
- [ ] `agent_sdk/logging_config.py` - Structured logging
- [ ] `agent_sdk/validators.py` - Input validation
- [ ] `agent_sdk/security.py` - Authentication
- [ ] Modify `agent_sdk/server/app.py` - Add auth + validation
- [ ] Modify `agent_sdk/config/rate_limit.py` - Thread safety
- [ ] Create `Dockerfile`
- [ ] Update `pyproject.toml` - Add dependencies
- [ ] Create `tests/` structure

### 🟠 HIGH (Week 1-2)
- [ ] `.env.example` - Environment template
- [ ] `docker-compose.yml` - Local development
- [ ] `tests/conftest.py` - Test fixtures
- [ ] `tests/test_*.py` - Initial tests (20% coverage)

### 🟡 MEDIUM (Week 2+)
- [ ] Additional integration tests
- [ ] Performance optimization
- [ ] Advanced monitoring
- [ ] Documentation

---

## Verification Checklist

After implementing all changes:

- [ ] All imports resolve (no circular dependencies)
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Type checking: `mypy agent_sdk --strict`
- [ ] Linting: `pylint agent_sdk`
- [ ] Code format: `black agent_sdk`
- [ ] Docker builds: `docker build .`
- [ ] API starts: `docker-compose up`
- [ ] Health check works: `curl http://localhost:9000/health`
- [ ] Authentication works: Missing key returns 401
- [ ] Invalid input rejected: Returns 400

---

## Success Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Test Coverage | 0% | 20% | 80% |
| Custom Exceptions Used | 0% | 80% | 100% |
| Input Validation | 0% | 100% | 100% |
| Authentication | ❌ | ✅ | ✅ |
| Deployable | ❌ | ✅ | ✅ |
| Health Checks | ❌ | ✅ | ✅ |
| Type Hints | 35% | 55% | 90% |
| Logging | 5% | 80% | 100% |
