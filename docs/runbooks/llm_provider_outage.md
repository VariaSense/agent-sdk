# Runbook: LLM Provider Outage

## Symptoms
- Elevated 5xx responses from run endpoints.
- Provider health endpoint reports unhealthy status.
- Increased retry/fallback activity.

## Immediate Actions
- Confirm provider status from `/admin/providers/health`.
- Enable failover to secondary provider if configured.
- Increase retry backoff if the provider is rate limiting.

## Mitigation Steps
1. Update model routing policy to prefer healthy providers.
2. Throttle non-critical traffic or reduce concurrency.
3. Communicate degradation to stakeholders.

## Recovery
- Monitor error rate and latency until normal.
- Restore primary provider when stable.
- Review usage impact and cost changes.
