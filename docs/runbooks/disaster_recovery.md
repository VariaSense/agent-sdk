# Disaster Recovery Runbook

## Objectives
- Restore service within the agreed RTO.
- Preserve data integrity (audit logs, runs, sessions, usage records).

## Preconditions
- Backups enabled and tested.
- Access to storage (DB snapshots / backups) and control plane backups.

## Recovery Steps
1. Declare incident and assign incident commander.
2. Stop writes to the primary system (maintenance mode).
3. Restore storage database (runs/sessions/events).
4. Restore control plane database (orgs/users/keys/policies).
5. Validate `/health` and `/ready` endpoints.
6. Re-enable traffic gradually.

## Validation Checklist
- Run a read-only query to confirm orgs and API keys exist.
- Verify audit log export is available.
- Run a sample `/run` and confirm streaming works.

## Game Day Checklist
- Verify backups in the last 24 hours.
- Restore to a staging environment.
- Execute a synthetic run and verify observability.
- Document gaps and update runbooks.
