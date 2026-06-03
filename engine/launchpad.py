"""Launchpad intelligence layer.

Mines provisioning data from RHDP ecosystem and surfaces patterns
invisible to existing tools. Not a provisioning tool — a provisioning
intelligence layer that sits on top of the existing RHDP stack.

Data sources consumed:
- RHDP provisioning event stream
- Babylon Control Plane via Stargate collector
- Sandbox-API via Stargate collector
- ZeroTouch catalog data via Stargate collector
- Labagator lab and session data via Stargate collector
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db import repository

logger = logging.getLogger("geolux.launchpad")


class LaunchpadIntelligence:
    def compute_demand_signals(self, data: dict, db: Session) -> dict:
        """Compute demand signals from provisioning data.

        Surfaces: most requested demos, failing configurations,
        returning partners, new partners.
        """
        sessions = data.get("sessions", [])
        labs = data.get("labs", [])

        demo_counts = Counter(s.get("demo_id", "") for s in sessions if s.get("demo_id"))
        most_requested = demo_counts.most_common(10)

        failure_counts = Counter(
            s.get("config", "")
            for s in sessions
            if s.get("status") == "failed" and s.get("config")
        )

        partner_sessions = defaultdict(list)
        for s in sessions:
            pid = s.get("partner_id", "")
            if pid:
                partner_sessions[pid].append(s)

        returning = [pid for pid, sess in partner_sessions.items() if len(sess) > 1]
        new = [pid for pid, sess in partner_sessions.items() if len(sess) == 1]

        signals = {
            "most_requested_demos": [{"demo_id": d, "count": c} for d, c in most_requested],
            "highest_failure_configs": [{"config": c, "count": n} for c, n in failure_counts.most_common(10)],
            "returning_partners": returning[:20],
            "new_partners": new[:20],
            "total_sessions": len(sessions),
            "total_labs": len(labs),
        }

        now = datetime.now(timezone.utc)
        record = repository.create_intelligence_record(
            db,
            intelligence_type="demand_signal",
            data_payload=signals,
            time_window_start=data.get("window_start", now),
            time_window_end=data.get("window_end", now),
        )
        db.commit()

        from events.publishers import publish_intelligence_updated
        publish_intelligence_updated({
            "intelligence_id": record.intelligence_id,
            "intelligence_type": "demand_signal",
        })

        return signals

    def compute_cost_attribution(self, data: dict, db: Session) -> dict:
        """Compute cost attribution across dimensions.

        Surfaces: cost per lab session, per SA, per partner,
        per Intel hardware configuration.
        """
        sessions = data.get("sessions", [])

        per_lab = defaultdict(float)
        per_sa = defaultdict(float)
        per_partner = defaultdict(float)
        per_hw = defaultdict(float)

        for s in sessions:
            cost = s.get("cost", 0.0)
            per_lab[s.get("lab_code", "unknown")] += cost
            per_sa[s.get("sa_id", "unknown")] += cost
            per_partner[s.get("partner_id", "unknown")] += cost
            per_hw[s.get("hardware_config", "unknown")] += cost

        costs = {
            "per_lab_session": [{"lab_code": k, "total_cost": round(v, 2)} for k, v in sorted(per_lab.items(), key=lambda x: -x[1])[:20]],
            "per_sa": [{"sa_id": k, "total_cost": round(v, 2)} for k, v in sorted(per_sa.items(), key=lambda x: -x[1])[:20]],
            "per_partner": [{"partner_id": k, "total_cost": round(v, 2)} for k, v in sorted(per_partner.items(), key=lambda x: -x[1])[:20]],
            "per_hardware_config": [{"config": k, "total_cost": round(v, 2)} for k, v in sorted(per_hw.items(), key=lambda x: -x[1])[:10]],
            "total_cost": round(sum(s.get("cost", 0.0) for s in sessions), 2),
        }

        now = datetime.now(timezone.utc)
        repository.create_intelligence_record(
            db,
            intelligence_type="cost_attribution",
            data_payload=costs,
            time_window_start=data.get("window_start", now),
            time_window_end=data.get("window_end", now),
        )
        db.commit()
        return costs

    def compute_utilization_patterns(self, data: dict, db: Session) -> dict:
        """Compute utilization patterns.

        Surfaces: idle time, peak demand windows, underutilized configurations.
        """
        sessions = data.get("sessions", [])
        capacity = data.get("capacity", {})

        hour_counts = Counter()
        for s in sessions:
            ts = s.get("started_at", "")
            if ts and len(ts) >= 13:
                try:
                    hour = int(ts[11:13])
                    hour_counts[hour] += 1
                except (ValueError, IndexError):
                    pass

        peak_hours = hour_counts.most_common(3)
        total_hours = capacity.get("total_hours", 24 * 7)
        active_hours = len([h for h in hour_counts if hour_counts[h] > 0])
        idle_hours = max(0, total_hours - active_hours)

        hw_usage = Counter(s.get("hardware_config", "") for s in sessions if s.get("hardware_config"))
        all_configs = set(capacity.get("configurations", []))
        used_configs = set(hw_usage.keys())
        underutilized = list(all_configs - used_configs)

        patterns = {
            "idle_time_hours": idle_hours,
            "peak_demand_windows": [{"hour": h, "count": c} for h, c in peak_hours],
            "underutilized_configs": underutilized,
            "active_hours": active_hours,
            "total_sessions": len(sessions),
        }

        now = datetime.now(timezone.utc)
        repository.create_intelligence_record(
            db,
            intelligence_type="utilization_pattern",
            data_payload=patterns,
            time_window_start=data.get("window_start", now),
            time_window_end=data.get("window_end", now),
        )
        db.commit()
        return patterns

    def compute_routing_intelligence(self, data: dict, db: Session) -> dict:
        """Compute routing intelligence for Deepfield's static routing policy.

        Surfaces: which workload types consistently route to Gaudi vs Xeon6,
        feeding Deepfield before adaptive calibration has history.
        """
        routing_history = data.get("routing_history", [])

        gaudi_workloads = [r for r in routing_history if r.get("substrate") == "gaudi"]
        xeon6_workloads = [r for r in routing_history if r.get("substrate") == "xeon6"]
        cpu_workloads = [r for r in routing_history if r.get("substrate") == "cpu"]

        gaudi_types = Counter(r.get("workload_type", "") for r in gaudi_workloads)
        xeon6_types = Counter(r.get("workload_type", "") for r in xeon6_workloads)

        routing = {
            "gaudi_workloads": [{"type": t, "count": c} for t, c in gaudi_types.most_common(10)],
            "xeon6_workloads": [{"type": t, "count": c} for t, c in xeon6_types.most_common(10)],
            "cpu_workloads_count": len(cpu_workloads),
            "total_routed": len(routing_history),
        }

        now = datetime.now(timezone.utc)
        repository.create_intelligence_record(
            db,
            intelligence_type="routing_intelligence",
            data_payload=routing,
            time_window_start=data.get("window_start", now),
            time_window_end=data.get("window_end", now),
        )
        db.commit()
        return routing
