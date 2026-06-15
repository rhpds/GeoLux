"""Summit event data miner.

Combines three authoritative sources:
1. Labagator API — the 81 labs scheduled for Summit (lab inventory)
2. Stargate summit-report.json — mined AAP provisioning/destroy data,
   evaluations, cluster performance, failure correlation
3. summit-reclamation.json — AAP destroy job analysis proving retry
   vs orphan outcomes for failed reclamations

Summit: Red Hat Summit 2026, Atlanta GA, May 11-14
"""

from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db import repository

logger = logging.getLogger("geolux.summit")

LABAGATOR_BASE = "http://labagator-backend.labagator-prod.svc:8080"
SUMMIT_EVENT_ID = 1
REPORT_PATH = Path(__file__).parent.parent / "receipts" / "summit-report.json"
RECLAMATION_PATH = Path(__file__).parent.parent / "receipts" / "summit-reclamation.json"


def _labagator_get(path: str) -> dict | list | None:
    try:
        r = urllib.request.urlopen(f"{LABAGATOR_BASE}{path}", timeout=10)
        return json.loads(r.read())
    except Exception as e:
        logger.warning("Labagator API call failed %s: %s", path, e)
        return None


def _load_report() -> dict:
    if REPORT_PATH.exists():
        return json.loads(REPORT_PATH.read_text())
    return {}


def _load_reclamation() -> dict:
    if RECLAMATION_PATH.exists():
        return json.loads(RECLAMATION_PATH.read_text())
    return {}


class SummitMiner:
    """Mines Summit data from Labagator + Stargate receipts."""

    def run(self, db: Session) -> dict:
        try:
            event = _labagator_get(f"/api/v1/events/{SUMMIT_EVENT_ID}")
            labs = _labagator_get(f"/api/v1/labs?event_id={SUMMIT_EVENT_ID}") or []
            report = _load_report()
            reclamation = _load_reclamation()

            event_info = {}
            if event:
                event_info = {
                    "event": event.get("name", "Red Hat Summit 2026"),
                    "location": event.get("location", ""),
                    "start_date": event.get("start_date", ""),
                    "end_date": event.get("end_date", ""),
                    "timezone": event.get("timezone", ""),
                    "rooms": event.get("rooms", []),
                    "enabled_dates": event.get("enabled_dates", []),
                }
            else:
                event_info = {
                    "event": "Red Hat Summit 2026",
                    "location": "Atlanta, GA",
                    "start_date": report.get("dates", {}).get("start", "2026-05-11"),
                    "end_date": report.get("dates", {}).get("end", "2026-05-14"),
                }

            dates = f"{event_info['start_date']} to {event_info['end_date']}"

            lab_summary = self._summarize_labs(labs)
            schedule = self._build_schedule(event)

            evals = report.get("evaluations", {})
            aap = report.get("aap", {})
            clusters = report.get("clusters", [])
            correlation = report.get("correlation", [])
            failure_breakdown = aap.get("failure_breakdown", {})

            overview = {
                "total_labs": lab_summary.get("total", len(labs)),
                "total_rooms": len(event_info.get("rooms", [])),
                "event_days": len(event_info.get("enabled_dates", [])),
                "total_evals": evals.get("total", 0),
                "eval_pass_rate": evals.get("pass_rate", 0),
                "total_aap_jobs": aap.get("total_jobs", 0),
                "aap_failed": aap.get("total_failed", 0),
                "aap_success_rate": aap.get("overall_success_rate", 0),
            }

            start = event_info["start_date"]
            end = event_info["end_date"]

            repository.create_intelligence_record(
                db,
                intelligence_type="summit_overview",
                data_payload={
                    **event_info,
                    "dates": dates,
                    "overview": overview,
                    "labs": lab_summary,
                    "schedule": schedule,
                    "evaluations": evals,
                    "aap": aap,
                    "clusters": clusters,
                    "correlation": correlation,
                    "failure_breakdown": failure_breakdown,
                    "reclamation": reclamation,
                    "data_sources": ["labagator", "stargate-receipts", "aap-controller"],
                },
                time_window_start=datetime.fromisoformat(f"{start}T00:00:00+00:00"),
                time_window_end=datetime.fromisoformat(f"{end}T23:59:59+00:00"),
            )

            repository.create_intelligence_record(
                db,
                intelligence_type="demand_signal",
                data_payload={
                    "event": "summit",
                    "total_labs": len(labs),
                    "aap_summary": {
                        "total_jobs": aap.get("total_jobs", 0),
                        "failed": aap.get("total_failed", 0),
                        "destroy_failures": failure_breakdown.get("by_type", {}).get("destroy", 0),
                        "provision_failures": failure_breakdown.get("by_type", {}).get("provision", 0),
                    },
                    "eval_summary": {
                        "total": evals.get("total", 0),
                        "pass_rate": evals.get("pass_rate", 0),
                    },
                },
                time_window_start=datetime.fromisoformat(f"{start}T00:00:00+00:00"),
                time_window_end=datetime.fromisoformat(f"{end}T23:59:59+00:00"),
            )

            db.commit()

            logger.info(
                "Summit mined: %d labs (labagator), %d AAP jobs, %d evals (receipts)",
                len(labs), aap.get("total_jobs", 0), evals.get("total", 0),
            )

            return overview

        except Exception as e:
            logger.warning("Summit mining failed: %s", e)
            return {"error": str(e)}

    def _summarize_labs(self, labs: list) -> dict:
        by_status: dict[str, int] = {}
        by_cloud: dict[str, int] = {}
        by_env_type: dict[str, int] = {}
        lab_list = []

        for lab in labs:
            status = lab.get("status") or "unknown"
            cloud = lab.get("cloud") or "unconfigured"
            env_type = lab.get("env_type") or "unconfigured"

            by_status[status] = by_status.get(status, 0) + 1
            if cloud:
                by_cloud[cloud] = by_cloud.get(cloud, 0) + 1
            if env_type:
                by_env_type[env_type] = by_env_type.get(env_type, 0) + 1

            lab_list.append({
                "lab_code": lab.get("lab_code", ""),
                "title": lab.get("title", ""),
                "status": status,
                "cloud": cloud,
                "env_type": env_type,
                "deploy_mode": lab.get("deploy_mode") or "",
            })

        return {
            "total": len(labs),
            "by_status": dict(sorted(by_status.items(), key=lambda x: -x[1])),
            "by_cloud": dict(sorted(by_cloud.items(), key=lambda x: -x[1])),
            "by_env_type": dict(sorted(by_env_type.items(), key=lambda x: -x[1])),
            "lab_list": lab_list,
        }

    def _build_schedule(self, event: dict | None) -> dict:
        if not event:
            return {"event_days": 0, "rooms": []}

        enabled_dates = event.get("enabled_dates", [])
        rooms = event.get("rooms", [])

        return {
            "event_days": len(enabled_dates),
            "by_day": [
                {"date": d.get("date", ""), "start_hour": d.get("start_hour", ""), "end_hour": d.get("end_hour", "")}
                for d in enabled_dates
            ],
            "rooms": sorted(
                [{"name": r.get("room_name", ""), "capacity": r.get("default_capacity", 0)} for r in rooms],
                key=lambda x: x["name"],
            ),
            "total_capacity": sum(r.get("default_capacity", 0) for r in rooms),
        }
