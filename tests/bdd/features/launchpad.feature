Feature: Launchpad Intelligence Layer
  As a governed inference platform
  I need to surface provisioning patterns from RHDP data
  So that demand, cost, and utilization are visible

  Scenario: Compute demand signals from sessions
    Given provisioning data with 4 sessions
    When demand signals are computed
    Then the most requested demo is identified
    And returning partners are identified

  Scenario: Compute cost attribution
    Given provisioning data with 4 sessions
    When cost attribution is computed
    Then total cost is 170.0
    And per-lab costs are calculated

  Scenario: Compute utilization patterns
    Given provisioning data with capacity info
    When utilization patterns are computed
    Then peak demand hours are identified
    And underutilized configs are identified

  Scenario: Compute routing intelligence
    Given routing history data
    When routing intelligence is computed
    Then gaudi workload types are surfaced
