"""Kafka replay engine for deterministic event sequence replay.

Records real event sequences to named archives and replays them
at configurable speeds. Supports pause/inspect and ground truth comparison.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("geolux.replay")

_ARCHIVE_DIR = Path(os.environ.get("GEOLUX_REPLAY_DIR", "replay-archives"))


class KafkaReplayEngine:
    def __init__(self):
        self._running = False
        self._paused = False
        self._current_offset = 0
        self._thread: Optional[threading.Thread] = None
        self._archive_data: list[dict] = []
        self._results: list[dict] = []
        self._lock = threading.Lock()

    def record(self, topic: str, output_archive: str, duration_seconds: int = 300) -> dict:
        """Record real events from a Kafka topic to a named archive."""
        _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        archive_path = _ARCHIVE_DIR / f"{output_archive}.jsonl"

        brokers = os.environ.get("GEOLUX_KAFKA_BROKERS", "")
        if not brokers:
            return {"status": "error", "reason": "Kafka not configured"}

        try:
            from confluent_kafka import Consumer

            consumer = Consumer({
                "bootstrap.servers": brokers,
                "group.id": f"geolux-recorder-{output_archive}",
                "auto.offset.reset": "latest",
            })
            consumer.subscribe([topic])

            events = []
            start = time.time()

            while time.time() - start < duration_seconds:
                msg = consumer.poll(timeout=1.0)
                if msg is None or msg.error():
                    continue
                event = {
                    "offset": msg.offset(),
                    "timestamp": msg.timestamp()[1] if msg.timestamp() else int(time.time() * 1000),
                    "key": msg.key().decode("utf-8") if msg.key() else None,
                    "value": json.loads(msg.value().decode("utf-8")),
                }
                events.append(event)

            consumer.close()

            with open(archive_path, "w") as f:
                for e in events:
                    f.write(json.dumps(e, default=str) + "\n")

            return {
                "status": "recorded",
                "archive": output_archive,
                "events": len(events),
                "path": str(archive_path),
            }

        except ImportError:
            return {"status": "error", "reason": "confluent-kafka not installed"}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def start(
        self,
        archive_name: str,
        speed_multiplier: float = 1.0,
        pause_at_offset: Optional[int] = None,
    ) -> dict:
        """Replay a recorded archive at configurable speed."""
        archive_path = _ARCHIVE_DIR / f"{archive_name}.jsonl"

        if not archive_path.exists():
            return {"status": "error", "reason": f"Archive not found: {archive_name}"}

        with open(archive_path) as f:
            self._archive_data = [json.loads(line) for line in f if line.strip()]

        if not self._archive_data:
            return {"status": "error", "reason": "Archive is empty"}

        self._running = True
        self._paused = False
        self._current_offset = 0
        self._results = []

        self._thread = threading.Thread(
            target=self._replay_loop,
            args=(speed_multiplier, pause_at_offset),
            daemon=True,
        )
        self._thread.start()

        logger.info(
            "Replay started: %s (%d events, %sx speed)",
            archive_name, len(self._archive_data), speed_multiplier,
        )

        return {
            "status": "started",
            "archive_name": archive_name,
            "total_events": len(self._archive_data),
            "speed_multiplier": speed_multiplier,
        }

    def _replay_loop(self, speed: float, pause_at: Optional[int]):
        """Replay events with timing based on original timestamps."""
        prev_ts = None

        for i, event in enumerate(self._archive_data):
            if not self._running:
                break

            while self._paused:
                time.sleep(0.1)
                if not self._running:
                    return

            if pause_at is not None and i >= pause_at:
                self._paused = True
                logger.info("Replay paused at offset %d", i)
                while self._paused and self._running:
                    time.sleep(0.1)

            ts = event.get("timestamp", 0)
            if prev_ts is not None and ts > prev_ts:
                delay = (ts - prev_ts) / 1000.0 / max(speed, 0.01)
                if delay > 0:
                    time.sleep(min(delay, 10.0))
            prev_ts = ts

            with self._lock:
                self._current_offset = i
                self._results.append({
                    "offset": i,
                    "event_type": event.get("value", {}).get("event_type", "unknown"),
                    "replayed_at": time.time(),
                })

            self._publish_replay_event(event)

        self._running = False
        logger.info("Replay completed: %d events", len(self._results))

    def _publish_replay_event(self, event: dict):
        """Publish a replay event to the replay.scenario topic."""
        try:
            from events.publishers import publish_event
            publish_event("replay.scenario", event.get("value", event))
        except Exception as e:
            logger.debug("Replay publish skipped: %s", e)

    def pause(self) -> dict:
        """Pause the current replay."""
        self._paused = True
        return {
            "status": "paused",
            "current_offset": self._current_offset,
            "total_events": len(self._archive_data),
        }

    def resume(self) -> dict:
        """Resume a paused replay."""
        self._paused = False
        return {"status": "resumed", "current_offset": self._current_offset}

    def stop(self) -> dict:
        """Stop the current replay."""
        self._running = False
        return {
            "status": "stopped",
            "events_replayed": len(self._results),
        }

    def get_status(self) -> dict:
        """Get current replay status."""
        return {
            "running": self._running,
            "paused": self._paused,
            "current_offset": self._current_offset,
            "total_events": len(self._archive_data),
            "events_replayed": len(self._results),
        }

    def compare_ground_truth(
        self,
        replay_results: list[dict],
        ground_truth: list[dict],
    ) -> dict:
        """Compare system outputs during replay against ground truth.

        Returns match status and list of differences.
        """
        differences = []
        matched = 0
        total = min(len(replay_results), len(ground_truth))

        for i in range(total):
            actual = replay_results[i]
            expected = ground_truth[i]

            actual_outcome = actual.get("outcome", actual.get("result", ""))
            expected_outcome = expected.get("outcome", expected.get("result", ""))

            if actual_outcome == expected_outcome:
                matched += 1
            else:
                differences.append({
                    "index": i,
                    "expected": expected_outcome,
                    "actual": actual_outcome,
                    "event_type": expected.get("event_type", ""),
                })

        return {
            "match": len(differences) == 0,
            "total_compared": total,
            "matched": matched,
            "differences": differences,
            "match_rate": matched / max(total, 1),
        }
