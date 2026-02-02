# Quick Reference Guide - New Production Modules

## 1. Exception Handling (`agent_sdk/exceptions.py`)

### Usage
```python
from agent_sdk.exceptions import (
    AgentSDKException,
    ConfigError,
    RateLimitError,
    ToolError,
    LLMError,
    ValidationError,
    TimeoutError
)

# Raise with context
raise ConfigError(
    message="Invalid configuration",
    code="CONFIG_INVALID",
    context={"field": "model", "reason": "not found"}
)

# Catch specific exceptions
try:
    load_config()
except ConfigError as e:
    print(f"Config error: {e.code}: {e.context}")
```

## 2. Structured Logging (`agent_sdk/logging_config.py`)

### Usage
```python
from agent_sdk.logging_config import setup_logging, logger

# Setup (once at startup)
setup_logging(level="INFO", format="json")

# Use global logger
logger.info("Task started", extra={"task_id": "123"})
logger.error("Failed to execute", exc_info=True)

# Add context filter for request tracking
from agent_sdk.logging_config import add_context_filter
add_context_filter(request_id="req-456")
```

### Output
```json
{
  "timestamp": "2024-02-01T22:32:00.123Z",
  "level": "INFO",
  "module": "agent",
  "function": "plan",
  "line": 42,
  "message": "Task started",
  "task_id": "123"
}
```

## 3. Input Validation (`agent_sdk/validators.py`)

### Usage
```python
from agent_sdk.validators import RunTaskRequest, ToolCallRequest

# Automatic validation
request = RunTaskRequest(task="Do something", timeout=300)

# Validation fails with clear error
try:
    request = RunTaskRequest(task="x" * 20000)  # Too long
except ValidationError as e:
    print(e.errors())  # [{"type": "string_too_long", ...}]
```

### Available Models
- `RunTaskRequest` - Task execution request
- `ToolCallRequest` - Tool invocation request
- `ModelConfigDict` - Model configuration
- `ConfigSchema` - Full config schema
- `TaskResponse` - Task execution response

## 4. Security (`agent_sdk/security.py`)

### API Key Authentication
```python
from agent_sdk.security import APIKeyManager, verify_api_key
from fastapi import Depends

# Setup (automatic from environment)
manager = APIKeyManager()  # Reads API_KEY env var

# Use in FastAPI
@app.post("/run", dependencies=[Depends(verify_api_key)])
async def run_task(request: RunTaskRequest):
    return {"status": "ok"}

# Client usage
headers = {"X-API-Key": "your-api-key"}
response = requests.post(url, headers=headers, json=data)
```

### Input Sanitization
```python
from agent_sdk.security import InputSanitizer

sanitizer = InputSanitizer(max_string_length=10000)
clean_input = sanitizer.sanitize(user_input)
# Removes null bytes, validates size
```

### PII Filtering
```python
from agent_sdk.security import PIIFilter

filter_obj = PIIFilter()
clean_text = filter_obj.filter_pii(user_text)
# Redacts emails, phones, API keys, passwords
```

## 5. Retry Logic (`agent_sdk/core/retry.py`)

### Async Usage
```python
from agent_sdk.core.retry import retry_with_backoff

# Automatically retries with exponential backoff
result = await retry_with_backoff(
    lambda: llm.generate(messages, config),
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0
)
```

### Sync Usage
```python
from agent_sdk.core.retry import sync_retry_with_backoff

result = sync_retry_with_backoff(
    lambda: tool.execute(args),
    max_retries=3
)
```

### Configuration
```python
from agent_sdk.core.retry import RetryConfig

config = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    exponential_base=2.0
)
```

## 6. Configuration Management (Updated `config/loader.py`)

### Usage
```python
from agent_sdk.config.loader import load_config

# Automatic validation and error handling
config = load_config("config.yaml")
# Raises ConfigError with clear messages if invalid

# Access loaded config
model_config = config.models["gpt4"]
agent_config = config.agents["planner"]
```

### Features
- Environment variable expansion (~user, $VAR)
- Schema validation with Pydantic
- Detailed error messages
- Logging at all stages

## 7. Deployment

### Docker
```bash
# Build image
docker build -t agent-sdk:latest .

# Run container
docker run -p 8000:8000 \
  -e API_KEY=your-key \
  -e OPENAI_API_KEY=your-key \
  agent-sdk:latest
```

### Docker Compose
```bash
# Start all services
docker-compose up

# Access API
curl http://localhost:8000/health
```

### Environment Variables
```bash
# Copy example and fill in values
cp .env.example .env

# Source in your shell
export $(cat .env | xargs)
```

## 8. Testing

### Run Tests
```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_api.py -v

# With coverage
pytest tests/ --cov=agent_sdk
```

### Write Tests
```python
import pytest
from agent_sdk.conftest import mock_llm, agent_context

def test_my_feature(agent_context, mock_llm):
    # Test code here
    pass

@pytest.mark.asyncio
async def test_async_feature():
    # Async test code
    pass
```

## 9. API Endpoints

### Health Check
```bash
GET /health
# Response: {"status": "healthy", "version": "1.0"}
```

### Ready Check
```bash
GET /ready
# Response: {"ready": true, "components": [...]}
```

### Run Task
```bash
POST /run
Header: X-API-Key: your-api-key
Body: {"task": "Do something", "timeout": 300}
# Response: {"task_id": "...", "status": "pending", "result": null}
```

### List Tools
```bash
GET /tools
# Response: [{"name": "search", "description": "...", "inputs": {...}}]
```

## 10. Common Patterns

### Error Handling
```python
from agent_sdk.exceptions import ToolError, LLMError

try:
    result = await executor.run_tool(step)
except ToolError as e:
    logger.error(f"Tool error: {e.code}", extra=e.context)
    # Handle tool-specific error
except LLMError as e:
    logger.error(f"LLM error: {e.message}")
    # Handle LLM-specific error
```

### Validation
```python
from agent_sdk.validators import RunTaskRequest
from pydantic import ValidationError

try:
    request = RunTaskRequest(**user_data)
except ValidationError as e:
    # e.errors() contains detailed validation errors
    return {"errors": e.errors()}, 422
```

### Rate Limiting
```python
from agent_sdk.config.rate_limit import RateLimiter
from agent_sdk.exceptions import RateLimitError

limiter = RateLimiter(max_requests=100, window_seconds=60)

try:
    limiter.check()
except RateLimitError:
    return {"error": "Rate limit exceeded"}, 429
```

### Logging
```python
from agent_sdk.logging_config import logger

logger.info("Operation started", extra={
    "task_id": task_id,
    "model": config.model,
    "temperature": config.temperature
})

try:
    result = await llm.generate(messages, config)
except Exception as e:
    logger.error("LLM call failed", exc_info=True, extra={
        "error_type": type(e).__name__,
        "task_id": task_id
    })
```

## Version Info
- **Created**: February 2024
- **Status**: Production Ready
- **Test Coverage**: 59 tests
- **Python Version**: 3.10+

## Support Resources
- See IMPLEMENTATION_SUMMARY.md for overview
- See PRODUCTION_IMPLEMENTATION_REPORT.md for detailed changes
- Check test files for usage examples
- Review docstrings in each module

