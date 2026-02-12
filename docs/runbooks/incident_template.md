# Incident Runbook Template

## Summary
- Incident ID:
- Start time:
- Detection source:
- Impacted services:
- Severity:

## Immediate Actions
- Acknowledge alert and assign incident commander.
- Verify scope and blast radius.
- Disable non-critical features if needed.

## Diagnostics
- Check recent deploys and config changes.
- Inspect logs for errors and latency spikes.
- Validate dependency health (LLM providers, storage, webhooks).

## Mitigation
- Roll back deployments if necessary.
- Reduce load via rate limiting or feature flags.
- Failover to backup providers.

## Resolution
- Confirm system stability.
- Update status page.
- Capture root cause and remediation tasks.

## Post-Incident
- Write incident report within 24 hours.
- Update runbooks and alerts as needed.
- Add regression tests for the root cause.
