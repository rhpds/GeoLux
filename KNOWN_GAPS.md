# Known Gaps and Future Work

Spec deliverable #7. This document tracks capabilities that are specified but not yet implemented, areas requiring additional research, and planned future phases.

---

## Specified but Deferred

### Rust Nano Agents

**Status:** Interface defined, Python implementation in place.

The nano tier (`engine/deepfield.py`) routes deterministic boolean-check workloads to CPU. The spec defines a Rust implementation for nano agents to achieve sub-millisecond evaluation latency and minimal memory footprint. The Python `DeepfieldRouter` and rule-based classification serve as the current implementation. The Rust agent interface is defined in `contracts/` but no Rust code exists yet. Migration path: implement the Rust agent behind the same API contract, swap at the routing layer.

### Go Kubernetes Operators

**Status:** Deferred to deployment phase.

The MPC controller (`engine/mpc.py`) outputs recommended actions. In the target architecture, a Go-based Kubernetes operator watches for `mpc.action.recommended` events on the Kafka topic and executes them as cluster operations (scaling, remediation, rollouts). Currently, action execution is handled by `engine/action_executor.py` as a Python stub. The operator spec (CRD definitions, reconciliation logic, RBAC) is documented but no Go code exists. This is intentionally deferred until the OpenShift deployment phase when cluster-level permissions and operator lifecycle management can be validated in situ.

### Agentic Coding Extension

**Status:** Promotion gate spec in runbook, no code.

The runbooks (`runbooks/`) define a promotion gate workflow where agentic coding tools (Claude Code, Cursor, etc.) must pass GeoLux's constraint classification before code changes are promoted. The gate spec defines the API contract (POST evidence bundle, receive pass/fail/inconclusive), required constraints (test coverage threshold, security scan pass, stability score minimum), and the escalation path for inconclusive results. No extension code, IDE plugin, or CI integration exists yet.

### Activation Variance Measurement

**Status:** Requires Gaudi/Xeon6 with vLLM.

The primary geometric stability measurement method is activation variance -- measuring the variance of internal model activations across token positions. This requires direct access to model internals via vLLM running on Intel Gaudi or Xeon6 hardware. The current implementation (`api/stability/`) falls back to token probability variance, logit entropy, and perplexity, which are measurable from standard API responses. Activation variance will be enabled when the Gaudi/Xeon6 vLLM deployment is available; the `StabilityMethod.ACTIVATION_VARIANCE` enum and database column are already in place.

---

## Requires Additional Research

### Geometric Stability Calibration

**Open question:** What threshold values work best in practice?

The current default threshold is 0.7 (`GEOLUX_STABILITY_THRESHOLD`). This value was chosen as a reasonable starting point but has not been validated against production workloads. Research needed:

- What stability scores does Granite 3.1 8B produce under normal inference on infrastructure evidence?
- Does the optimal threshold vary by endpoint (hypothesis generation vs. semantic classification vs. MPC prediction)?
- Should per-endpoint thresholds replace the single global threshold?
- How does threshold interact with temperature and max_tokens settings?

### MPC Objective Function Definition

**Open question:** Per-cluster calibration methodology.

The MPC controller (`engine/mpc.py`) optimizes candidate actions against an objective, but the objective function itself is passed in by the caller. Research needed:

- What objective functions produce good outcomes across different cluster types (dev, staging, production)?
- How should objectives be calibrated per-cluster based on operational history?
- Should objective weights be learned from historical MPC cycle outcomes?
- What is the right balance between resource efficiency and stability preservation?

### Cross-Cluster Pattern Detection

**Open question:** Macro tier use case.

The Deepfield router sends complex reasoning tasks to the macro tier (Gaudi). One planned macro-tier use case is cross-cluster pattern detection: identifying correlated failures, cascading issues, or systemic patterns across multiple clusters. Research needed:

- What context length is required to represent multi-cluster state simultaneously?
- Can cross-cluster patterns be detected incrementally (per-cluster summary then aggregation) or does it require full joint context?
- What patterns are actually actionable vs. merely interesting?
- How does cross-cluster detection interact with the MPC controller's per-cluster planning?

---

## Future Phases

### PatternFly 6 Migration

**Current state:** Tailwind CSS matching Stargate visual style.

