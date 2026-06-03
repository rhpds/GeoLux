# Specification by Example

Concrete input/output examples for every GeoLux component. Each table is an executable specification: given the Input, the system must produce the Expected Output.

---

## 1. Geometric Stability

Stability measurement converts raw LLM output signals (logprobs, entropy, perplexity) into a score and a four-state classification.

### Score Calculation

| Input (logprobs array) | Stability Method | Expected Score | Rationale |
|---|---|---|---|
| `[-0.01, -0.02, -0.01, -0.02, -0.01]` | `token_probability` | 0.95 | Low variance, high token confidence |
| `[-0.5, -1.2, -0.3, -2.1, -0.8]` | `token_probability` | 0.42 | High variance across tokens |
| `[-0.1, -0.1, -0.1, -0.1, -0.1]` | `token_probability` | 0.99 | Near-zero variance (deterministic) |
| `[-3.0, -3.5, -4.0, -3.2, -3.8]` | `perplexity` | 0.35 | Consistently low confidence tokens |

### State Classification

Threshold = 0.7 (default `GEOLUX_STABILITY_THRESHOLD`). "Pass" = LLM output matched expected schema/format.

| Stability Score | Output Valid | Expected State | Action |
|---|---|---|---|
| 0.95 | Yes | `stable_pass` | Trust the result |
| 0.55 | Yes | `unstable_pass` | Flag for validation -- fragile |
| 0.85 | No | `stable_fail` | High-confidence failure signal |
| 0.40 | No | `unstable_fail` | Possible artifact -- investigate |

### Full Example Record

| Field | Value |
|---|---|
| `call_id` | `"call-abc-001"` |
| `endpoint` | `"hypothesis_generation"` |
| `model` | `"granite-3.1-8b"` |
| `stability_score` | `0.88` |
| `stability_method` | `token_probability` |
| `stability_threshold` | `0.7` |
| `stability_state` | `stable_pass` |
| `raw_signal` | `{"logprobs": [-0.05, -0.03, -0.04, -0.06, -0.02]}` |

---

## 2. Hypothesis Engine (THE)

### Evidence Bundle Input

```json
{
  "bundle_id": "bundle-cluster7-20260601",
  "evidence_fields": {
    "cpu_utilization": 0.92,
    "memory_pressure": 0.78,
    "pod_restart_count": 14,
    "error_rate": 0.05,
    "namespace": "demo-prod",
    "cluster_id": "cluster-7"
  }
}
```

### Expected Hypothesis Output (ranked by stability score)

| # | Claim | Testable Conditions | Confidence | Stability Score | Stability State |
|---|---|---|---|---|---|
| 1 | "High CPU utilization is caused by pod restart loops consuming resources" | `[{"field": "pod_restart_count", "operator": "gt", "value": 10}, {"field": "cpu_utilization", "operator": "gt", "value": 0.85}]` | 0.82 | 0.91 | `stable_pass` |
| 2 | "Memory pressure exceeding 0.75 is driving OOM kills and pod restarts" | `[{"field": "memory_pressure", "operator": "gt", "value": 0.75}, {"field": "pod_restart_count", "operator": "gt", "value": 5}]` | 0.75 | 0.91 | `stable_pass` |

### Validation Examples

Validation is deterministic against evidence. The LLM's confidence is irrelevant.

| Hypothesis Claim | Testable Conditions | Evidence | Expected Outcome |
|---|---|---|---|
| "CPU is over 85%" | `[{"field": "cpu_utilization", "operator": "gt", "value": 0.85}]` | `{"cpu_utilization": 0.92}` | `validated` |
| "Error rate exceeds 10%" | `[{"field": "error_rate", "operator": "gt", "value": 0.10}]` | `{"error_rate": 0.05}` | `falsified` |
| "Pod restart count is elevated" | `[{"field": "pod_restart_count", "operator": "gt", "value": 10}]` | `{}` (field missing) | `inconclusive` |
| "Memory is normal" | `[{"field": "memory_pressure", "operator": "lt", "value": 0.5}]` | `{"memory_pressure": 0.78}` | `falsified` |

