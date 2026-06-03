"""Synthetic client and Kafka replay endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from api.routers._shared import GEOLUX_MODE

router = APIRouter(prefix="/scenarios", tags=["synthetic-client"])


class ScenarioRunRequest(BaseModel):
    scenario_name: str
    speed_multiplier: float = 1.0
    entropy_level: float = 0.0


class ReplayStartRequest(BaseModel):
    archive_name: str
    speed_multiplier: float = 1.0
    pause_at_offset: Optional[int] = None


@router.get("/list")
def list_scenarios():
    from scenarios import registry
    return {"scenarios": registry.list_scenarios()}


@router.post("/run", status_code=201)
def run_scenario(
    body: ScenarioRunRequest,
    db: Session = Depends(get_db),
):
    from scenarios import registry
    scenario = registry.get_scenario(body.scenario_name)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{body.scenario_name}' not found")
    result = scenario.run(
        speed_multiplier=body.speed_multiplier,
        entropy_level=body.entropy_level,
        db=db,
    )
    return result


@router.post("/replay/start", status_code=201)
def start_replay(body: ReplayStartRequest):
    if GEOLUX_MODE != "replay":
        raise HTTPException(status_code=409, detail="Replay only available in GEOLUX_MODE=replay")
    from engine.replay import KafkaReplayEngine
    engine = KafkaReplayEngine()
    result = engine.start(
        archive_name=body.archive_name,
        speed_multiplier=body.speed_multiplier,
        pause_at_offset=body.pause_at_offset,
    )
    return result


@router.post("/replay/pause")
def pause_replay():
    from engine.replay import KafkaReplayEngine
    engine = KafkaReplayEngine()
    return engine.pause()
