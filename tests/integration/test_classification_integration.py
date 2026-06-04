"""Integration tests for evidence-based constraint classification."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, set_engine
from db import repository
from constraints.loader import load_all_constraints, sync_constraints_to_db, load_constraint_file
from engine.classification import classify_evidence


@pytest.fixture
def cls_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    set_engine(engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


STAGES_DIR = Path(__file__).parent.parent.parent / "constraints" / "stages"


class TestConstraintLoader:
    def test_load_all_constraints_from_yaml(self):
        constraints = load_all_constraints(STAGES_DIR)
        assert len(constraints) > 0
        for c in constraints:
            assert "constraint_id" in c
            assert "constraint_name" in c
            assert "stage" in c
            assert "assertion_type" in c

    def test_load_cluster_health_file(self):
        path = STAGES_DIR / "cluster-health.yaml"
        constraints = load_constraint_file(path)
        assert len(constraints) == 4
        assert constraints[0]["constraint_id"] == "ch-001"
        assert constraints[0]["stage"] == "cluster-health"

    def test_sync_to_db_creates_records(self, cls_db):
        result = sync_constraints_to_db(cls_db, STAGES_DIR)
        assert result["total"] > 0
        assert result["created"] == result["total"]
        assert result["updated"] == 0

        records = repository.get_constraint_definitions(cls_db)
        assert len(records) == result["total"]

    def test_sync_idempotent(self, cls_db):
        sync_constraints_to_db(cls_db, STAGES_DIR)
        result2 = sync_constraints_to_db(cls_db, STAGES_DIR)
        assert result2["created"] == 0
        assert result2["unchanged"] == result2["total"]

    def test_all_stages_have_constraints(self):
        constraints = load_all_constraints(STAGES_DIR)
        stages = set(c["stage"] for c in constraints)
        expected_stages = {
            "cluster-health", "namespace-ready", "deployment-ready",
            "route-ready", "vm-runtime-ready", "run-created",
            "provision-complete", "storage-clone-ready", "smoke-test-ready",
            "showroom-healthy", "model-endpoint-ready",
        }
        assert stages == expected_stages


class TestClassifyEvidence:
    def test_classify_cluster_health_pass(self, cls_db):
        sync_constraints_to_db(cls_db, STAGES_DIR)

        result = classify_evidence({
            "evidence_bundle_id": "test-bundle-1",
            "evidence": {
                "outcome": "pass",
                "failure_class": "",
                "stage_id": "cluster-health",
                "lab_code": "test-lab",
                "cluster_name": "test-cluster",
            },
            "stage": "cluster-health",
        }, cls_db)

        assert result["overall_result"] == "pass"
        assert len(result["results"]) == 4

    def test_classify_cluster_health_fail(self, cls_db):
        sync_constraints_to_db(cls_db, STAGES_DIR)

        result = classify_evidence({
            "evidence_bundle_id": "test-bundle-2",
            "evidence": {
                "outcome": "fail",
                "failure_class": "pods_crashlooping",
                "stage_id": "cluster-health",
                "lab_code": "test-lab",
                "cluster_name": "test-cluster",
            },
            "stage": "cluster-health",
        }, cls_db)

        assert result["overall_result"] == "fail"
        fail_count = sum(1 for r in result["results"] if r["result"] == "fail")
        assert fail_count >= 1

    def test_classify_with_missing_evidence(self, cls_db):
        sync_constraints_to_db(cls_db, STAGES_DIR)

        result = classify_evidence({
            "evidence_bundle_id": "test-bundle-3",
            "evidence": {"outcome": "pass"},
            "stage": "cluster-health",
        }, cls_db)

        assert result["overall_result"] in ("inconclusive", "pass")
        inconclusive_count = sum(1 for r in result["results"] if r["result"] == "inconclusive")
        assert inconclusive_count >= 2

    def test_classify_persists_to_db(self, cls_db):
        sync_constraints_to_db(cls_db, STAGES_DIR)

        result = classify_evidence({
            "evidence_bundle_id": "persist-test",
            "evidence": {
                "outcome": "pass",
                "failure_class": "",
                "stage_id": "cluster-health",
            },
            "stage": "cluster-health",
        }, cls_db)

        for r in result["results"]:
            record = repository.get_classification(cls_db, r["classification_id"])
            assert record is not None
            assert record.evidence_bundle_id == "persist-test"

    def test_classify_creates_audit_trail(self, cls_db):
        sync_constraints_to_db(cls_db, STAGES_DIR)

        classify_evidence({
            "evidence_bundle_id": "audit-test",
            "evidence": {"outcome": "pass", "failure_class": ""},
            "stage": "cluster-health",
        }, cls_db)

        events = repository.get_audit_events(cls_db, source_component="classification-engine")
        assert len(events) >= 1
        assert any(e.event_type == "classification.started" for e in events)

    def test_classify_with_schema_version_mismatch(self, cls_db):
        sync_constraints_to_db(cls_db, STAGES_DIR)

        result = classify_evidence({
            "evidence_bundle_id": "version-test",
            "evidence": {"outcome": "pass", "failure_class": ""},
            "stage": "cluster-health",
            "schema_version": 999,
        }, cls_db)

        assert "error" in result
        assert result["error"] == "schema_version_mismatch"

    def test_classify_auto_loads_constraints(self, cls_db):
        result = classify_evidence({
            "evidence_bundle_id": "auto-load-test",
            "evidence": {
                "outcome": "pass",
                "failure_class": "",
                "stage_id": "cluster-health",
            },
            "stage": "cluster-health",
        }, cls_db)

        assert result["overall_result"] == "pass"

    def test_classify_specific_constraint_ids(self, cls_db):
        sync_constraints_to_db(cls_db, STAGES_DIR)

        result = classify_evidence({
            "evidence_bundle_id": "specific-test",
            "evidence": {"outcome": "pass", "failure_class": ""},
            "constraint_ids": ["ch-001"],
            "stage": "cluster-health",
        }, cls_db)

        assert len(result["results"]) == 1
        assert result["results"][0]["constraint_id"] == "ch-001"


class TestClassificationAPIEndpoints:
    def test_get_constraints_empty(self, client):
        response = client.get("/classify/constraints")
        assert response.status_code == 200

    def test_get_classification_not_found(self, client):
        response = client.get("/classify/classifications/nonexistent")
        assert response.status_code == 404
