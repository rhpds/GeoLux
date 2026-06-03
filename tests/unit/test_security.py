"""Unit tests for security module."""

from __future__ import annotations

import pytest

from api.security import (
    sanitize_string,
    validate_json_depth,
    validate_evidence_bundle,
    compute_audit_hash,
    verify_audit_chain,
    AuthenticatedUser,
)


class TestInputSanitization:
    def test_strips_script_tags(self):
        result = sanitize_string('<script>alert("xss")</script>')
        assert "<script" not in result.lower()

    def test_strips_javascript_protocol(self):
        result = sanitize_string('javascript:alert(1)')
        assert "javascript:" not in result.lower()

    def test_strips_event_handlers(self):
        result = sanitize_string('onload=alert(1)')
        assert "onload=" not in result.lower()

    def test_strips_sql_injection_drop(self):
        result = sanitize_string("'; DROP TABLE users; --")
        assert "DROP TABLE" not in result.upper()

    def test_strips_sql_injection_union(self):
        result = sanitize_string("' UNION SELECT * FROM passwords")
        assert "UNION SELECT" not in result.upper()

    def test_strips_sql_injection_or(self):
        result = sanitize_string("' OR '1'='1")
        assert "OR '1'='1" not in result

    def test_strips_eval(self):
        result = sanitize_string("eval(document.cookie)")
        assert "eval(" not in result.lower()

    def test_truncates_long_strings(self):
        long_str = "a" * 20000
        result = sanitize_string(long_str)
        assert len(result) <= 10000

    def test_preserves_safe_strings(self):
        safe = "cpu_percent is 85.5 for cluster-a"
        assert sanitize_string(safe) == safe

    def test_preserves_json_content(self):
        json_str = '{"key": "value", "count": 42}'
        assert sanitize_string(json_str) == json_str


class TestJsonDepthValidation:
    def test_shallow_json_passes(self):
        assert validate_json_depth({"a": {"b": "c"}}) is True

    def test_deeply_nested_json_fails(self):
        obj = "leaf"
        for _ in range(15):
            obj = {"nested": obj}
        assert validate_json_depth(obj) is False

    def test_flat_list_passes(self):
        assert validate_json_depth([1, 2, 3, 4, 5]) is True

    def test_deeply_nested_list_fails(self):
        obj = [1]
        for _ in range(15):
            obj = [obj]
        assert validate_json_depth(obj) is False

    def test_scalar_passes(self):
        assert validate_json_depth(42) is True
        assert validate_json_depth("hello") is True
        assert validate_json_depth(None) is True


class TestEvidenceBundleValidation:
    def test_sanitizes_string_values(self):
        bundle = {"log": '<script>alert("xss")</script>'}
        result = validate_evidence_bundle(bundle)
        assert "<script" not in result["log"].lower()

    def test_preserves_numeric_values(self):
        bundle = {"cpu": 85.5, "count": 42}
        result = validate_evidence_bundle(bundle)
        assert result["cpu"] == 85.5
        assert result["count"] == 42

    def test_rejects_too_deep(self):
        obj = {"a": "b"}
        for _ in range(15):
            obj = {"nested": obj}
        with pytest.raises(Exception):
            validate_evidence_bundle(obj)


class TestAuditHashChain:
    def test_hash_is_deterministic(self):
        h1 = compute_audit_hash("evt-1", "payload-1", "")
        h2 = compute_audit_hash("evt-1", "payload-1", "")
        assert h1 == h2

    def test_hash_changes_with_input(self):
        h1 = compute_audit_hash("evt-1", "payload-1", "")
        h2 = compute_audit_hash("evt-2", "payload-1", "")
        assert h1 != h2

    def test_hash_chains(self):
        h1 = compute_audit_hash("evt-1", "p1", "")
        h2 = compute_audit_hash("evt-2", "p2", h1)
        h3 = compute_audit_hash("evt-3", "p3", h2)
        assert h1 != h2 != h3

    def test_verify_valid_chain(self):
        events = []
        prev = ""
        for i in range(5):
            eid = f"evt-{i}"
            payload = f"payload-{i}"
            h = compute_audit_hash(eid, payload, prev)
            events.append({"event_id": eid, "payload_reference": payload, "hash": h})
            prev = h
        assert verify_audit_chain(events) is True


class TestAuthenticatedUser:
    def test_admin_with_admin_role(self):
        user = AuthenticatedUser("u1", roles=["geolux-admin"], auth_method="oidc")
        assert user.is_admin is True

    def test_admin_with_api_key(self):
        user = AuthenticatedUser("api-key-user", auth_method="api_key")
        assert user.is_admin is True

    def test_non_admin(self):
        user = AuthenticatedUser("u2", roles=["viewer"], auth_method="oidc")
        assert user.is_admin is False

    def test_platform_admin_role(self):
        user = AuthenticatedUser("u3", roles=["platform-admin"], auth_method="proxy")
        assert user.is_admin is True


class TestSecurityHeaders:
    def test_security_headers_present(self, client):
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers
        assert response.headers.get("Cache-Control") == "no-store"
        assert "Permissions-Policy" in response.headers

    def test_cors_headers(self, client):
        response = client.options("/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        assert response.status_code in (200, 405)
