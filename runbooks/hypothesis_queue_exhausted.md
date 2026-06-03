# Runbook: Hypothesis Queue Exhausted

## Trigger
All hypotheses for an evidence bundle have been falsified. No remaining
hypotheses can explain the observed system state. Novel failure mode suspected.

## Severity
**Medium** — The system cannot classify the current state. Human review required.

## Symptoms
- Kafka `audit.event` topic receiving `rubric.extension.triggered` events
- All hypotheses for a bundle show `validation_outcome = falsified`
- `hypothesis.all_falsified` audit event logged
- Classification engine receiving unclassifiable evidence

## Investigation Steps

1. **Review the evidence bundle**
   ```sql
   SELECT h.evidence_bundle_id, h.claim, h.validation_outcome, h.evidence_snapshot
   FROM glx_hypotheses h
   WHERE h.evidence_bundle_id = '<bundle_id>'
   ORDER BY h.created_at;
   ```

2. **Identify what made each hypothesis fail**
   - For each falsified hypothesis, check which testable condition failed
   - Look for common patterns across falsifications

3. **Check if evidence is novel**
   - Compare evidence fields against known constraint definitions
   - Identify evidence fields that don't match any existing constraint

4. **Check recent cluster changes**
   - New workload types deployed?
   - Infrastructure changes (node additions, network changes)?
   - New failure modes not covered by rubric?

## Remediation

### Immediate
- Flag the evidence bundle for human review
- Queue the unclassified evidence in the rubric extension queue
- Continue monitoring — the system is safe (no action taken on unclassified state)

### Short-term
- Analyst reviews the evidence and determines if:
  - An existing constraint needs broader conditions
  - A new constraint should be added to the rubric
  - The evidence was an anomaly (no action needed)
- If new constraint needed: add to `constraints/stages/` YAML and redeploy

### Long-term
- Track frequency of "all falsified" events per cluster
- Clusters with frequent exhaustion may have drifted from rubric coverage
- Consider automated constraint proposal (Deepfield agentic coding extension)

## Escalation
- If exhaustion rate > 5% of bundles: notify rubric maintainer
- If exhaustion correlates with a specific cluster: investigate cluster-specific drift
- If exhaustion is sustained across clusters: rubric coverage review needed
