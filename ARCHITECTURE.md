# GeoLux Architecture

## Theoretical Foundations

These foundations are load-bearing constraints, not background context. Every component responds to a specific dimension.

### Computational Irreducibility
The behavioral state space of complex distributed infrastructure cannot be analytically predicted faster than the system itself executes.

| Consequence | Component Response |
|-------------|-------------------|
| Closed-form prediction inadequate | LLM-MPC uses receding horizons, not long-range prediction |
| Universal threshold calibration unreliable | NanoObs calibrates per-cluster via observed execution |
| Synthetic tests epistemically incomplete | Kafka replay replays real recorded events for validation |
| Long-horizon planning unsafe | MPC horizon auto-shortens when stability drops |

### Geometric State Theory
The probability manifold of an LLM has measurable geometric shape. Stable outputs produce stable geometry. Instability is physically measurable via activation variance (or fallback: logprob variance, entropy, perplexity).

**Four evaluation states:**
| State | Geometry | Output | Action |
|-------|----------|--------|--------|
| Stable Pass | Stable | Correct | Trust the result |
| Unstable Pass | Unstable | Correct | Flag for validation — fragile |
| Stable Fail | Stable | Incorrect | High confidence failure signal |
| Unstable Fail | Unstable | Incorrect | Possible artifact — investigate |

---

## Component Architecture

### 1. Geometric Stability Infrastructure
**Purpose:** Measure LLM call stability as a first-class signal.
**Files:** `api/stability/measure.py`, `api/stability/wrapper.py`
**Measurement methods:** token probability variance, logit entropy, perplexity (fallback; primary activation variance requires Gaudi/Xeon6 with vLLM).
**Integration:** `StabilityAwareLLMClient` wraps all LLM calls. Every call gets a stability score stored in `glx_llm_stability_records`.

### 2. Hypothesis Engine (THE)
**Purpose:** Replace LLM-as-decision-maker with LLM-as-hypothesis-generator.
**Files:** `engine/hypothesis.py`, `api/routers/hypothesis.py`
**Flow:** Evidence bundle → stability-aware LLM generates structured hypotheses → ranked by stability score → deterministic validation against evidence → falsification or validation.
**Governance:** Instability gate blocks generation. LLM unavailable queues stale hypotheses. All-falsified triggers rubric extension for human review.

### 3. Evidence-Based Constraint Classification
**Purpose:** Deterministic classification via formal typed constraint assertions.
**Files:** `engine/classification.py`, `constraints/loader.py`, `constraints/stages/*.yaml`
**Assertion types:** threshold, boolean, range, pattern, composite, semantic (LLM-assisted).
**Coverage:** 11 rubric stages × 2-4 constraints each = 33 constraints defined in YAML.
**Governance:** LLM used only for semantic assertions. Unstable semantic evaluation → inconclusive + human review.

### 4. LLM-MPC Controller
**Purpose:** Model Predictive Control with LLM dynamics model and receding horizon.
**Files:** `engine/mpc.py`, `api/routers/mpc.py`
**Control loop:** State model → LLM prediction → optimize → execute first action → observe → replan.
**Governance:** Activation gate requires operational history. Horizon auto-adjusts via stability. Sustained instability → suspension → reactive fallback.

### 5. Deepfield Router + NanoObs
**Purpose:** Map task complexity to hardware substrate (CPU/Xeon6/Gaudi).
**Files:** `engine/deepfield.py`, `engine/nanoobs.py`, `api/routers/deepfield.py`
**Tiers:** nano (CPU, deterministic), micro (Xeon6, structured inference), macro (Gaudi, complex reasoning).
**Governance:** Unstable classification → tier escalation for safety. Unavailable substrate → automatic fallback. Operator override requires reason. NanoObs detects threshold drift; adjustments require human approval.

### 6. Launchpad Intelligence Layer
**Purpose:** Mine provisioning data from RHDP ecosystem.
**Files:** `engine/launchpad.py`, `api/routers/launchpad.py`
**Outputs:** Demand signals, cost attribution, utilization patterns, routing intelligence.

### 7. Synthetic Client + Kafka Replay
**Purpose:** Testing without production infrastructure.
**Files:** `scenarios/*.py`, `engine/replay.py`, `api/routers/scenarios.py`
**Scenarios:** healthy-baseline, node-failure, instability-event.
**Modes:** live (real data), synthetic (generated), replay (recorded events).
**Replay:** Record real Kafka events, replay at configurable speed, pause/inspect, ground truth comparison.

### 8. Action Execution Layer
**Purpose:** Execute MPC-recommended actions with approval workflow and audit trail.
**Files:** `engine/action_executor.py`
**Gates:** Approval, confidence threshold, dry-run mode, live-mode-only.
**Audit:** Before/after state capture, action.executed Kafka event.

