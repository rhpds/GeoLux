# GeoLux Integration Map

## System Overview

```
                    ┌─────────────────────────────────────────────┐
                    │              Stargate Platform              │
                    │  (React Dashboard + FastAPI + PostgreSQL)   │
                    └──────┬──────────────┬──────────────┬───────┘
                           │              │              │
                    Evidence Bundles  Event Bus    Dashboard API
                           │              │              │
          ┌────────────────┼──────────────┼──────────────┼────────────────┐
          │                │     GeoLux Platform         │                │
          │                ▼              │              ▼                │
          │  ┌──────────────────┐        │   ┌───────────────────┐       │
          │  │   Constraint     │        │   │  Stability-Aware  │       │
          │  │ Classification   │◄───────┼───│   LLM Client      │       │
          │  │    Engine        │        │   │  (LiteLLM+Logprobs)│      │
          │  └────────┬─────────┘       │   └────────┬──────────┘       │
          │           │                  │            │                   │
          │           ▼                  │            ▼                   │
          │  ┌──────────────────┐        │   ┌───────────────────┐       │
          │  │   Hypothesis     │        │   │    Geometric      │       │
          │  │   Engine (THE)   │◄───────┼───│   Stability       │       │
          │  │                  │        │   │   Infrastructure  │       │
          │  └────────┬─────────┘       │   └───────────────────┘       │
          │           │                  │                               │
          │           ▼                  │                               │
          │  ┌──────────────────┐        │                               │
          │  │   LLM-MPC        │        │                               │
          │  │   Controller     │        │                               │
          │  └────────┬─────────┘       │                               │
          │           │                  │                               │
          │           ▼                  │                               │
          │  ┌──────────────────┐  ┌─────┴──────────┐  ┌──────────────┐ │
          │  │   Deepfield      │  │   Launchpad    │  │  Synthetic   │ │
          │  │   Router         │  │   Intelligence │  │  Client +    │ │
          │  │   + NanoObs      │  │   Layer        │  │  Replay      │ │
          │  └──────────────────┘  └────────────────┘  └──────────────┘ │
          └──────────────────────────────────────────────────────────────┘
```

## Kafka Topic Flows

```
Stargate Collectors ─── evidence.collected ──────►  THE + Classification
THE ────────────────── hypothesis.generated ─────►  Classification + Event Bus
Classification ──────── classification.completed ──► LLM-MPC + Deepfield + Dashboard
LLM-MPC ────────────── mpc.action.recommended ───►  Action Execution + Dashboard
Deepfield ──────────── deepfield.routing.decision ► Inference Serving + Dashboard
Launchpad ──────────── launchpad.intelligence ────►  Dashboard + Deepfield
All Components ──────── audit.event ──────────────►  Audit Trail + Dashboard
Action Execution ────── action.executed ──────────►  Audit Trail + Dashboard
Synthetic Client ────── replay.scenario ──────────►  Evidence Consumers (replay mode)
```

## REST API Dependencies

| Consumer | Provider | Endpoint |
|----------|----------|----------|
| Dashboard | Stability | GET /stability/scores |
| Dashboard | THE | GET /hypotheses/queue |
| Dashboard | Classification | GET /classify/constraints |
| Dashboard | MPC | GET /mpc/cycles |
| Dashboard | Deepfield | GET /deepfield/routing-history |
| Dashboard | Launchpad | GET /launchpad/intelligence |
| THE | Stability Client | (internal: StabilityAwareLLMClient) |
| Classification | Stability Client | (internal: semantic evaluation) |
| MPC | Classification | (consumes classification results) |
| Deepfield | Stability Client | (internal: workload classification) |

## PostgreSQL Tables

| Table | Owner Component | Consumers |
|-------|----------------|-----------|
| glx_llm_stability_records | Stability Infrastructure | All LLM-calling components |
| glx_hypotheses | Hypothesis Engine | Classification, Dashboard |
| glx_constraint_definitions | Classification Engine | Classification, Dashboard |
| glx_classifications | Classification Engine | MPC, Dashboard |
| glx_mpc_cycles | LLM-MPC Controller | Dashboard |
| glx_routing_decisions | Deepfield Router | Dashboard |
| glx_nano_obs_records | NanoObs | Deepfield, Dashboard |
| glx_audit_events | All Components | Dashboard, Compliance |
| glx_launchpad_intelligence | Launchpad | Dashboard, Deepfield |

## Data Flow: Evidence → Action

1. **Evidence Collection** (Stargate collectors → Kafka `evidence.collected`)
2. **Constraint Classification** (evidence → formal constraint evaluation → classification result)
3. **Hypothesis Generation** (evidence → stability-aware LLM → ranked falsifiable hypotheses)
4. **Hypothesis Validation** (hypotheses → deterministic evaluation against evidence)
5. **MPC Planning** (classification + state → LLM prediction → action optimization)
6. **Deepfield Routing** (workload → complexity classification → tier/substrate assignment)
7. **Action Execution** (first action only → observe outcome → replan)
8. **Audit Trail** (every step logged to glx_audit_events + Kafka `audit.event`)

## Operating Modes

| Mode | Evidence Source | LLM | Stability | Audit |
|------|---------------|-----|-----------|-------|
| **LIVE** | Real collectors | Real calls | Real measurement | Full |
| **SYNTHETIC** | Scenario generator | Real calls | Real measurement | Full |
| **REPLAY** | Kafka replay archive | Real calls | Real measurement + ground truth comparison | Full |

Mode switch: `PUT /mode` — no restart required.

## External Integrations

| System | Integration Point | Direction |
|--------|------------------|-----------|
| LiteLLM | StabilityAwareLLMClient | GeoLux → LiteLLM |
| Granite (via vLLM) | LiteLLM backend | LiteLLM → Gaudi/Xeon6 |
| OpenShift | Helm chart deployment | Deploy target |
| Stargate | Shared PostgreSQL, Event Bus | Bidirectional |
| Kafka | All inter-service events | Publish/Subscribe |
| Prometheus | Metrics endpoint | GeoLux → Prometheus |
