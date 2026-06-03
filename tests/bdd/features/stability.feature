Feature: Geometric Stability Measurement
  As a governed inference platform
  I need to measure the geometric stability of LLM calls
  So that unstable outputs are flagged and gated before action

  Background:
    Given the stability threshold is 0.7

  Scenario: Stable LLM call produces stable_pass state
    Given an LLM call with low logprob variance
    When stability is measured
    And the output is correct
    Then the stability state is "stable_pass"
    And the stability score is above the threshold

  Scenario: Unstable LLM call produces unstable_pass state
    Given an LLM call with high logprob variance
    When stability is measured
    And the output is correct
    Then the stability state is "unstable_pass"
    And the stability score is below the threshold

  Scenario: Stable incorrect output produces stable_fail state
    Given an LLM call with low logprob variance
    When stability is measured
    And the output is incorrect
    Then the stability state is "stable_fail"

  Scenario: Unstable incorrect output produces unstable_fail state
    Given an LLM call with high logprob variance
    When stability is measured
    And the output is incorrect
    Then the stability state is "unstable_fail"

  Scenario: Missing logprobs returns default score
    Given an LLM call with no logprobs
    When stability is measured
    Then the stability score is 0.5

  Scenario: Stability threshold can be updated
    When the stability threshold is set to 0.85
    Then the stability threshold is 0.85

  Scenario: Invalid threshold is rejected
    When the stability threshold is set to 1.5
    Then the update is rejected with a validation error
