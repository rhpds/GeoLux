# GeoLux -- Governed Agentic Inference Platform

Extension of the Stargate platform for Red Hat Intel AI Platform. GeoLux adds geometric stability analysis, hypothesis-driven reasoning, constraint classification, model predictive control, and Deepfield routing to govern agentic inference workloads.

**Live deployment:** https://geolux.apps.ocpv-infra01.dal12.infra.demo.redhat.com

---

## Architecture overview

GeoLux is a full-stack application with a Python/FastAPI backend and a React/TypeScript frontend, backed by PostgreSQL (shared with Stargate; all tables prefixed `glx_`).

The backend is organized around 11 engine modules that implement the core inference governance logic: `hypothesis`, `classification`, `mpc`, `deepfield`, `nanoobs`, `launchpad`, `replay`, `action_executor`, `objectives`, `retention`, and a `stability` wrapper. Eight FastAPI routers expose these engines as REST endpoints.

The frontend provides 8 pages: Overview, Hypotheses, Classification, MPC, Hardware, Launchpad, Stability, and Admin.

For a detailed component diagram and data-flow description, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Quick start

```bash
# Install Python and Node dependencies
make install

# Start API + frontend + PostgreSQL (podman-compose)
make dev

# Run the full test suite (380 checks)
make test
```

Prerequisites: Python 3.11+, Node 20+, podman-compose (or Docker Compose).

---

## Project structure

```
api/            FastAPI application, routers, security, metrics
engine/         11 inference engine modules (hypothesis, MPC, deepfield, etc.)
frontend/       React 19 / TypeScript / Vite / Tailwind v4 SPA
db/             SQLAlchemy models and database utilities
alembic/        Database migration scripts
deploy/         Helm chart (10 templates) and Tekton CI/CD pipelines
tests/          pytest unit/integration/property tests and BDD scenarios
scenarios/      Synthetic client scenario definitions
contracts/      Consumer-driven contract tests
constraints/    Constraint definitions for classification engine
rubrics/        Scoring rubrics for hypothesis validation
runbooks/       Operational runbooks
docs/           Supplementary documentation (SBE spec)
prompts/        Prompt templates for agentic inference
events/         Event schema definitions
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check and readiness probe |
| GET | `/mode` | Current operating mode |
| PUT | `/mode` | Switch operating mode |
| GET | `/metrics` | Prometheus-format metrics |
| POST | `/hypotheses/generate` | Generate new hypotheses |
| GET | `/hypotheses/queue` | List queued hypotheses |
| GET | `/hypotheses/{id}` | Retrieve a hypothesis |
| POST | `/hypotheses/{id}/validate` | Validate a hypothesis |
| POST | `/classify` | Classify constraints |
| GET | `/classify/constraints` | List constraint definitions |
| GET | `/classify/classifications/{id}` | Retrieve a classification |
| POST | `/mpc/plan` | Generate an MPC control plan |
| GET | `/mpc/cycles` | List MPC cycles |
| GET | `/mpc/cycles/{id}` | Retrieve a specific cycle |
| POST | `/deepfield/route` | Route a request via Deepfield |
| GET | `/deepfield/tiers` | List routing tiers |
| GET | `/deepfield/routing-history` | Query routing history |
| GET | `/launchpad/intelligence` | Launchpad intelligence summary |
| GET | `/launchpad/demand` | Current demand metrics |
| GET | `/launchpad/cost` | Cost analysis |
| GET | `/launchpad/utilization` | Resource utilization |
| GET | `/stability/scores` | Geometric stability scores |
| GET | `/stability/thresholds` | Current stability thresholds |
| PUT | `/stability/thresholds` | Update stability thresholds |
| GET | `/scenarios/list` | List available scenarios |
| POST | `/scenarios/run` | Execute a scenario |
| POST | `/scenarios/replay/start` | Start scenario replay |
| POST | `/scenarios/replay/pause` | Pause scenario replay |

Interactive docs available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## Configuration

Copy the example environment file and edit as needed:

```bash
cp .env.example .env
```

See [.env.example](.env.example) for all available variables including database connection, CORS origins, rate-limit settings, and engine tuning parameters.

---

## Deployment

GeoLux deploys to OpenShift via Helm. The chart includes 10 templates (deployment, service, route, configmap, secrets, HPA, PDB, network policy, service account, migration job).

```bash
# Render templates for dev
make helm-template-dev

# Render templates for prod
make helm-template-prod
```

CI/CD is handled by Tekton pipelines in `deploy/tekton/`.

For local development, `make dev` uses `podman-compose.yaml` to start the API, frontend dev server, and PostgreSQL.

See the [deploy/](deploy/) directory for full chart and pipeline definitions.

---

## Testing

```bash
make test              # Run all 380 checks
make test-unit         # pytest unit tests
make test-integration  # pytest integration tests
make test-property     # pytest property-based tests
make test-contract     # Consumer-driven contract tests
make test-bdd          # BDD scenario tests (41 scenarios)
make test-frontend     # Vitest frontend tests (3 suites)
```

**Breakdown:** 336 pytest + 41 BDD + 3 Vitest = 380 total checks, 0 failures.

Additional quality gates: `make lint` and `make typecheck`.

---

## Documentation index

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Component diagram, data flow, module interactions |
| [SECURITY.md](SECURITY.md) | Threat model, authentication, header hardening, rate limiting |
| [PERSISTENCE.md](PERSISTENCE.md) | Database schema, migration strategy, `glx_` table reference |
| [INTEGRATION_MAP.md](INTEGRATION_MAP.md) | Stargate integration points and shared-database contract |
| [KNOWN_GAPS.md](KNOWN_GAPS.md) | Current limitations and planned improvements |
| [docs/SBE.md](docs/SBE.md) | Specification by Example -- BDD scenario catalog |

---

## Theoretical foundations

**Computational Irreducibility.** GeoLux treats agentic inference outputs as computationally irreducible processes -- their behavior cannot be predicted without executing the full computation. This motivates the hypothesis-validate-replay loop rather than static policy enforcement.

**Geometric State Theory.** System stability is modeled as a geometric manifold where each engine's state vector occupies a position in a multi-dimensional space. The stability module continuously computes manifold curvature to detect drift before constraint violations occur, enabling preemptive MPC corrections.