### 9. Supporting Infrastructure
- **Circuit breaker** (`api/stability/wrapper.py`): Opens after 5 LLM failures, 60s cooldown, auto-reset.
- **Prometheus metrics** (`api/metrics.py`): 12 metrics (HTTP, LLM, hypotheses, classifications, MPC, routing, circuit breaker). Endpoint: `GET /metrics`.
- **Kafka consumers** (`events/consumers.py`): Consumer framework with topic handlers and threading.
- **MPC objectives** (`engine/objectives.py`): Per-cluster versioned objective functions with audit trail.
- **Data retention** (`engine/retention.py`): Background job deleting records past retention (30d-365d per table).
- **Security** (`api/security.py`): SSO/OIDC, API key auth, input sanitization, audit hash chain.

---

## Development Methodology

| Layer | Tool | Purpose |
|-------|------|---------|
| **EDD** | `rubrics/*.yaml` | Evaluation rubric matrix before implementation |
| **TDD** | `tests/unit/` | Red/green cycle for all pure functions |
| **BDD** | `tests/bdd/features/` | Given/When/Then executable specifications |
| **PDD** | `tests/property/` | Invariant verification via Hypothesis |
| **CDD** | `tests/contract/` | API contract verification for all consumer/provider pairs |
| **GDD** | `api/stability/` | Geometric stability measurement at every LLM call site |

---

## Polyglot Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | Python + FastAPI | Matches Stargate; LiteLLM + ML ecosystem |
| Frontend | React + TypeScript + Tailwind | Matches Stargate dashboard |
| Database | PostgreSQL + SQLAlchemy + Alembic | Matches Stargate; shared instance |
| Events | Kafka (confluent-kafka) | Inter-service communication |
| LLM | LiteLLM → Granite (vLLM) | Model-swappable abstraction |
| Testing | pytest + Hypothesis + Behave | Full test pyramid |
| Containers | UBI9 base images | Red Hat standard |
| Deployment | Helm + OpenShift | Matches Stargate |
| Observability | OpenTelemetry + Prometheus | Standard stack |

---

## Kafka Topic Taxonomy

| Topic | Producer | Consumers |
|-------|----------|-----------|
| `evidence.collected` | Stargate collectors | THE, Classification |
| `hypothesis.generated` | THE | Classification, Event Bus |
| `classification.completed` | Classification | MPC, Deepfield, Dashboard |
| `mpc.action.recommended` | MPC | Action Execution, Dashboard |
| `deepfield.routing.decision` | Deepfield | Inference Serving, Dashboard |
| `launchpad.intelligence.updated` | Launchpad | Dashboard, Deepfield |
| `action.executed` | Action Execution | Audit Trail, Dashboard |
| `audit.event` | All components | Audit Persister, Dashboard |
| `replay.scenario` | Synthetic Client | Evidence consumers (replay mode) |

---

## PostgreSQL Schema

All tables prefixed `glx_` to avoid collision with Stargate tables.

| Table | Records | Retention |
|-------|---------|-----------|
| `glx_llm_stability_records` | Per-LLM-call stability measurement | 90 days |
| `glx_hypotheses` | Structured falsifiable hypotheses | 90 days |
| `glx_constraint_definitions` | Formal typed constraint schemas | Permanent |
| `glx_classifications` | Evidence classification results | 90 days |
| `glx_mpc_cycles` | MPC prediction and optimization traces | 90 days |
| `glx_routing_decisions` | Deepfield routing decisions | 90 days |
| `glx_nano_obs_records` | NanoObs threshold observations | 90 days |
| `glx_audit_events` | Unified audit trail (hash-chained) | 1 year |
| `glx_launchpad_intelligence` | Provisioning intelligence snapshots | 30 days |

---

## API Endpoints

| Prefix | Component | Endpoints |
|--------|-----------|-----------|
| `/stability` | Geometric Stability | GET /scores, GET/PUT /thresholds |
| `/hypotheses` | THE | POST /generate, GET /queue, GET /{id}, POST /{id}/validate |
| `/classify` | Classification | POST /, GET /constraints, GET /classifications/{id} |
| `/mpc` | LLM-MPC | POST /plan, GET /cycles, GET /cycles/{id} |
| `/deepfield` | Deepfield | POST /route, GET /tiers, GET /routing-history |
| `/launchpad` | Launchpad | GET /intelligence, /demand, /cost, /utilization |
| `/scenarios` | Synthetic Client | GET /list, POST /run, POST /replay/start, /replay/pause |
| `/health` | System | GET /health |
| `/mode` | System | GET /mode, PUT /mode |
| `/metrics` | Observability | GET /metrics (Prometheus) |

All specs in `contracts/openapi/*.yaml` (OpenAPI 3.1) and `contracts/asyncapi/*.yaml` (AsyncAPI 2.6).

**Production deployment:** https://geolux.apps.ocpv-infra01.dal12.infra.demo.redhat.com

---

## Test Coverage

| Category | Count | Framework |
|----------|-------|-----------|
| Unit tests | 156 | pytest |
| Integration tests | 105 | pytest + SQLite |
| Property tests | 40 | Hypothesis |
| Contract tests | 35 | pytest (CDD) |
| BDD scenarios | 41 | Behave |
| Frontend tests | 3 | Vitest |
| **Total** | **380** | **0 failures** |
