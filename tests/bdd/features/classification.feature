Feature: Evidence-Based Constraint Classification
  As a governed inference platform
  I need to classify system state against formal constraint definitions
  So that classification is deterministic, auditable, and evidence-based

  Scenario: All constraints pass for healthy cluster
    Given constraint definitions for cluster-health stage
    And evidence showing a healthy cluster
    When evidence is classified
    Then the overall result is "pass"
    And all individual constraints pass

  Scenario: Constraint fails for unhealthy cluster
    Given constraint definitions for cluster-health stage
    And evidence showing cluster unreachable
    When evidence is classified
    Then the overall result is "fail"

  Scenario: Missing evidence produces inconclusive
    Given constraint definitions for cluster-health stage
    And evidence with missing fields
    When evidence is classified
    Then at least one constraint is "inconclusive"

  Scenario: Threshold constraint evaluates correctly
    Given a threshold constraint requiring cpu below 85
    And evidence with cpu at 50
    When the constraint is evaluated
    Then the result is "pass"

  Scenario: Boolean constraint evaluates correctly
    Given a boolean constraint requiring cluster reachable
    And evidence with cluster unreachable
    When the constraint is evaluated
    Then the result is "fail"

  Scenario: Range constraint evaluates correctly
    Given a range constraint requiring status code 200-299
    And evidence with status code 200
    When the constraint is evaluated
    Then the result is "pass"
