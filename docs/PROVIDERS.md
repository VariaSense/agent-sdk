# Provider Integrations

This SDK includes first-class provider clients with error normalization.

## OpenAI
Environment:
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (optional)

Usage:
```python
from agent_sdk.llm.providers import create_openai_client
client = create_openai_client()
```

## Anthropic
Environment:
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_BASE_URL` (optional)

Usage:
```python
from agent_sdk.llm.providers import create_anthropic_client
client = create_anthropic_client()
```

## Azure OpenAI
Environment:
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_VERSION` (optional)

Usage:
```python
from agent_sdk.llm.providers import create_azure_client
client = create_azure_client()
```

## Error Normalization
Provider errors are normalized into `ProviderError` with:
- `status_code`
- `code`
- `message`
- `retriable`
