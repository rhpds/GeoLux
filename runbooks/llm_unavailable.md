# Runbook: LLM Unavailable

## Trigger
LLM endpoint is unreachable or returning errors across all components.

## Severity
**Critical** — All LLM-dependent components degrade simultaneously.

## Automatic Degradation
- **Hypothesis Engine**: queues last known hypotheses with staleness flag
- **Classification**: semantic constraints return inconclusive; deterministic constraints unaffected
- **LLM-MPC**: returns empty predictions, suspends planning
- **Deepfield**: falls back to rule-based classification (static policy)
- **Stability**: all calls return score 0.0, state unstable_fail

## Investigation
1. Check LiteLLM endpoint: `curl $GEOLUX_LITELLM_URL/health`
2. Check API key validity
3. Check rate limits and quotas
4. Check network connectivity between GeoLux and LLM endpoint

## Recovery
All components automatically resume normal operation when the LLM endpoint recovers. No manual intervention needed beyond fixing the LLM service.

## Escalation
- Unavailable > 15 minutes: page on-call SRE
- Unavailable > 1 hour: notify platform team lead
