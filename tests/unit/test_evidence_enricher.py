"""Unit tests for cross-system evidence enrichment."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from engine.evidence_enricher import (
    EvidenceEnricher,
    _payload_matches,
    _get_payload_field,
)


def _make_record(payload=None, **kwargs):
    """Create a minimal record-like object for testing."""
    obj = SimpleNamespace(
        event_id="evt-1",
        source_component="test",
        event_type="test.event",
        payload_reference=None,
        created_at=None,
        **kwargs,
    )
    if payload is not None:
        obj.payload = payload
    return obj


class TestPayloadMatches:
    def test_matching_dict_payload(self):
        record = _make_record(payload={"cluster_id": "c-1"})
        assert _payload_matches(record, "cluster_id", "c-1") is True

    def test_non_matching_dict_payload(self):
        record = _make_record(payload={"cluster_id": "c-2"})
        assert _payload_matches(record, "cluster_id", "c-1") is False

    def test_matching_string_payload(self):
        record = _make_record(payload=json.dumps({"cluster_id": "c-1"}))
        assert _payload_matches(record, "cluster_id", "c-1") is True

    def test_no_payload_attribute(self):
        record = _make_record()  # no payload attr
        assert _payload_matches(record, "cluster_id", "c-1") is False

    def test_malformed_payload(self):
        record = _make_record(payload="not-json")
        assert _payload_matches(record, "cluster_id", "c-1") is False

    def test_missing_field_in_payload(self):
        record = _make_record(payload={"other_field": "val"})
        assert _payload_matches(record, "cluster_id", "c-1") is False


class TestGetPayloadField:
    def test_dict_payload(self):
        record = _make_record(payload={"outcome": "pass"})
        assert _get_payload_field(record, "outcome") == "pass"

    def test_string_payload(self):
        record = _make_record(payload=json.dumps({"signal_type": "cpu_spike"}))
        assert _get_payload_field(record, "signal_type") == "cpu_spike"

    def test_no_payload_attribute(self):
        record = _make_record()
        assert _get_payload_field(record, "outcome") is None

    def test_missing_field(self):
        record = _make_record(payload={"other": "val"})
        assert _get_payload_field(record, "outcome") is None

    def test_malformed_string_payload(self):
        record = _make_record(payload="not-json")
        assert _get_payload_field(record, "outcome") is None


class TestEvidenceEnricherEmptyDB:
    @patch("engine.evidence_enricher.repository")
    def test_empty_db_returns_original_bundle(self, mock_repo):
        mock_repo.get_audit_events.return_value = []
        enricher = EvidenceEnricher(db=None)
        bundle = {
            "bundle_id": "b-1",
            "evidence_fields": {"namespace": "ns-1"},
        }
        result = enricher.enrich(bundle)
        assert "cross_system" not in result["evidence_fields"]

    @patch("engine.evidence_enricher.repository")
    def test_preserves_existing_fields(self, mock_repo):
        mock_repo.get_audit_events.return_value = []
        enricher = EvidenceEnricher(db=None)
        bundle = {
            "bundle_id": "b-1",
            "evidence_fields": {"namespace": "ns-1", "cpu": 80},
        }
        result = enricher.enrich(bundle)
        assert result["evidence_fields"]["namespace"] == "ns-1"
        assert result["evidence_fields"]["cpu"] == 80


class TestStargateEnrichment:
    @patch("engine.evidence_enricher.repository")
    def test_stargate_pass_rate(self, mock_repo):
        records = [
            _make_record(payload={"outcome": "pass", "failure_class": None}),
            _make_record(payload={"outcome": "pass", "failure_class": None}),
            _make_record(payload={"outcome": "fail", "failure_class": "timeout"}),
        ]
        mock_repo.get_audit_events.return_value = records
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {}}
        result = enricher.enrich(bundle)
        sg = result["evidence_fields"]["cross_system"]["stargate"]
        assert sg["recent_evaluations"] == 3
        assert sg["pass_rate"] == 0.67
        assert sg["last_outcome"] == "pass"

    @patch("engine.evidence_enricher.repository")
    def test_stargate_failure_classes(self, mock_repo):
        records = [
            _make_record(payload={"outcome": "fail", "failure_class": "timeout"}),
            _make_record(payload={"outcome": "fail", "failure_class": "oom"}),
            _make_record(payload={"outcome": "fail", "failure_class": "timeout"}),
        ]
        mock_repo.get_audit_events.return_value = records
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {}}
        result = enricher.enrich(bundle)
        sg = result["evidence_fields"]["cross_system"]["stargate"]
        assert set(sg["failure_classes"]) == {"timeout", "oom"}

    @patch("engine.evidence_enricher.repository")
    def test_stargate_cluster_filter(self, mock_repo):
        records = [
            _make_record(payload={"outcome": "pass", "cluster_id": "c-1"}),
            _make_record(payload={"outcome": "fail", "cluster_id": "c-2"}),
        ]
        mock_repo.get_audit_events.return_value = records
        enricher = EvidenceEnricher(db=None)
        bundle = {"cluster_id": "c-1", "evidence_fields": {}}
        result = enricher.enrich(bundle)
        sg = result["evidence_fields"]["cross_system"]["stargate"]
        # Should filter to only the c-1 record
        assert sg["recent_evaluations"] == 1
        assert sg["pass_rate"] == 1.0


class TestDeepfieldEnrichment:
    @patch("engine.evidence_enricher.repository")
    def test_deepfield_signal_types(self, mock_repo):
        records = [
            _make_record(payload={"signal_type": "cpu_spike", "category": "resource"}),
            _make_record(payload={"signal_type": "pod_crashloop", "category": "workload"}),
            _make_record(payload={"signal_type": "cpu_spike", "category": "resource"}),
        ]
        mock_repo.get_audit_events.return_value = records
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {}}
        result = enricher.enrich(bundle)
        df = result["evidence_fields"]["cross_system"]["deepfield"]
        assert df["recent_events"] == 3
        assert set(df["signal_types"]) == {"cpu_spike", "pod_crashloop"}
        assert set(df["rca_categories"]) == {"resource", "workload"}

    @patch("engine.evidence_enricher.repository")
    def test_deepfield_no_records(self, mock_repo):
        # First call (stargate) returns nothing, second call (deepfield) returns nothing
        mock_repo.get_audit_events.return_value = []
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {}}
        result = enricher.enrich(bundle)
        assert "cross_system" not in result["evidence_fields"]


class TestLaunchpadEnrichment:
    @patch("engine.evidence_enricher.repository")
    def test_launchpad_event_types(self, mock_repo):
        records = [
            _make_record(payload={"event_type": "provision.started"}),
            _make_record(payload={"event_type": "provision.completed"}),
            _make_record(payload={"event_type": "provision.started"}),
        ]
        mock_repo.get_audit_events.return_value = records
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {}}
        result = enricher.enrich(bundle)
        lp = result["evidence_fields"]["cross_system"]["launchpad"]
        assert lp["recent_events"] == 3
        assert set(lp["event_types"]) == {"provision.started", "provision.completed"}


class TestAllSourcesPopulated:
    @patch("engine.evidence_enricher.repository")
    def test_all_three_sources(self, mock_repo):
        def side_effect(db, source_component=None, limit=10):
            if source_component == "stargate":
                return [_make_record(payload={"outcome": "pass"})]
            elif source_component == "deepfield":
                return [_make_record(payload={"signal_type": "latency_spike", "category": "network"})]
            elif source_component == "launchpad":
                return [_make_record(payload={"event_type": "scale.up"})]
            return []

        mock_repo.get_audit_events.side_effect = side_effect
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {"namespace": "prod"}}
        result = enricher.enrich(bundle)
        cross = result["evidence_fields"]["cross_system"]
        assert "stargate" in cross
        assert "deepfield" in cross
        assert "launchpad" in cross
        # Original fields preserved
        assert result["evidence_fields"]["namespace"] == "prod"


class TestGracefulDegradation:
    @patch("engine.evidence_enricher.repository")
    def test_stargate_failure_skips_source(self, mock_repo):
        call_count = 0

        def side_effect(db, source_component=None, limit=10):
            nonlocal call_count
            call_count += 1
            if source_component == "stargate":
                raise RuntimeError("StarGate DB timeout")
            elif source_component == "deepfield":
                return [_make_record(payload={"signal_type": "mem_pressure", "category": "resource"})]
            elif source_component == "launchpad":
                return [_make_record(payload={"event_type": "deploy"})]
            return []

        mock_repo.get_audit_events.side_effect = side_effect
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {}}
        result = enricher.enrich(bundle)
        cross = result["evidence_fields"]["cross_system"]
        assert "stargate" not in cross
        assert "deepfield" in cross
        assert "launchpad" in cross

    @patch("engine.evidence_enricher.repository")
    def test_all_sources_fail_no_cross_system(self, mock_repo):
        mock_repo.get_audit_events.side_effect = RuntimeError("DB down")
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {"status": "running"}}
        result = enricher.enrich(bundle)
        assert "cross_system" not in result["evidence_fields"]
        assert result["evidence_fields"]["status"] == "running"

    @patch("engine.evidence_enricher.repository")
    def test_deepfield_failure_skips_source(self, mock_repo):
        def side_effect(db, source_component=None, limit=10):
            if source_component == "stargate":
                return [_make_record(payload={"outcome": "fail", "failure_class": "crashloop"})]
            elif source_component == "deepfield":
                raise ConnectionError("DeepField unreachable")
            elif source_component == "launchpad":
                return []
            return []

        mock_repo.get_audit_events.side_effect = side_effect
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {}}
        result = enricher.enrich(bundle)
        cross = result["evidence_fields"]["cross_system"]
        assert "stargate" in cross
        assert "deepfield" not in cross
        assert "launchpad" not in cross


class TestEdgeCases:
    @patch("engine.evidence_enricher.repository")
    def test_missing_evidence_fields_key(self, mock_repo):
        """Bundle without evidence_fields gets an empty dict created."""
        mock_repo.get_audit_events.return_value = []
        enricher = EvidenceEnricher(db=None)
        bundle = {"bundle_id": "b-1"}
        result = enricher.enrich(bundle)
        assert "evidence_fields" in result
        assert isinstance(result["evidence_fields"], dict)

    @patch("engine.evidence_enricher.repository")
    def test_cluster_id_from_evidence_fields(self, mock_repo):
        """cluster_id falls back to evidence_fields when not at top level."""
        records = [
            _make_record(payload={"outcome": "pass", "cluster_id": "c-from-fields"}),
            _make_record(payload={"outcome": "fail", "cluster_id": "c-other"}),
        ]
        mock_repo.get_audit_events.return_value = records
        enricher = EvidenceEnricher(db=None)
        bundle = {"evidence_fields": {"cluster_id": "c-from-fields"}}
        result = enricher.enrich(bundle)
        sg = result["evidence_fields"]["cross_system"]["stargate"]
        assert sg["recent_evaluations"] == 1
