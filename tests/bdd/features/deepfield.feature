Feature: Deepfield Router
  As a governed inference platform
  I need to route workloads to appropriate hardware substrates
  So that task complexity maps to proper compute resources

  Scenario: Simple workload routes to nano tier
    Given a workload with no reasoning required
    When the workload is classified by rules
    Then the tier is "nano" with substrate "cpu"

  Scenario: Complex workload routes to macro tier
    Given a workload that is novel and multi-step
    When the workload is classified by rules
    Then the tier is "macro" with substrate "gaudi"

  Scenario: Override requires a reason
    Given a routing request with override but no reason
    Then the routing is rejected

  Scenario: Tier escalation on unstable classification
    Given an unstable classification result for nano tier
    When safety escalation is applied
    Then the tier is escalated to "micro"

  Scenario: Fallback when gaudi unavailable
    Given a macro workload and gaudi is unavailable
    When fallback policy is applied
    Then the workload routes to nano with cpu

  Scenario: NanoObs detects drift after sufficient observations
    Given 10 observations with value 95 against threshold 80
    When a new observation is recorded
    Then drift is detected
    And an adjustment is recommended

  Scenario: NanoObs adjustment requires human approval
    Given a recommended threshold adjustment
    When the adjustment is approved by an operator
    Then the approval is recorded with the operator name
