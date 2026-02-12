# Compatibility Matrix

## SDK Versioning
- Major versions may include breaking API changes.
- Minor versions add features without breaking stable public APIs.
- Patch versions include fixes only.

## Supported Compatibility
- Current major: 0
- Supported API version: v1
- Upgrade guidance: validate CLI `compat upgrade-check` before deploying.

## Contract Stability
- Event envelope schema is stable across minor versions.
- Policy bundle structure is stable within the same major version.
- Storage schemas are migrated via Alembic.
