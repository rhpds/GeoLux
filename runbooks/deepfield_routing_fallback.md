# Runbook: Deepfield Routing Fallback

## Trigger
Target substrate tier is unavailable or unhealthy, forcing the Deepfield Router
to fall back to a lower-priority tier for workload placement.

## Severity
**Medium** — Workloads continue to execute on a fallback tier but may
experience degraded throughput or higher latency.

## Symptoms
- `deepfield.routing.fallback` audit events in Kafka
- RouteResponse records showing `fallback_used: true`
- NanoObs traces with elevated latency on fallback substrate
- Dashboard Deepfield tab showing amber/red health for one or more tiers
- Increased `routing.fallback.count` metric in monitoring

## Investigation Steps

1. **Check substrate health**
   ```bash
   curl -s https://<gaudi-endpoint>/healthz
   curl -s https://<xeon6-endpoint>/healthz
   ```

2. **Check recent routing decisions for fallback activity**
   ```sql
   SELECT routing_id, workload_id, selected_tier, fallback_used,
          fallback_chain, geometric_stability_score, created_at
   FROM glx_deepfield_routing_decisions
   WHERE fallback_used = true
   ORDER BY created_at DESC LIMIT 20;
   ```

3. **Check Gaudi substrate health**
   ```sql
   SELECT tier_name, healthy, capacity_remaining_pct, updated_at
   FROM glx_deepfield_tiers
   WHERE substrate_type = 'gaudi'
   ORDER BY priority;
   ```

4. **Check Xeon6 substrate health**
   ```sql
   SELECT tier_name, healthy, capacity_remaining_pct, updated_at
   FROM glx_deepfield_tiers
   WHERE substrate_type = 'xeon6'
   ORDER BY priority;
   ```

5. **Identify root cause**
   - Is the substrate endpoint unreachable (network/DNS)?
   - Is the substrate overloaded (capacity_remaining_pct near 0)?
   - Has a recent deployment changed endpoint configuration?
   - Are NanoObs traces showing timeouts on the primary tier?

## Remediation

### Automatic (already in effect)
- Router falls back to the next-priority tier in the tier chain
- Fallback chain is recorded in RouteResponse for audit
- NanoObs continues tracing on the fallback substrate
- `deepfield.routing.fallback` event published to Kafka

### Manual
- **Verify substrate URLs**: confirm endpoints in tier definitions match live infrastructure
- **Restart unhealthy substrate**: if the substrate process is down, restart the service
- **Scale substrate capacity**: if capacity is exhausted, add nodes or increase quotas
- **Manual tier override**: force routing to a specific tier via the `preferred_tier` field
  ```bash
  curl -X POST /deepfield/route \
    -d '{"workload_id":"...","workload_type":"inference","compute_profile":{...},"preferred_tier":"xeon6-backup"}'
  ```
- **Temporarily disable unhealthy tier**: mark the tier as unhealthy to prevent retry churn
  ```sql
  UPDATE glx_deepfield_tiers SET healthy = false WHERE tier_name = '<tier>';
  ```

### Recovery
- Router automatically re-includes a tier when its health check returns healthy
- Fallback routing ceases once the primary tier recovers
- NanoObs trace latency should return to baseline after recovery

## Escalation
- Fallback active > 30 minutes: page on-call SRE
- All tiers unhealthy (503 responses): escalate to infrastructure team immediately
- Fallback correlates with substrate deployment: notify platform ops
- Geometric stability degradation during fallback: notify ML ops
