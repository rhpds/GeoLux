# K8s Effector Implementation Spec

## Summary

GeoLux's intelligence layer (hypothesis, classification, MPC, Deepfield routing) makes real LLM calls. The action executor's gate harness (mode/dry-run/confidence gates, audit trail, Kafka events) is fully functional. This spec wired the effectors to real K8s operations.

## Pattern

Follows StarGate's proven approach:
- **subprocess calls to `oc` CLI** — not the Python kubernetes client
- **Separate executor ServiceAccount** — namespace-scoped RBAC, disabled by default
- **Rollback via JSON state snapshots** — capture before, restore on failure

## Components

### `engine/k8s_client.py`

Thin wrapper around `oc` subprocess calls. Functions: `run_oc`, `validate_kubeconfig`, `get_deployment`, `scale_deployment`, `delete_pod`, `rollout_restart`, `capture_namespace_state`, `apply_state`.

### `engine/action_executor.py`

`_execute_action()` routes to real `oc` commands:
- `scale_replicas` → `k8s_client.scale_deployment()`
- `execute_remediation` → `k8s_client.rollout_restart()` or `k8s_client.delete_pod()`
- `no_action` → returns success (unchanged)

`_capture_state()` reads real cluster state via `k8s_client.capture_namespace_state()`. Falls back to parameter echo when no kubeconfig is available.

Rollback: on execution failure, `k8s_client.apply_state(before_state)` restores pre-execution resources.

### `deploy/helm/geolux-executor-sa/`

Namespace-scoped Role: pods (get/list/delete), deployments (get/list/patch/update/create/scale), services/configmaps/events (get/list). Disabled by default (`executor.enabled: false`).

## Safety Model

1. Executor disabled by default in Helm
2. Namespace-scoped RBAC (not ClusterRole)
3. Existing gates: dry-run, mode, confidence, stability threshold (now auth-protected)
4. Kubeconfig validated before every operation
5. Rollback on failure
6. MPC auto-planning stays disabled until validated

## Environment Variables

- `GEOLUX_EXECUTOR_KUBECONFIG` — path to executor kubeconfig
- `GEOLUX_EXECUTOR_NAMESPACE` — default namespace for execution