The frontend (`frontend/`) uses React + TypeScript + Tailwind CSS to match the existing Stargate dashboard aesthetic. The target state is PatternFly 6 (Red Hat's design system) for full visual and behavioral consistency with other Red Hat internal tools. This migration is deferred because PatternFly 6 was not yet stable when development began. Migration path: replace Tailwind utility classes with PatternFly components, adopt PatternFly layout patterns, integrate PatternFly charts for dashboard visualizations.

### Multi-Region Deployment

**Current state:** Single-region OpenShift deployment.

The architecture assumes a single OpenShift cluster. Future work includes:

- Multi-region Kafka topic replication for cross-region event propagation
- Region-aware Deepfield routing (route to nearest available substrate)
- Cross-region MPC coordination (how do per-cluster controllers interact across regions?)
- Launchpad intelligence aggregation across regions

### Blue-Green Deployments

**Current state:** Rolling updates via Helm.

The deployment configuration (`deploy/`, `podman-compose.yaml`) supports rolling updates. Blue-green deployment would enable:

- Zero-downtime schema migrations (Alembic migrations against the inactive database)
- Canary validation of new constraint definitions before full rollout
- Safe rollback if MPC behavior degrades after an update
- A/B testing of stability threshold changes

### HA PostgreSQL

**Current state:** Single PostgreSQL instance, separate credentials.

All GeoLux tables (`glx_*`) live in the shared Stargate PostgreSQL instance. Credentials are now isolated (`GEOLUX_DATABASE_URL`), but both services use the same superuser role. Future work:

- Streaming replication for read replicas (dashboard queries against replica)
- Automatic failover for the primary instance
- Connection pooling (PgBouncer) for high-concurrency MPC and classification workloads
- Evaluate whether audit events (`glx_audit_events`, 365-day retention) should move to a separate instance to avoid bloating the primary

---

## Security Hardening (applied 2026-06-19)

### Cross-Platform Credential Isolation

All `STARGATE_*` environment variable fallbacks have been removed. GeoLux previously fell back to StarGate's admin API key, database URL, LiteLLM credentials, Kafka brokers, and CORS origins — meaning one leaked key was admin on both platforms, and a bad GeoLux migration could reach StarGate's live-cluster executor. Each platform now requires its own `GEOLUX_*` environment variables with no cross-product secret chain.

### Stability Threshold Endpoint Authentication

`PUT /stability/thresholds` now requires admin authentication. Previously unauthenticated — anyone could set the threshold to 0.0 and disable stability gating on all LLM calls (hypothesis generation, classification, MPC), or to 1.0 to suspend all operations.

### Internal Hostname Exposure

All hardcoded `.infra.demo.redhat.com` URLs removed from source code, docs, and rubrics. The live deployment URL was in README.md, ARCHITECTURE.md, INTEGRATION_MAP.md, and engine/catalog_miner.py.

### Remaining Security Items

- **SSL verification disabled in catalog_miner.py** — `ssl.CERT_NONE` when fetching Launchpad catalog. Vulnerable to MITM on internal network. Fix when internal CA chain is available.
- **API key scope** — `is_admin` returns `True` for any valid API key regardless of origin. Future work: scoped keys with per-endpoint permissions.
- **Shared PostgreSQL** — GeoLux `glx_*` tables still coexist with StarGate tables in the same database instance. Credentials are now separate, but a non-superuser DB role per service would further contain blast radius.

---

## Resolved Gaps

The following were identified as gaps during development and have been closed:

| Gap | Resolution |
|-----|-----------|
| AsyncAPI specs | 9 AsyncAPI 2.6 specs in `contracts/asyncapi/` |
| Kafka consumers | Consumer framework in `events/consumers.py` |
| Action execution layer | `engine/action_executor.py` with gates and audit |
| Kafka replay engine | Full implementation in `engine/replay.py` |
| Circuit breaker | `CircuitBreaker` class in `api/stability/wrapper.py` |
| Prometheus metrics | 12 metrics in `api/metrics.py`, endpoint at `/metrics` |
| Data retention job | `engine/retention.py` with per-table policies |
| MPC objectives | Versioned per-cluster objectives in `engine/objectives.py` |
| NanoObs → THE feedback | Drift detection feeds hypothesis generation |
| SBE documentation | `docs/SBE.md` with concrete examples |
| Pre-commit hooks | `.pre-commit-config.yaml` with secret detection |
| Playwright config | `frontend/playwright.config.ts` |
| SQLAlchemy enum fix | `values_callable` on all Enum columns for PostgreSQL compatibility |
| Cross-platform secret fallbacks | All `STARGATE_*` fallbacks removed; each platform owns its credentials |
| Stability threshold auth | `PUT /stability/thresholds` requires admin authentication |
| Internal hostname exposure | All `.infra.demo.redhat.com` URLs replaced with env var references |
| MPC auto-planning disabled | Kept disabled until Go operator and remediation actions exist |
