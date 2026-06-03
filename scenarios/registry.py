"""Scenario registry for synthetic client."""

from __future__ import annotations

from typing import Optional

_SCENARIOS: dict = {}


def register_scenario(scenario):
    _SCENARIOS[scenario.name] = scenario


def get_scenario(name: str) -> Optional[object]:
    return _SCENARIOS.get(name)


def list_scenarios() -> list[dict]:
    return [
        {"name": s.name, "description": s.description}
        for s in _SCENARIOS.values()
    ]
