# Runbook: Nano Agent Promotion Failure

## Trigger
A candidate nano agent failed the promotion gate during the agentic coding extension pipeline.

## Severity
**Low** — No impact on production. The candidate agent is rejected and does not touch real cluster state.

## Investigation
1. Review the failure evidence record in the audit trail
2. Check which promotion gate criterion failed
3. Review the synthetic scenario replay results

## Remediation
- Analyze the failure evidence and determine if the agent logic needs correction
- Re-submit the candidate after fixing the identified issues
- No production impact — the promotion gate prevented unsafe deployment

## Note
This runbook covers a future-phase feature (agentic coding extension). The promotion gate specification is documented but not yet implemented.
