"""Prometheus metrics and OpenTelemetry instrumentation for GeoLux.

Metrics exposed at /metrics endpoint.
"""

from __future__ import annotations

import time
from typing import Optional

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

if PROMETHEUS_AVAILABLE:
    http_requests_total = Counter(
        "geolux_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )
    http_request_duration = Histogram(
        "geolux_http_request_duration_seconds",
        "HTTP request duration",
        ["method", "path"],
    )
    llm_calls_total = Counter(
        "geolux_llm_calls_total",
        "Total LLM calls",
        ["endpoint", "stability_state"],
    )
    llm_call_duration = Histogram(
        "geolux_llm_call_duration_seconds",
        "LLM call duration",
        ["endpoint"],
    )
    llm_stability_score = Histogram(
        "geolux_llm_stability_score",
        "LLM call stability scores",
        ["endpoint"],
        buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    )
    hypotheses_generated = Counter(
        "geolux_hypotheses_generated_total",
        "Total hypotheses generated",
    )
    classifications_completed = Counter(
        "geolux_classifications_completed_total",
        "Total classifications completed",
        ["result"],
    )
    mpc_cycles_total = Counter(
        "geolux_mpc_cycles_total",
        "Total MPC cycles",
        ["suspended"],
    )
    routing_decisions_total = Counter(
        "geolux_routing_decisions_total",
        "Total routing decisions",
        ["tier", "substrate"],
    )
    circuit_breaker_state = Gauge(
        "geolux_circuit_breaker_state",
        "Circuit breaker state (0=closed, 1=open)",
    )
    active_mode = Gauge(
        "geolux_mode",
        "Current operating mode",
        ["mode"],
    )
else:
    class _NoopMetric:
        def inc(self, *a, **kw): pass
        def observe(self, *a, **kw): pass
        def set(self, *a, **kw): pass
        def labels(self, *a, **kw): return self

    http_requests_total = _NoopMetric()
    http_request_duration = _NoopMetric()
    llm_calls_total = _NoopMetric()
    llm_call_duration = _NoopMetric()
    llm_stability_score = _NoopMetric()
    hypotheses_generated = _NoopMetric()
    classifications_completed = _NoopMetric()
    mpc_cycles_total = _NoopMetric()
    routing_decisions_total = _NoopMetric()
    circuit_breaker_state = _NoopMetric()
    active_mode = _NoopMetric()


def get_metrics_response():
    """Generate Prometheus metrics response."""
    if PROMETHEUS_AVAILABLE:
        return generate_latest(), CONTENT_TYPE_LATEST
    return b"# prometheus_client not installed\n", "text/plain"
