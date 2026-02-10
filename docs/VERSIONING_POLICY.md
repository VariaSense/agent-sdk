# Versioning and Compatibility Policy

Agent SDK follows semantic versioning for server APIs and client SDKs.

## Policy
- **Major version** changes (X.0.0) may introduce breaking changes.
- **Minor version** changes (0.X.0) add backward-compatible features.
- **Patch version** changes (0.0.X) include bug fixes only.

## Compatibility Checks
Client SDKs compare their major version against the server `/v1/health` version.
- If majors match, compatibility is considered **true**.
- If majors differ, compatibility is **false** and clients should upgrade.

## Deprecation
Unversioned API requests return an `X-API-Deprecated` response header.
Use `/v1/...` for all production integrations.
