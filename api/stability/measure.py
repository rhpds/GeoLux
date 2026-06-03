"""Geometric stability measurement functions.

Implements fallback measurement methods for cloud LLM APIs that don't
expose transformer activations. Primary method (activation variance)
requires vLLM on Gaudi/Xeon6 — not available yet.

Fallback methods:
1. Token probability variance — variance in top-k token probabilities
2. Logit entropy — entropy of logit distribution per step
3. Perplexity — perplexity of generated output against input context
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Optional


class StabilityMethod(str, Enum):
    ACTIVATION_VARIANCE = "activation_variance"
    TOKEN_PROBABILITY = "token_probability"
    PERPLEXITY = "perplexity"
    LOGIT_ENTROPY = "logit_entropy"


class StabilityState(str, Enum):
    STABLE_PASS = "stable_pass"
    UNSTABLE_PASS = "unstable_pass"
    STABLE_FAIL = "stable_fail"
    UNSTABLE_FAIL = "unstable_fail"


def compute_token_probability_variance(logprobs: list[list[float]]) -> float:
    """Measure confidence via top-1 token probability at each generation step.

    Uses the top token's logprob as the confidence signal. A logprob near 0.0
    means the model is very confident (probability near 1.0). More negative
    means less confident. We average the top-1 logprob across all steps and
    convert to a 0-1 score.
    """
    if not logprobs:
        return 0.5

    top1_logprobs = []
    for step_probs in logprobs:
        if step_probs:
            top1_logprobs.append(max(step_probs))

    if not top1_logprobs:
        return 0.5

    avg_top1 = sum(top1_logprobs) / len(top1_logprobs)
    return _normalize_score(-avg_top1, lower_is_better=True, scale=5.0)


def compute_logit_entropy(logprobs: list[list[float]]) -> float:
    """Compute entropy of logit distribution at each generation step.

    Lower entropy = more certain = more stable = higher score.
    """
    if not logprobs:
        return 0.5

    entropies = []
    for step_probs in logprobs:
        if not step_probs:
            continue
        probs = [math.exp(lp) for lp in step_probs]
        total = sum(probs)
        if total == 0:
            continue
        probs = [p / total for p in probs]
        entropy = -sum(p * math.log(p + 1e-10) for p in probs if p > 0)
        entropies.append(entropy)

    if not entropies:
        return 0.5

    mean_entropy = sum(entropies) / len(entropies)
    return _normalize_score(mean_entropy, lower_is_better=True, scale=3.0)


def compute_perplexity(logprobs: list[list[float]]) -> float:
    """Compute perplexity from token log probabilities.

    Lower perplexity = more confident = more stable = higher score.
    """
    if not logprobs:
        return 0.5

    top_logprobs = []
    for step in logprobs:
        if step:
            top_logprobs.append(max(step))

    if not top_logprobs:
        return 0.5

    avg_neg_logprob = -sum(top_logprobs) / len(top_logprobs)
    perplexity = math.exp(min(avg_neg_logprob, 20))
    return _normalize_score(perplexity, lower_is_better=True, scale=100.0)


def compute_stability_score(
    logprobs: list[list[float]],
    method: str = "token_probability",
) -> float:
    """Compute stability score using the specified method.

    Returns score normalized to [0.0, 1.0].
    0.0 = maximally unstable, 1.0 = maximally stable.
    """
    if method == "token_probability":
        return compute_token_probability_variance(logprobs)
    elif method == "logit_entropy":
        return compute_logit_entropy(logprobs)
    elif method == "perplexity":
        return compute_perplexity(logprobs)
    else:
        return 0.5


def determine_stability_state(
    stability_score: float,
    outcome_correct: bool,
    threshold: float = 0.7,
) -> StabilityState:
    """Determine the four-state stability classification.

    - Stable pass: correct output from stable geometry. Trust.
    - Unstable pass: correct output from unstable geometry. Fragile.
    - Stable fail: incorrect output from stable geometry. Real problem.
    - Unstable fail: incorrect output from unstable geometry. Investigate.
    """
    if stability_score >= threshold:
        if outcome_correct:
            return StabilityState.STABLE_PASS
        return StabilityState.STABLE_FAIL
    else:
        if outcome_correct:
            return StabilityState.UNSTABLE_PASS
        return StabilityState.UNSTABLE_FAIL


def _normalize_score(value: float, lower_is_better: bool = True, scale: float = 1.0) -> float:
    """Normalize a raw signal to [0.0, 1.0]."""
    normalized = value / max(scale, 0.001)
    if lower_is_better:
        score = max(0.0, 1.0 - normalized)
    else:
        score = min(1.0, normalized)
    return round(max(0.0, min(1.0, score)), 4)