### Governance Scenarios

| Scenario | Stability Score | LLM Available | Expected Behavior |
|---|---|---|---|
| Normal generation | 0.88 | Yes | Generate and rank hypotheses |
| Instability gate | 0.45 | Yes | Block generation, log stability breach, return `gated: true` |
| LLM unavailable | N/A | No | Return last known hypotheses with `stale: true` |
| All falsified | N/A | N/A | Trigger `rubric.extension.triggered` audit event for human review |

---

## 3. Evidence-Based Constraint Classification

### Threshold Assertion

| Evidence | Constraint Definition | Expected Result |
|---|---|---|
| `{"cpu_utilization": 0.92}` | `{"type": "threshold", "field": "cpu_utilization", "operator": "lte", "value": 0.90}` | `fail` (0.92 > 0.90) |
| `{"cpu_utilization": 0.85}` | `{"type": "threshold", "field": "cpu_utilization", "operator": "lte", "value": 0.90}` | `pass` (0.85 <= 0.90) |

### Boolean Assertion

| Evidence | Constraint Definition | Expected Result |
|---|---|---|
| `{"tls_enabled": true}` | `{"type": "boolean", "field": "tls_enabled", "value": true}` | `pass` |
| `{"tls_enabled": false}` | `{"type": "boolean", "field": "tls_enabled", "value": true}` | `fail` |

### Range Assertion

| Evidence | Constraint Definition | Expected Result |
|---|---|---|
| `{"replica_count": 3}` | `{"type": "range", "field": "replica_count", "min": 2, "max": 10}` | `pass` (3 in [2, 10]) |
| `{"replica_count": 1}` | `{"type": "range", "field": "replica_count", "min": 2, "max": 10}` | `fail` (1 < 2) |

### Pattern Assertion

| Evidence | Constraint Definition | Expected Result |
|---|---|---|
| `{"image_tag": "v2.3.1-ubi9"}` | `{"type": "pattern", "field": "image_tag", "pattern": ".*-ubi9$"}` | `pass` |
| `{"image_tag": "v2.3.1-alpine"}` | `{"type": "pattern", "field": "image_tag", "pattern": ".*-ubi9$"}` | `fail` |

### Composite Assertion

| Evidence | Constraint Definition | Expected Result |
|---|---|---|
| `{"cpu_utilization": 0.60, "memory_pressure": 0.40}` | `{"type": "composite", "logic": "all", "assertions": [{"type": "threshold", "field": "cpu_utilization", "operator": "lte", "value": 0.90}, {"type": "threshold", "field": "memory_pressure", "operator": "lte", "value": 0.75}]}` | `pass` (both pass) |
| `{"cpu_utilization": 0.60, "memory_pressure": 0.85}` | Same as above | `fail` (memory exceeds 0.75) |

### Semantic Assertion (LLM-assisted)

| Evidence | Constraint Definition | Stability State | Expected Result |
|---|---|---|---|
| `{"error_log": "OOMKilled in pod-xyz"}` | `{"type": "semantic", "field": "error_log", "question": "Does this log indicate a memory exhaustion event?"}` | `stable_pass` | `pass` or `fail` (per LLM) |
| `{"error_log": "OOMKilled in pod-xyz"}` | Same as above | `unstable_pass` | `inconclusive` (unstable LLM -- requires human review) |

### Missing Evidence

| Evidence | Constraint (requires `cpu_utilization`) | Expected Result |
|---|---|---|
| `{"memory_pressure": 0.40}` | `{"type": "threshold", "field": "cpu_utilization", "operator": "lte", "value": 0.90}` | `inconclusive` (missing required field) |

### Overall Result Determination

