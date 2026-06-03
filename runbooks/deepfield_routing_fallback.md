# Runbook: Deepfield Routing Fallback

## Trigger
Target substrate is unavailable, forcing the Deepfield Router to fall back
to a lower tier or CPU for workload placement.

## Severity
**Medium** -- Workloads continue on fallback substrate but may experience
degraded throughput or higher latency.

## Symptoms
- Routing decisions showing `policy_rule_applied` starting with `fallback_from_`
- Audit events with `deepfield.routing.started` but tier different from LLM classification
- Dashboard Hardware tab showing routing to unexpected tiers
- Substrate environment variables (`GEOLUX_GAUDI_URL`, `GEOLUX_XEON6_URL`) empty or unreachable

## Investigation Steps

1. **Check substrate availability**
   ```bash
   curl -s $GEOLUX_GAUDI_URL/health
   curl -s $GEOLUX_XEON6_URL/health
   ```

2. **Check recent routing decisions for fallback activity**
   ```sql
   SELECT routing_id, workload_id, tier_assignment, substrate,
          policy_rule_applied, confidence_score, created_at
   FROM glx_routing_decisions
   WHERE policy_rule_applied LIKE 'fallback_%'
   ORDER BY created_at DESC LIMIT 20;
   ```

3. **Check substrate URL configuration**
   ```bash
   oc get configmap geolux-config -o yaml | grep -i gaudi
   oc get configmap geolux-config -o yaml | grep -i xeon
   ```

4. **Check routing distribution**
   ```sql
   SELECT tier_assignment, substrate, COUNT(*)
   FROM glx_routing_decisions
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY tier_assignment, substrate;
   ```

5. **Identify root cause**
   - Is the substrate endpoint unreachable (network/DNS)?
   - Are environment variables set correctly?
   - Has a deployment changed endpoint configuration?

## Remediation

### Automatic (already in effect)
- Router falls back: macro→micro→nano (TIER_ESCALATION chain)
- If escalated tier also unavailable, falls back to nano/CPU
- CPU substrate is always available (no external dependency)
- Routing decision logged with `fallback_from_*` policy rule
- Audit event published to Kafka

### Manual
- **Verify substrate URLs**: check `GEOLUX_GAUDI_URL` and `GEOLUX_XEON6_URL` in configmap
- **Restart unhealthy substrate**: if the inference server is down, restart it
- **Manual override**: route to specific tier with reason
  ```bash
  curl -X POST /deepfield/route \
    -H "Content-Type: application/json" \
    -d '{"workload_id":"...","workload_description":{...},"override_tier":"micro","override_reason":"gaudi maintenance","override_operator":"admin@redhat.com"}'
  ```
- **Suspend adaptive routing**: if LLM classification is also unstable, the router
  automatically falls back to static rule-based classification

### Recovery
- Set the substrate URL environment variable and restart the pod
- Router will automatically use the substrate once available
- Verify with: `curl $GEOLUX_GAUDI_URL/health`

## Escalation
- Fallback active > 30 minutes: page on-call SRE
- All substrates unavailable (only CPU): escalate to infrastructure team
- Fallback correlates with substrate deployment: notify platform ops
