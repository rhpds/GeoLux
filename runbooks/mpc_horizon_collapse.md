# Runbook: MPC Horizon Collapse

## Trigger
MPC prediction horizon has collapsed to minimum (1 step) or MPC has been
suspended due to sustained geometric instability in prediction calls.

## Severity
**High** — MPC is unable to plan beyond reactive response. The system falls
back to reactive classification only.

## Symptoms
- `mpc.suspended` audit events in Kafka
- MPC cycles showing `horizon: 1` or `suspended: true`
- `geometric_stability_profile.min` consistently below threshold
- Dashboard MPC tab showing collapsed horizon visualization

## Investigation Steps

1. **Check recent MPC cycles**
   ```sql
   SELECT cycle_id, cluster_id, horizon, suspended,
          geometric_stability_profile->'min' as min_stability,
          created_at
   FROM glx_mpc_cycles
   WHERE cluster_id = '<cluster_id>'
   ORDER BY created_at DESC LIMIT 20;
   ```

2. **Check stability trend for prediction calls**
   ```sql
   SELECT stability_score, stability_state, created_at
   FROM glx_llm_stability_records
   WHERE endpoint = 'mpc_prediction'
   ORDER BY created_at DESC LIMIT 20;
   ```

3. **Identify root cause of instability**
   - Is the LLM endpoint degraded?
   - Has the input state distribution changed significantly?
   - Is the cluster experiencing novel conditions the model hasn't seen?

## Remediation

### Automatic (already in effect)
- MPC suspends and falls back to reactive classification
- No autonomous actions taken while suspended
- Operator alerted via audit events

### Manual
- Check LLM service health
- If LLM is healthy: review input state for anomalies
- If cluster state is genuinely novel: add training data
- Consider temporarily increasing stability threshold to be more permissive

### Recovery
- MPC will automatically resume when stability scores recover
- The consecutive instability counter resets on any stable prediction
- Horizon will gradually extend back from minimum as stability sustains

## Escalation
- Suspended > 1 hour: page on-call SRE
- Multiple clusters suspended simultaneously: LLM service investigation
- Suspension correlates with model update: notify ML ops