| Individual Results | Expected Overall |
|---|---|
| `[pass, pass, pass]` | `pass` |
| `[pass, fail, pass]` | `fail` |
| `[pass, inconclusive, pass]` | `inconclusive` |
| `[pass, unclassifiable, pass]` | `unclassifiable` |

---

## 4. LLM-MPC Controller

### Planning Cycle

**Input:**

```json
{
  "cluster_id": "cluster-7",
  "current_state": {
    "cpu_utilization": 0.88,
    "memory_pressure": 0.72,
    "active_pods": 12,
    "error_rate": 0.03
  },
  "horizon": 3,
  "objective": {"type": "scale", "target": 5}
}
```

**Expected Output (stable, activated):**

| Field | Expected Value |
|---|---|
| `cluster_id` | `"cluster-7"` |
| `horizon` | 3 (or adjusted if stability drops) |
| `predictions` | Array of 3 step predictions with `predicted_state` and `confidence` |
| `recommended_action` | `{"action_type": "scale_replicas", "parameters": {"target_replicas": 5}}` |
| `suspended` | `false` |
| `horizon_adjusted` | `false` (if stability stays above threshold) |

### Horizon Auto-Adjustment

| Stability Scores | Current Horizon | Expected Adjusted Horizon | Reason |
|---|---|---|---|
| `[0.85, 0.90, 0.88]` | 3 | 3 | Stable, no change needed |
| `[0.65, 0.70, 0.55]` | 3 | 2 | Min stability (0.55) below threshold (0.7) |
| `[0.85, 0.88, 0.90]` | 2 | 3 | Sustained stability above threshold + 0.1, extend |
| `[0.40]` | 3 | 2 | Single unstable prediction, shorten |

### Activation Gate

| Cluster History | Min History Weeks | Expected Result |
|---|---|---|
| 15 classification records in last 4 weeks | 4 | Activated (>= 10 records) |
| 5 classification records in last 4 weeks | 4 | Blocked ("insufficient operational history") |
| 0 classification records | 4 | Blocked |

### Suspension

| Consecutive Instabilities | Threshold | Expected State |
|---|---|---|
| 1 | 3 | Active |
| 2 | 3 | Active |
| 3 | 3 | Suspended -- falls back to reactive |

---

## 5. Deepfield Router

### Rule-Based Classification (fallback)

| Workload Description | Expected Tier | Expected Substrate | Policy Rule |
|---|---|---|---|
| `{"task_type": "boolean_check", "reasoning_required": false, "multi_step": false, "novel": false, "context_length": 256}` | `nano` | `cpu` | `complexity_nano` |
| `{"task_type": "pattern_analysis", "reasoning_required": true, "multi_step": false, "novel": false, "context_length": 2048}` | `micro` | `xeon6` | `complexity_micro` |
| `{"task_type": "root_cause_analysis", "reasoning_required": true, "multi_step": true, "novel": true, "context_length": 8192}` | `macro` | `gaudi` | `complexity_macro` |

### Instability Escalation

| Original Tier (from rules) | Stability State | Expected Tier | Policy Rule |
|---|---|---|---|
| `nano` | `unstable_pass` | `micro` | `unstable_complexity_nano` (escalated for safety) |
| `micro` | `unstable_fail` | `macro` | `unstable_complexity_micro` (escalated for safety) |
| `macro` | `unstable_pass` | `macro` | `unstable_complexity_macro` (already highest tier) |

### Substrate Fallback

| Target Substrate | Available | Expected Fallback Tier | Expected Fallback Substrate |
|---|---|---|---|
| `gaudi` | No (`GEOLUX_GAUDI_URL` unset) | `nano` | `cpu` |
| `xeon6` | No (`GEOLUX_XEON6_URL` unset) | `macro` | `gaudi` (if available), else `nano`/`cpu` |
| `cpu` | Always | N/A | No fallback needed |

### Operator Override

