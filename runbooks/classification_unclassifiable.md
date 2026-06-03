# Runbook: Classification Unclassifiable Event

## Trigger
Evidence matches no constraint definition. The system cannot classify
the observed state. Rubric extension triggered for human review.

## Severity
**Medium** — Unclassified evidence indicates a gap in rubric coverage.

## Symptoms
- Classification result contains `unclassifiable` constraints
- Kafka `audit.event` topic receiving unclassifiable events
- Novel evidence fields not covered by any constraint definition

## Investigation Steps

1. **Identify the unclassifiable evidence**
   ```sql
   SELECT c.evidence_bundle_id, c.constraint_id, c.result, c.evidence_chain
   FROM glx_classifications c
   WHERE c.result = 'unclassifiable'
   ORDER BY c.created_at DESC LIMIT 20;
   ```

2. **Check what evidence fields were present**
   - Review the evidence chain for missing or unexpected fields
   - Compare against constraint evidence_requirements

3. **Determine if constraint coverage needs expansion**
   - Is this a new workload type?
   - Has infrastructure changed?
   - Is the evidence format different from expected?

## Remediation
- Add new constraint YAML definitions to `constraints/stages/`
- Run `sync_constraints_to_db` to load new definitions
- Re-classify the evidence bundle to verify coverage

## Escalation
- Sustained unclassifiable rate > 10%: notify rubric maintainer
- New infrastructure type: coordinate with platform team
