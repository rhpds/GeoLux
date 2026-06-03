Feature: Synthetic Client and Mode Switching
  As a governed inference platform
  I need synthetic scenarios and mode switching
  So that I can test without touching production

  Scenario: Healthy baseline scenario generates passing state
    Given the healthy-baseline scenario
    When the scenario is executed
    Then all expected outcomes are "pass"

  Scenario: Node failure scenario generates failing state
    Given the node-failure scenario
    When the scenario is executed
    Then cluster-health expected outcome is "fail"

  Scenario: Scenario registry lists all scenarios
    Given all scenarios are registered
    When the scenario list is requested
    Then at least 3 scenarios are available

  Scenario: Mode can be switched without restart
    Given the current mode is "live"
    When mode is switched to "synthetic"
    Then the current mode is "synthetic"
