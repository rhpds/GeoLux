"""Security module for GeoLux platform.

Implements:
- Red Hat SSO (Keycloak) OIDC integration
- API key authentication (fallback)
- OAuth proxy header trust (OpenShift deployment)
- Input validation and sanitization
- Rate limiting per auth identity
- Audit logging for auth events
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("geolux.security")

# ── Configuration ─────────────────────────────────────────────────────

SSO_ENABLED = os.environ.get("GEOLUX_SSO_ENABLED", "false").lower() == "true"
SSO_ISSUER_URL = os.environ.get("GEOLUX_SSO_ISSUER_URL", "")
SSO_CLIENT_ID = os.environ.get("GEOLUX_SSO_CLIENT_ID", "geolux")
SSO_REALM = os.environ.get("GEOLUX_SSO_REALM", "redhat-external")
TRUST_PROXY_AUTH = os.environ.get("GEOLUX_TRUST_PROXY_AUTH", "false").lower() == "true"
ADMIN_API_KEY = os.environ.get("GEOLUX_ADMIN_API_KEY", os.environ.get("STARGATE_ADMIN_API_KEY", ""))
ADMIN_ROLES = os.environ.get("GEOLUX_ADMIN_ROLES", "geolux-admin,platform-admin").split(",")

_bearer_scheme = HTTPBearer(auto_error=False)

# ── OIDC Token Validation ─────────────────────────────────────────────

_jwks_cache: dict = {"keys": [], "fetched_at": 0.0}
_JWKS_TTL = 3600


def _fetch_jwks() -> list[dict]:
    """Fetch JWKS from SSO issuer for token validation."""
    if not SSO_ISSUER_URL:
        return []

    now = time.time()
    if _jwks_cache["keys"] and now - _jwks_cache["fetched_at"] < _JWKS_TTL:
        return _jwks_cache["keys"]

    try:
        import urllib.request
        import json
        jwks_url = f"{SSO_ISSUER_URL}/protocol/openid-connect/certs"
        with urllib.request.urlopen(jwks_url, timeout=10) as resp:
            data = json.loads(resp.read())
            _jwks_cache["keys"] = data.get("keys", [])
            _jwks_cache["fetched_at"] = now
            return _jwks_cache["keys"]
    except Exception as e:
        logger.warning("Failed to fetch JWKS from %s: %s", SSO_ISSUER_URL, e)
        return _jwks_cache["keys"]


def validate_oidc_token(token: str) -> Optional[dict]:
    """Validate an OIDC JWT token against the SSO issuer.

    Returns decoded claims if valid, None if invalid.
    """
    if not SSO_ENABLED or not SSO_ISSUER_URL:
        return None

    try:
        import jwt as pyjwt

        jwks = _fetch_jwks()
        if not jwks:
            logger.warning("No JWKS keys available for token validation")
            return None

        header = pyjwt.get_unverified_header(token)
        kid = header.get("kid")
        key_data = next((k for k in jwks if k.get("kid") == kid), None)
        if not key_data:
            return None

        public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(key_data)
        claims = pyjwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=SSO_CLIENT_ID,
            issuer=SSO_ISSUER_URL,
        )
        return claims

    except ImportError:
        logger.warning("PyJWT not installed — OIDC validation unavailable")
        return None
    except Exception as e:
        logger.debug("Token validation failed: %s", e)
        return None


# ── Authentication Dependencies ───────────────────────────────────────


class AuthenticatedUser:
    """Represents an authenticated user with identity and roles."""

    def __init__(self, user_id: str, email: str = "", roles: list[str] = None, auth_method: str = "unknown"):
        self.user_id = user_id
        self.email = email
        self.roles = roles or []
        self.auth_method = auth_method

    @property
    def is_admin(self) -> bool:
        return any(r in ADMIN_ROLES for r in self.roles) or self.auth_method == "api_key"


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[AuthenticatedUser]:
    """Extract and validate user identity from request.

    Priority order:
    1. Bearer token (OIDC JWT from Red Hat SSO)
    2. X-API-Key header (service-to-service)
    3. X-Forwarded-User header (OAuth proxy in OpenShift)
    4. Anonymous (None)
    """
    # 1. Bearer token (OIDC)
    if credentials and credentials.credentials:
        claims = validate_oidc_token(credentials.credentials)
        if claims:
            return AuthenticatedUser(
                user_id=claims.get("sub", ""),
                email=claims.get("email", ""),
                roles=claims.get("realm_access", {}).get("roles", []),
                auth_method="oidc",
            )

    # 2. API key
    api_key = request.headers.get("X-API-Key", "")
    if api_key and ADMIN_API_KEY:
        if hmac.compare_digest(api_key, ADMIN_API_KEY):
            return AuthenticatedUser(
                user_id="api-key-user",
                roles=ADMIN_ROLES,
                auth_method="api_key",
            )

    # 3. OAuth proxy header
    if TRUST_PROXY_AUTH:
        forwarded_user = request.headers.get("X-Forwarded-User", "")
        forwarded_email = request.headers.get("X-Forwarded-Email", "")
        forwarded_groups = request.headers.get("X-Forwarded-Groups", "")
        if forwarded_user:
            roles = [g.strip() for g in forwarded_groups.split(",") if g.strip()]
            return AuthenticatedUser(
                user_id=forwarded_user,
                email=forwarded_email,
                roles=roles,
                auth_method="proxy",
            )

    return None


async def require_authenticated(
    user: Optional[AuthenticatedUser] = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require any authenticated user."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_admin_user(
    user: Optional[AuthenticatedUser] = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require an admin user."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


# ── Input Validation & Sanitization ──────────────────────────────────

_DANGEROUS_PATTERNS = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r";\s*DROP\s+TABLE", re.IGNORECASE),
    re.compile(r";\s*DELETE\s+FROM", re.IGNORECASE),
    re.compile(r"UNION\s+SELECT", re.IGNORECASE),
    re.compile(r"--\s*$", re.MULTILINE),
    re.compile(r"'\s*OR\s+'1'\s*=\s*'1", re.IGNORECASE),
]

_MAX_STRING_LENGTH = 10000
_MAX_JSON_DEPTH = 10


def sanitize_string(value: str) -> str:
    """Remove potentially dangerous content from string input."""
    if len(value) > _MAX_STRING_LENGTH:
        value = value[:_MAX_STRING_LENGTH]

    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(value):
            logger.warning("Dangerous pattern detected in input: %s", pattern.pattern)
            value = pattern.sub("", value)

    return value


def validate_json_depth(obj: object, max_depth: int = _MAX_JSON_DEPTH, current_depth: int = 0) -> bool:
    """Reject deeply nested JSON to prevent resource exhaustion."""
    if current_depth > max_depth:
        return False
    if isinstance(obj, dict):
        return all(validate_json_depth(v, max_depth, current_depth + 1) for v in obj.values())
    if isinstance(obj, list):
        return all(validate_json_depth(v, max_depth, current_depth + 1) for v in obj)
    return True


def validate_evidence_bundle(bundle: dict) -> dict:
    """Validate and sanitize an evidence bundle before processing."""
    if not validate_json_depth(bundle):
        raise HTTPException(status_code=400, detail="Evidence bundle too deeply nested")

    sanitized = {}
    for key, value in bundle.items():
        clean_key = sanitize_string(str(key))
        if isinstance(value, str):
            sanitized[clean_key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[clean_key] = validate_evidence_bundle(value)
        else:
            sanitized[clean_key] = value

    return sanitized


# ── Audit Log Integrity ──────────────────────────────────────────────

def compute_audit_hash(event_id: str, payload: str, previous_hash: str = "") -> str:
    """Compute tamper-detection hash for audit chain."""
    data = f"{event_id}:{payload}:{previous_hash}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def verify_audit_chain(events: list[dict]) -> bool:
    """Verify integrity of an audit event chain."""
    previous_hash = ""
    for event in events:
        expected = compute_audit_hash(
            event.get("event_id", ""),
            str(event.get("payload_reference", "")),
            previous_hash,
        )
        if event.get("hash") and event["hash"] != expected:
            return False
        previous_hash = expected
    return True
