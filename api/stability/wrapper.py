"""Stability-aware LLM client wrapper.

Intercepts all LLM calls, requests logprobs, computes stability score,
and attaches it to the response before returning to the caller.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from api.stability.measure import (
    StabilityMethod,
    StabilityState,
    compute_stability_score,
    determine_stability_state,
)
from db import repository
from db.models import StabilityMethod as DBStabilityMethod, StabilityState as DBStabilityState

logger = logging.getLogger("geolux.stability")

COST_PER_1K_PROMPT = float(os.environ.get("GEOLUX_LLM_COST_PROMPT", "0.003"))
COST_PER_1K_COMPLETION = float(os.environ.get("GEOLUX_LLM_COST_COMPLETION", "0.006"))

_prompt_cache: dict[str, dict] = {}
_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts")


def load_prompt(name: str) -> dict:
    """Load a versioned prompt from prompts/{name}.yaml. Cached after first load."""
    if name in _prompt_cache:
        return _prompt_cache[name]
    import yaml
    path = os.path.join(_PROMPTS_DIR, f"{name}.yaml")
    if not os.path.exists(path):
        logger.warning("Prompt file not found: %s", path)
        return {}
    with open(path) as f:
        prompt = yaml.safe_load(f)
    _prompt_cache[name] = prompt
    logger.info("Loaded prompt '%s' v%s", name, prompt.get("version", "?"))
    return prompt


class CircuitBreaker:
    """Circuit breaker for LLM calls. Opens after consecutive failures, auto-resets after cooldown."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._opened_at: Optional[float] = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        import time as _t
        if _t.time() - self._opened_at > self.cooldown_seconds:
            self._opened_at = None
            self._failures = 0
            return False
        return True

    def record_success(self):
        self._failures = 0
        self._opened_at = None

    def record_failure(self):
        self._failures += 1
        if self._failures >= self.failure_threshold:
            import time as _t
            self._opened_at = _t.time()
            logger.warning("Circuit breaker opened after %d failures", self._failures)

    def reset(self):
        self._failures = 0
        self._opened_at = None


_circuit_breaker = CircuitBreaker()