| Override Input | Expected Behavior |
|---|---|
| `{"override_tier": "macro", "override_reason": "Critical investigation", "override_operator": "jsmith"}` | Route to `macro`/`gaudi`, `override: true`, `policy_rule: "operator_override"` |
| `{"override_tier": "nano"}` (no reason) | Error: `"override_reason required for manual routing"` |

---

## 6. Launchpad Intelligence

### Demand Signals

**Input:**

```json
{
  "sessions": [
    {"demo_id": "openshift-ai", "partner_id": "partner-1", "status": "success", "config": "gaudi-4node"},
    {"demo_id": "openshift-ai", "partner_id": "partner-1", "status": "success", "config": "gaudi-4node"},
    {"demo_id": "openshift-ai", "partner_id": "partner-2", "status": "failed", "config": "xeon6-2node"},
    {"demo_id": "ansible-ee", "partner_id": "partner-3", "status": "success", "config": "cpu-1node"},
    {"demo_id": "ansible-ee", "partner_id": "partner-2", "status": "failed", "config": "xeon6-2node"}
  ],
  "labs": [
    {"lab_code": "LAB-001"},
    {"lab_code": "LAB-002"}
  ]
}
```

**Expected Output:**

| Signal | Expected Value |
|---|---|
| `most_requested_demos` | `[{"demo_id": "openshift-ai", "count": 3}, {"demo_id": "ansible-ee", "count": 2}]` |
| `highest_failure_configs` | `[{"config": "xeon6-2node", "count": 2}]` |
| `returning_partners` | `["partner-1", "partner-2"]` (> 1 session each) |
| `new_partners` | `["partner-3"]` (exactly 1 session) |
| `total_sessions` | `5` |
| `total_labs` | `2` |

### Cost Attribution

**Input:**

```json
{
  "sessions": [
    {"lab_code": "LAB-001", "sa_id": "sa-west", "partner_id": "partner-1", "hardware_config": "gaudi-4node", "cost": 120.50},
    {"lab_code": "LAB-001", "sa_id": "sa-west", "partner_id": "partner-2", "hardware_config": "gaudi-4node", "cost": 115.00},
    {"lab_code": "LAB-002", "sa_id": "sa-east", "partner_id": "partner-3", "hardware_config": "cpu-1node", "cost": 8.75}
  ]
}
```

**Expected Output:**

| Dimension | Expected Top Entry |
|---|---|
| `per_lab_session` | `{"lab_code": "LAB-001", "total_cost": 235.50}` |
| `per_sa` | `{"sa_id": "sa-west", "total_cost": 235.50}` |
| `per_partner` | `{"partner_id": "partner-1", "total_cost": 120.50}` |
| `per_hardware_config` | `{"config": "gaudi-4node", "total_cost": 235.50}` |
| `total_cost` | `244.25` |

### Utilization Patterns

**Input:**

```json
{
  "sessions": [
    {"started_at": "2026-06-01T09:00:00Z", "hardware_config": "gaudi-4node"},
    {"started_at": "2026-06-01T09:30:00Z", "hardware_config": "gaudi-4node"},
    {"started_at": "2026-06-01T14:00:00Z", "hardware_config": "xeon6-2node"},
    {"started_at": "2026-06-01T14:15:00Z", "hardware_config": "cpu-1node"}
  ],
  "capacity": {
    "total_hours": 168,
    "configurations": ["gaudi-4node", "xeon6-2node", "cpu-1node", "gaudi-8node"]
  }
}
```

**Expected Output:**

| Signal | Expected Value |
|---|---|
| `peak_demand_windows` | `[{"hour": 9, "count": 2}, {"hour": 14, "count": 2}]` |
| `underutilized_configs` | `["gaudi-8node"]` (present in capacity but never used) |
| `active_hours` | `2` (hours 9 and 14) |
| `idle_time_hours` | `166` (168 - 2) |
