# Module Ownership

## Purpose

This document records the top-level ownership decision for the current `agent-sdk` modules.

## Classifications

- `sdk-core`: reusable domain/runtime logic
- `sdk-adapter`: reusable infrastructure adapter or integration point
- `sdk-app-shell`: local developer or packaging shell around the SDK
- `needs-boundary-review`: currently present in the SDK but likely to move out or be narrowed

## Ownership Map

- `agents`: `sdk-core`
- `archival.py`: `needs-boundary-review`
- `billing.py`: `deprecated-compat-shim`
- `cli`: `sdk-app-shell`
- `config`: `sdk-core`
- `contracts`: `sdk-core`
- `coordination`: `sdk-core`
- `core`: `sdk-core`
- `dashboard`: `deprecated-compat-shim`
- `data_connectors`: `sdk-adapter`
- `docs.py`: `sdk-app-shell`
- `encryption.py`: `sdk-adapter`
- `exceptions.py`: `sdk-core`
- `execution`: `sdk-core`
- `finetuning`: `needs-boundary-review`
- `human_in_the_loop`: `needs-boundary-review`
- `identity`: `sdk-adapter`
- `interfaces`: `sdk-core`
- `llm`: `sdk-adapter`
- `logging_config.py`: `sdk-adapter`
- `memory`: `sdk-core`
- `observability`: `sdk-adapter`
- `planning`: `sdk-core`
- `plugins`: `sdk-adapter`
- `policies`: `needs-boundary-review`
- `policy`: `needs-boundary-review`
- `presets`: `sdk-core`
- `privacy.py`: `deprecated-compat-shim`
- `prompt_management`: `sdk-core`
- `registry`: `sdk-core`
- `reliability`: `sdk-core`
- `routing`: `sdk-core`
- `runtime`: `sdk-core`
- `sandbox.py`: `sdk-adapter`
- `secrets.py`: `sdk-adapter`
- `secrets_rotation.py`: `needs-boundary-review`
- `security`: `needs-boundary-review`
- `security.py`: `needs-boundary-review`
- `server`: `deprecated-compat-shim-plus-generic-support`
- `storage`: `sdk-adapter`
- `testing`: `sdk-core`
- `tool_packs`: `sdk-core`
- `ui`: `needs-boundary-review`
- `validators.py`: `sdk-core`
- `versioning.py`: `sdk-core`
- `webhooks.py`: `deprecated-compat-shim`
