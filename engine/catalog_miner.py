"""Catalog miner — reads Launchpad catalog for Deepfield routing intelligence.

Single GET request per hour. Read-only. Timeout: 10s.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.request
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db import repository

logger = logging.getLogger("geolux.catalog_miner")

LAUNCHPAD_API = os.environ.get("GEOLUX_LAUNCHPAD_API_URL", "")


def mine_catalog(db: Session) -> dict:
    """Fetch Launchpad catalog and extract routing intelligence.

    One GET request. Extracts:
    - Hardware profiles → Deepfield routing policy
    - Category distribution → demand signals
    - Capability requirements → complexity classification
    """
    if not LAUNCHPAD_API:
        return {"skipped": True, "reason": "no Launchpad API URL"}

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        url = f"{LAUNCHPAD_API.rstrip('/')}/api/v1/catalog"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            items = json.loads(resp.read())

        if not isinstance(items, list):
            items = items.get("items", items.get("catalog", []))

        if not items:
            return {"skipped": True, "reason": "empty catalog"}

        categories = Counter(i.get("category", "unknown") for i in items)
        hw_profiles = Counter(i.get("default_hardware_profile", "standard") for i in items)

        gaudi_items = [i for i in items if "gaudi" in str(i.get("required_capabilities", "")).lower() or "gpu" in str(i.get("default_hardware_profile", "")).lower()]
        xeon_items = [i for i in items if "xeon" in str(i.get("required_capabilities", "")).lower() or "intel" in str(i.get("default_hardware_profile", "")).lower()]
        cpu_items = [i for i in items if i not in gaudi_items and i not in xeon_items]

        now = datetime.now(timezone.utc)

        repository.create_intelligence_record(
            db,
            intelligence_type="catalog_analysis",
            data_payload={
                "total_items": len(items),
                "categories": dict(categories.most_common(10)),
                "hardware_profiles": dict(hw_profiles.most_common(10)),
                "gaudi_workloads": len(gaudi_items),
                "xeon_workloads": len(xeon_items),
                "cpu_workloads": len(cpu_items),
                "sample_gaudi": [i.get("display_name", "") for i in gaudi_items[:5]],
                "sample_xeon": [i.get("display_name", "") for i in xeon_items[:5]],
            },
            time_window_start=now,
            time_window_end=now,
        )

        repository.create_intelligence_record(
            db,
            intelligence_type="routing_intelligence",
            data_payload={
                "gaudi_workloads": [{"type": i.get("category", ""), "count": 1} for i in gaudi_items[:10]],
                "xeon6_workloads": [{"type": i.get("category", ""), "count": 1} for i in xeon_items[:10]],
                "cpu_workloads_count": len(cpu_items),
                "total_routed": len(items),
            },
            time_window_start=now,
            time_window_end=now,
        )

        db.commit()

        logger.info(
            "Catalog mined: %d items (%d gaudi, %d xeon, %d cpu), %d categories",
            len(items), len(gaudi_items), len(xeon_items), len(cpu_items), len(categories),
        )

        return {
            "total": len(items),
            "gaudi": len(gaudi_items),
            "xeon": len(xeon_items),
            "cpu": len(cpu_items),
            "categories": len(categories),
        }

    except Exception as e:
        logger.warning("Catalog mining failed: %s", e)
        return {"error": str(e)}
