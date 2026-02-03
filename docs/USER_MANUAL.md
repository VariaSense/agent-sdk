# Agent SDK - User Manual

## Table of Contents

1. [Getting Started](#getting-started)
2. [Installation](#installation)
3. [Basic Usage](#basic-usage)
4. [Core Concepts](#core-concepts)
5. [Common Tasks](#common-tasks)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)
8. [Examples](#examples)

---

## Getting Started

The Agent SDK is a production-grade agent framework that provides:
- **Planning & Execution**: Decompose tasks into steps and execute them
- **LLM Integration**: Built-in support for multiple LLM providers
- **Tool System**: Easily add custom tools and integrations
- **Rate Limiting**: Protect your API usage
- **Observability**: Track events and metrics
- **API Server**: Built-in FastAPI server for remote execution
- **Dashboard**: Monitor agents in real-time

### What is an Agent?

An agent is an autonomous system that:
1. **Receives** a task from a user
2. **Plans** how to accomplish it (breaks into steps)
3. **Executes** the plan using available tools
4. **Iterates** based on results

### Prerequisites

- Python 3.9+
- pip or conda
- API keys for LLM providers (OpenAI, etc.)

---

## Installation

### From PyPI (Recommended)

```bash
pip install agent-sdk
```

### From Source

```bash
git clone <repo>
cd agent-sdk
pip install -e .
```

### Verify Installation

```bash
agent-sdk --version
python -c "from agent_sdk import Agent; print('✓ Agent SDK installed')"
```

---

## Basic Usage

### 1. Simple Task Execution

```python
from agent_sdk.core.agent import Agent
from agent_sdk.llm.mock import MockLLM
from agent_sdk.core.context import AgentContext

# Create context
context = AgentContext()

# Create agent
agent = Agent(name="assistant", context=context, llm=MockLLM())

# Run task
import asyncio
result = asyncio.run(agent.plan("Write a greeting"))
print(result)
```

### 2. Using the CLI

```bash
# Initialize a new project
agent-sdk init project my-app

# Run a task
agent-sdk run "Do something useful"

# Start the server
agent-sdk server --port 8000

# Check health
curl http://localhost:8000/health
```

### 3. Using the API Server

```bash
# Start the server
agent-sdk server

# Set API key
export API_KEY="your-api-key"

# Run task via API
curl -X POST http://localhost:8000/run \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"task": "Write a Python function"}'
```

---

## Core Concepts

### Agent

An agent orchestrates task execution:
```python
from agent_sdk.core.agent import Agent

agent = Agent(
    name="my-agent",
    context=context,
    llm=llm_client
)
```

### Context

Stores state during execution:
```python
from agent_sdk.core.context import AgentContext

context = AgentContext()
context.add_short_term_message({"role": "user", "content": "..."})
```

**Features:**
- Message history (short-term: 1000, long-term: 10000)
- Automatic cleanup of old messages
- Tool registry
- Rate limiter
- Event bus

### Plan

Decomposition of a task into steps:
```python
from agent_sdk.planning.plan_schema import Plan, PlanStep

plan = Plan(
    task="Do something",
    steps=[
        PlanStep(id=1, description="Step 1", tool="search", inputs={}),
        PlanStep(id=2, description="Step 2", tool="write", inputs={}),
    ]
)
```

### Tools

Callable functions available to agents:
```python
def my_tool(inputs: dict) -> str:
    return f"Result: {inputs}"

context.tools["my_tool"] = my_tool
```

### Events

Track what's happening:
```python
from agent_sdk.observability.bus import EventBus

event_bus = EventBus()
event_bus.subscribe("*", lambda e: print(f"Event: {e}"))
```

---

## Common Tasks

### Task 1: Create a Custom Tool

```python
from agent_sdk.core.agent import Agent
from agent_sdk.core.context import AgentContext

def search_web(inputs: dict) -> str:
    """Search the web for information"""
    query = inputs.get("query", "")
    return f"Search results for: {query}"

# Register the tool
context = AgentContext()
context.tools["search_web"] = search_web

# Now agents can use it!
agent = Agent("assistant", context=context)
```

### Task 2: Configure LLM Provider

```python
from agent_sdk.config.model_config import ModelConfig
from agent_sdk.llm.base import LLMClient

# Create model config
config = ModelConfig(
    name="gpt-4",
    provider="openai",
    model_id="gpt-4",
    temperature=0.7,
    max_tokens=2048
)

# Set API key
import os
os.environ["OPENAI_API_KEY"] = "your-key"

# Use with agent
agent = Agent("assistant", context=context)
```

### Task 3: Set Up Rate Limiting

```python
from agent_sdk.config.rate_limit import RateLimiter

# Create rate limiter
limiter = RateLimiter(
    max_requests=100,
    window_seconds=60
)

# Add to context
context.rate_limiter = limiter

# Use in code
try:
    limiter.check(agent_name="assistant", model="gpt-4")
    # Make API call
except Exception as e:
    print(f"Rate limited: {e}")
```

### Task 4: Handle Errors Gracefully

```python
from agent_sdk.exceptions import ToolError, LLMError, ValidationError
import asyncio

try:
    result = asyncio.run(agent.plan("Do something"))
except ToolError as e:
    print(f"Tool error: {e.code} - {e.message}")
except LLMError as e:
    print(f"LLM error: {e.message}")
except ValidationError as e:
    print(f"Validation error: {e.message}")
```

### Task 5: Monitor Events

```python
from agent_sdk.observability.bus import EventBus

def event_handler(event):
    print(f"[{event.event_type}] {event.source}: {event.data}")

event_bus = EventBus()
event_bus.subscribe("*", event_handler)

# Events emitted automatically:
# - executor.tool.call
# - executor.tool.error
# - llm.latency
# - llm.usage
# - etc.
```

---

## API Reference

### Agent

```python
class Agent:
    def __init__(self, name: str, context: AgentContext, llm: LLMClient)
    
    async def plan(task: str) -> dict
        """Generate a plan for the task"""
    
    async def execute(plan: Plan) -> list
        """Execute the plan"""
    
    async def step(message: Message) -> Message
        """Execute one step"""
```

### AgentContext

```python
class AgentContext:
    def add_short_term_message(message: dict) -> None
        """Add to short-term memory (max 1000)"""
    
    def add_long_term_message(message: dict) -> None
        """Add to long-term memory (max 10000)"""
    
    def cleanup_old_messages() -> None
        """Manually cleanup old messages"""
    
    @property
    def short_term: list
        """Short-term message history"""
    
    @property
    def long_term: list
        """Long-term message history"""
```

### RateLimiter

```python
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int)
    
    def check(agent: str, model: str, tokens: int = 0) -> None
        """Check if request is allowed, raises RateLimitError if not"""
```

### Exceptions

```python
# Custom exception hierarchy
AgentSDKException          # Base class
├── ConfigError           # Configuration issues
├── RateLimitError        # Rate limit exceeded
├── ToolError             # Tool execution failed
├── LLMError              # LLM API failed
├── ValidationError       # Input validation failed
└── TimeoutError          # Operation timed out

# Usage:
try:
    ...
except ToolError as e:
    print(f"Code: {e.code}, Context: {e.context}")
```

---

## Troubleshooting

### Problem: "API Key not set"

**Solution:**
```bash
export API_KEY="your-key"
export OPENAI_API_KEY="your-openai-key"
```

Or in code:
```python
import os
os.environ["API_KEY"] = "your-key"
```

### Problem: "Tool not found"

**Solution:**
```python
# Register tools before using
context.tools["my_tool"] = my_tool_function
```

### Problem: "Rate limit exceeded"

**Solution:**
```python
# Increase rate limit
limiter = RateLimiter(max_requests=1000, window_seconds=60)
context.rate_limiter = limiter
```

### Problem: "LLM call failed"

**Solution:**
```python
# Retry logic is automatic with exponential backoff
# Check API key and network connectivity
# Review logs for details
```

### Problem: "Memory usage is high"

**Solution:**
```python
# Messages are automatically cleaned up
# To manually cleanup:
context.cleanup_old_messages()

# Check limits:
print(f"Short-term: {len(context.short_term)} / {context.max_short_term}")
print(f"Long-term: {len(context.long_term)} / {context.max_long_term}")
```

---

## Examples

### Example 1: Simple Task

```python
import asyncio
from agent_sdk.core.agent import Agent
from agent_sdk.core.context import AgentContext
from agent_sdk.llm.mock import MockLLM

async def main():
    context = AgentContext()
    agent = Agent("assistant", context, MockLLM())
    
    plan = await agent.plan("Greet the user")
    print(plan)

asyncio.run(main())
```

### Example 2: Custom Tool

```python
def calculator(inputs: dict) -> str:
    operation = inputs.get("operation")
    a = inputs.get("a", 0)
    b = inputs.get("b", 0)
    
    if operation == "add":
        return str(a + b)
    elif operation == "multiply":
        return str(a * b)
    return "Unknown operation"

context.tools["calculator"] = calculator

# Agent can now use: {"tool": "calculator", "inputs": {"operation": "add", "a": 5, "b": 3}}
```

### Example 3: Error Handling

```python
from agent_sdk.exceptions import ToolError, LLMError

def risky_tool(inputs: dict) -> str:
    if "error" in inputs:
        raise ToolError("Something went wrong", code="TOOL_001")
    return "Success"

context.tools["risky_tool"] = risky_tool

try:
    result = context.tools["risky_tool"]({"error": True})
except ToolError as e:
    print(f"Error {e.code}: {e.message}")
```

### Example 4: Event Monitoring

```python
from agent_sdk.observability.bus import EventBus

def log_event(event):
    print(f"[{event.timestamp}] {event.event_type}: {event.data}")

event_bus = EventBus()
event_bus.subscribe("*", log_event)

# Events are emitted during execution
```

### Example 5: Docker Deployment

```bash
# Build image
docker build -t agent-sdk:latest .

# Run container
docker run -p 8000:8000 \
  -e API_KEY="your-key" \
  -e OPENAI_API_KEY="your-openai-key" \
  agent-sdk:latest

# Test
curl http://localhost:8000/health
```

---

## Next Steps

1. **Read**: [Production Implementation Report](../documents/PRODUCTION_IMPLEMENTATION_REPORT.md)
2. **Review**: [Quick Reference](../documents/QUICK_REFERENCE.md)
3. **Explore**: Source code in `agent_sdk/` folder
4. **Test**: Run `pytest tests/ -v`
5. **Deploy**: Use Docker or run directly

---

## Support

- **Documentation**: See `documents/` folder in installation
- **Issues**: Check [GitHub Issues](https://github.com)
- **Examples**: See `examples/` folder or this manual
- **API Docs**: Run `agent-sdk server` then visit OpenAPI docs

---

**Version**: 1.0  
**Last Updated**: February 2024  
**Status**: Production Ready ✅
