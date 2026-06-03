Feature: Hypothesis Engine (THE)
  As a governed inference platform
  I need to generate structured falsifiable hypotheses about system state
  So that decisions are based on evidence validation, not LLM confidence

  Scenario: Generate hypotheses from evidence bundle
    Given an evidence bundle with cluster health data
    When hypotheses are generated
    Then the result contains structured hypotheses
    And each hypothesis has a claim and testable conditions
    And hypotheses are ranked by stability score

  Scenario: Validate a hypothesis against evidence
    Given a hypothesis claiming "cpu usage is above 90%"
    And evidence showing cpu at 95%
    When the hypothesis is validated
    Then the outcome is "validated"

  Scenario: Falsify a hypothesis against evidence
    Given a hypothesis claiming "cpu usage is above 90%"
    And evidence showing cpu at 50%
    When the hypothesis is validated
    Then the outcome is "falsified"

  Scenario: Inconclusive when evidence is missing
    Given a hypothesis claiming "cpu usage is above 90%"
    And evidence with no cpu field
    When the hypothesis is validated
    Then the outcome is "inconclusive"

  Scenario: Parse LLM JSON array response
    Given an LLM response with a JSON array of hypotheses
    When the response is parsed
    Then all hypotheses are extracted

  Scenario: Parse LLM code-fenced response
    Given an LLM response with code-fenced JSON
    When the response is parsed
    Then all hypotheses are extracted

  Scenario: Handle invalid LLM response
    Given an LLM response with invalid JSON
    When the response is parsed
    Then an empty list is returned