class StabilityAwareLLMClient:
    """Wraps LLM calls with geometric stability measurement and circuit breaker."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        stability_threshold: float = 0.7,
        stability_method: str = "token_probability",
    ):
        self.base_url = base_url or os.environ.get("GEOLUX_LITELLM_URL", "")
        self.api_key = api_key or os.environ.get("GEOLUX_LITELLM_API_KEY", "")
        self.model = model or os.environ.get("GEOLUX_LLM_MODEL", "granite-3-2-8b-instruct")
        self.stability_threshold = stability_threshold
        self.stability_method = stability_method

    def _get_threshold(self, endpoint: str) -> float:
        """Get per-endpoint stability threshold, falling back to global."""
        try:
            from api.routers._shared import STABILITY_THRESHOLDS
            return STABILITY_THRESHOLDS.get(endpoint, self.stability_threshold)
        except ImportError:
            return self.stability_threshold

    def call(
        self,
        endpoint: str,
        messages: list[dict],
        max_tokens: int = 500,
        temperature: float = 0.1,
        db: Optional[Session] = None,
        outcome_correct: Optional[bool] = None,
    ) -> dict:
        """Call LLM with stability measurement.

        Returns dict with: content, success, stability_score, stability_state,
        stability_method, usage, latency_ms.
        """
        import time
        start = time.time()
        call_id = str(uuid.uuid4())

        if _circuit_breaker.is_open:
            from api.metrics import circuit_breaker_state
            circuit_breaker_state.set(1)
            return {
                "content": "",
                "success": False,
                "call_id": call_id,
                "stability_score": 0.0,
                "stability_state": StabilityState.UNSTABLE_FAIL.value,
                "stability_method": self.stability_method,
                "latency_ms": 0,
                "error": "Circuit breaker open — LLM calls suspended",
            }

        try:
            import litellm
            response = litellm.completion(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                api_base=self.base_url if self.base_url else None,
                api_key=self.api_key if self.api_key else None,
                logprobs=True,
                top_logprobs=5,
            )

            content = response.choices[0].message.content
            logprobs_data = self._extract_logprobs(response)
            stability_score = compute_stability_score(logprobs_data, self.stability_method)

            is_correct = outcome_correct if outcome_correct is not None else True
            threshold = self._get_threshold(endpoint)
            stability_state = determine_stability_state(
                stability_score, is_correct, threshold
            )

            latency_ms = int((time.time() - start) * 1000)

            if db:
                self._store_stability_record(
                    db, call_id, endpoint, stability_score,
                    stability_state, logprobs_data, latency_ms,
                )

            _circuit_breaker.record_success()

            from api.metrics import llm_calls_total, llm_call_duration, llm_stability_score as llm_stab_metric
            llm_calls_total.labels(endpoint=endpoint, stability_state=stability_state.value).inc()
            llm_call_duration.labels(endpoint=endpoint).observe(latency_ms / 1000)
            llm_stab_metric.labels(endpoint=endpoint).observe(stability_score)

            return {
                "content": content,
                "success": True,
                "call_id": call_id,
                "stability_score": stability_score,
                "stability_state": stability_state.value,
                "stability_method": self.stability_method,
                "latency_ms": latency_ms,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            }

        except Exception as e:
            _circuit_breaker.record_failure()
            latency_ms = int((time.time() - start) * 1000)
            logger.warning("LLM call failed for %s: %s", endpoint, e)
            return {
                "content": "",
                "success": False,
                "call_id": call_id,
                "stability_score": 0.0,
                "stability_state": StabilityState.UNSTABLE_FAIL.value,
                "stability_method": self.stability_method,
                "latency_ms": latency_ms,
                "error": str(e),
            }

    def _extract_logprobs(self, response) -> list[list[float]]:
        """Extract logprobs from LLM response."""
        try:
            choice = response.choices[0]
            if hasattr(choice, "logprobs") and choice.logprobs:
                content_logprobs = choice.logprobs.content or []
                return [
                    [tlp.logprob for tlp in token.top_logprobs]
                    for token in content_logprobs
                    if hasattr(token, "top_logprobs") and token.top_logprobs
                ]
        except (AttributeError, IndexError):
            pass
        return []

    def _store_stability_record(
        self,
        db: Session,
        call_id: str,
        endpoint: str,
        stability_score: float,
        stability_state: StabilityState,
        logprobs_data: list,
        latency_ms: int,
    ):
        """Persist stability measurement to database."""
        try:
            method_map = {
                "token_probability": DBStabilityMethod.TOKEN_PROBABILITY,
                "logit_entropy": DBStabilityMethod.LOGIT_ENTROPY,
                "perplexity": DBStabilityMethod.PERPLEXITY,
                "activation_variance": DBStabilityMethod.ACTIVATION_VARIANCE,
            }
            state_map = {
                "stable_pass": DBStabilityState.STABLE_PASS,
                "unstable_pass": DBStabilityState.UNSTABLE_PASS,
                "stable_fail": DBStabilityState.STABLE_FAIL,
                "unstable_fail": DBStabilityState.UNSTABLE_FAIL,
            }

            repository.create_stability_record(
                db,
                call_id=call_id,
                endpoint=endpoint,
                model=self.model,
                stability_score=stability_score,
                stability_method=method_map.get(self.stability_method, DBStabilityMethod.TOKEN_PROBABILITY),
                stability_threshold=self.stability_threshold,
                stability_state=state_map.get(stability_state.value, DBStabilityState.UNSTABLE_FAIL),
                raw_signal={"logprobs_length": len(logprobs_data), "latency_ms": latency_ms},
            )
        except Exception as e:
            logger.warning("Failed to store stability record: %s", e)
