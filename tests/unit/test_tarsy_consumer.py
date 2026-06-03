"""Unit tests for TARSy investigation result consumer."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from events.consumers import (
    _handle_tarsy_investigation_completed,
    _extract_max_confidence,
)


def _make_completed_message(**overrides):
    """Build a minimal completed TARSy investigation message."""
    payload = {
        "tarsy_session_id": "sess-001",
        "source": "deepfield",
        "status": "completed",
        "originator_id": "orig-42",
        "root_causes": [
            {"description": "memory pressure", "confidence": "high"},
            {"description": "noisy neighbour", "confidence": "medium"},
        ],
        "recommended_actions": [
            {"action": "scale-up", "target": "node-7"},
        ],
        "executive_summary": "GPU cluster under memory pressure",
        "investigation_gaps": [],
        "score": 0.87,
    }
    payload.update(overrides)
    return {
        "trace_id": "trace-abc",
        "payload": payload,
    }


class TestExtractMaxConfidence:
    def test_high_confidence(self):
        causes = [{"confidence": "high"}, {"confidence": "low"}]
        assert _extract_max_confidence(causes) == 0.9

    def test_medium_confidence(self):
        causes = [{"confidence": "medium"}]
        assert _extract_max_confidence(causes) == 0.6

    def test_low_confidence(self):
        causes = [{"confidence": "low"}]
        assert _extract_max_confidence(causes) == 0.3

    def test_empty_list(self):
        assert _extract_max_confidence([]) == 0.0

    def test_missing_confidence_defaults_to_low(self):
        causes = [{"description": "unknown"}]
        assert _extract_max_confidence(causes) == 0.3


class TestHandleTarsyInvestigationCompleted:
    def test_skips_non_completed_status(self):
        msg = _make_completed_message(status="in_progress")
        # Should return early without touching hypothesis engine or audit
        _handle_tarsy_investigation_completed(msg)

    def test_skips_empty_status(self):
        msg = _make_completed_message(status="")
        _handle_tarsy_investigation_completed(msg)

    @patch("events.publishers.publish_audit_event")
    @patch("engine.hypothesis.generate_hypotheses")
    @patch("db.database.get_db")
    def test_builds_correct_evidence_bundle(self, mock_get_db, mock_gen, mock_audit):
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_gen.return_value = {"total": 2, "gated": False}

        msg = _make_completed_message()
        _handle_tarsy_investigation_completed(msg)

        mock_gen.assert_called_once()
        bundle = mock_gen.call_args[0][0]
        assert bundle["bundle_id"] == "tarsy-sess-001"
        assert bundle["source"] == "tarsy"
        assert bundle["trace_id"] == "trace-abc"
        assert bundle["evidence_fields"]["confidence"] == 0.9
        assert bundle["evidence_fields"]["originating_source"] == "deepfield"
        assert bundle["evidence_fields"]["originator_id"] == "orig-42"
        assert bundle["evidence_fields"]["score"] == 0.87
        assert len(bundle["evidence_fields"]["recommended_actions"]) == 1
        assert len(bundle["evidence_fields"]["root_causes"]) == 2

    @patch("events.publishers.publish_audit_event")
    @patch("engine.hypothesis.generate_hypotheses")
    @patch("db.database.get_db")
    def test_calls_generate_hypotheses_with_db(self, mock_get_db, mock_gen, mock_audit):
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_gen.return_value = {"total": 1, "gated": True}

        msg = _make_completed_message()
        _handle_tarsy_investigation_completed(msg)

        mock_gen.assert_called_once()
        assert mock_gen.call_args[0][1] is mock_db
        mock_db.close.assert_called_once()

    @patch("events.publishers.publish_audit_event")
    @patch("engine.hypothesis.generate_hypotheses")
    @patch("db.database.get_db")
    def test_publishes_audit_event(self, mock_get_db, mock_gen, mock_audit):
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_gen.return_value = {"total": 0, "gated": False}

        msg = _make_completed_message()
        _handle_tarsy_investigation_completed(msg)

        mock_audit.assert_called_once()
        audit = mock_audit.call_args[0][0]
        assert audit["source_component"] == "tarsy-governance"
        assert audit["event_type"] == "tarsy.investigation.governed"
        assert audit["tarsy_session_id"] == "sess-001"
        assert audit["trace_id"] == "trace-abc"
        assert audit["source"] == "deepfield"
        assert audit["originator_id"] == "orig-42"
        assert audit["actions_count"] == 1
        assert audit["root_causes_count"] == 2

    @patch("events.publishers.publish_audit_event", side_effect=Exception("kafka down"))
    @patch("engine.hypothesis.generate_hypotheses")
    @patch("db.database.get_db")
    def test_audit_failure_does_not_raise(self, mock_get_db, mock_gen, mock_audit):
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])
        mock_gen.return_value = {"total": 0, "gated": False}

        msg = _make_completed_message()
        # Should not raise despite audit publish failure
        _handle_tarsy_investigation_completed(msg)

    @patch("events.publishers.publish_audit_event")
    @patch("engine.hypothesis.generate_hypotheses", side_effect=Exception("db error"))
    @patch("db.database.get_db")
    def test_hypothesis_failure_does_not_raise(self, mock_get_db, mock_gen, mock_audit):
        mock_db = MagicMock()
        mock_get_db.return_value = iter([mock_db])

        msg = _make_completed_message()
        # Should not raise despite hypothesis generation failure
        _handle_tarsy_investigation_completed(msg)
