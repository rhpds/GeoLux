# PostgreSQL Role Setup

GeoLux shares a PostgreSQL instance with StarGate. All GeoLux tables use the `glx_*` prefix. To contain blast radius, each service should use a scoped database role instead of the shared superuser.

## Create the GeoLux role

```sql
-- Run as PostgreSQL superuser (once per cluster)
CREATE ROLE geolux_app LOGIN PASSWORD '<generate-a-strong-password>';

-- Grant access to GeoLux tables only
GRANT CONNECT ON DATABASE stargate TO geolux_app;
GRANT USAGE ON SCHEMA public TO geolux_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  glx_llm_stability_records,
  glx_hypotheses,
  glx_constraint_definitions,
  glx_classifications,
  glx_mpc_cycles,
  glx_routing_decisions,
  glx_nano_obs_records,
  glx_audit_events,
  glx_launchpad_intelligence
TO geolux_app;

-- Allow Alembic migrations (grant on sequences too)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO geolux_app;

-- For future tables created by Alembic
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO geolux_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO geolux_app;
```

## Update the deployment

Set `GEOLUX_DATABASE_URL` to use the scoped role:

```
GEOLUX_DATABASE_URL=postgresql://geolux_app:<password>@stargate-postgres.stargate.svc:5432/stargate
```

## What this prevents

- GeoLux cannot read/write StarGate tables (evaluations, runs, stages, evidence)
- A bug in GeoLux migrations cannot drop StarGate tables
- A leaked GeoLux DB password does not grant access to StarGate data
