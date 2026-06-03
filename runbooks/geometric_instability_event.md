# Runbook: Geometric Instability Event

## Trigger
Sustained geometric instability detected — stability scores consistently below
the configured threshold (default 0.7) across multiple LLM calls.

## Severity
**High** — Unstable LLM outputs may produce unreliable hypotheses, incorrect
classifications, or unsafe MPC actions.

## Symptoms
- Stability monitor widget shows sustained scores below threshold
- `glx_llm_stability_records` shows consecutive `unstable_pass` or `unstable_fail` states
- Kafka `audit.event` topic receiving `stability.threshold.breach` events
- Hypothesis engine generating fewer hypotheses (instability gate blocking)
- MPC horizon collapsing to minimum

## Investigation Steps

1. **Check stability score trends**
   ```sql
   SELECT endpoint, stability_score, stability_state, created_at
   FROM glx_llm_stability_records
   ORDER BY created_at DESC
   LIMIT 50;
   ```

2. **Identify affected endpoints**
   ```sql
   SELECT endpoint, COUNT(*), AVG(stability_score)
   FROM glx_llm_stability_records
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY endpoint
   ORDER BY AVG(stability_score) ASC;
   ```

3. **Check LLM service health**
   - Verify LiteLLM endpoint is responding: `curl $GEOLUX_LITELLM_URL/health`
   - Check model availability and response latency
   - Verify API key is valid and rate limits not exceeded

4. **Check input data quality**
   - Review recent evidence bundles for anomalies
   - Check if novel input distributions are causing instability
   - Verify collectors are producing well-formed evidence

5. **Check infrastructure**
   - Verify GPU/CPU utilization on inference servers
   - Check for memory pressure or thermal throttling
   - Review network latency between GeoLux and LLM endpoint

## Remediation

### Immediate
- Components automatically degrade when instability is sustained:
  - Hypothesis Engine: stops generating, queues last known hypotheses with staleness flag
  - LLM-MPC: suspends planning, falls back to reactive classification
  - Deepfield: suspends adaptive routing, falls back to static policy
- Verify these automatic degradations are active

### Short-term
- If LLM endpoint is degraded: wait for recovery, stability will resume
- If input data has changed: review evidence normalizers for new patterns
- If model has changed: verify model version matches expected configuration
- Consider temporarily raising the stability threshold to be more permissive

### Long-term
- Review stability threshold calibration against recent operational data
- Consider adding additional measurement methods for robustness
- Document the incident and root cause in the operational log

## Escalation
- If instability persists > 30 minutes: page on-call SRE
- If all LLM-dependent components are degraded: notify platform team lead
- If instability correlates with model deployment: notify ML ops team

## Recovery Verification
- Stability scores return above threshold for 10+ consecutive calls
- Hypothesis generation resumes normally
- MPC horizon recovers to configured default
- All stability states show healthy distribution in dashboard
