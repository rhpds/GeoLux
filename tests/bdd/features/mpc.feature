Feature: LLM-MPC Controller
  As a governed inference platform
  I need model predictive control with automatic horizon adjustment
  So that agent actions are optimized within constraint boundaries

  Scenario: Horizon stays same with moderate stability
    Given stability scores of 0.72 and 0.74
    And current horizon is 2
    When the horizon is adjusted
    Then the horizon remains 2

  Scenario: Horizon shortens on instability
    Given stability scores of 0.3 and 0.5
    And current horizon is 3
    When the horizon is adjusted
    Then the horizon is less than 3

  Scenario: Horizon extends on sustained high stability
    Given stability scores of 0.9, 0.85, and 0.88
    And current horizon is 2
    When the horizon is adjusted
    Then the horizon is 3

  Scenario: Horizon never exceeds maximum
    Given stability scores of 0.95, 0.95, and 0.95
    And current horizon is 5 with max 5
    When the horizon is adjusted
    Then the horizon remains 5

  Scenario: Suspension after consecutive instabilities
    Given 3 consecutive unstable prediction cycles
    When suspension is checked
    Then MPC is suspended

  Scenario: Generate scale candidate from objective
    Given an objective to scale to 5 replicas
    When candidates are generated
    Then a scale_replicas action is produced
