"""Integration tests for PIIS UI-9 Settings & Configuration Workspace endpoints.

Comprehensive test suite verifying:
1. Authorization enforcement: 401 on unauthenticated access.
2. System info metadata retrieval with valid claims.
3. Locked operational boundaries (all mutation flags False).
4. Secret redaction across settings payloads.
5. Immutability protection: 405 on POST/PUT/DELETE/PATCH mutations.
6. NOC factory defaults retrieval.
7. Grounded documentation catalog paths.
8. Zero side effects on repeated GET calls.
9. Zero subprocess execution.
10. Zero external network egress.
"""

from __future__ import annotations

import re
import socket
import subprocess
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient

from piis.api.app import app
from piis.auth import ApplicationRole, AuthManager


@pytest.fixture
def auth_manager():
    return AuthManager()


@pytest.fixture
def auth_headers_operator(auth_manager):
    """Network operator with VIEW_INCIDENTS permission."""
    token = auth_manager.mint_dev_token(
        principal_id="noc-operator-01",
        role=ApplicationRole.NOC_L1,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Authorization Enforcement (401 on Unauthenticated Access)
# ---------------------------------------------------------------------------

def test_settings_unauthenticated_access_denied(test_client):
    """Verify settings endpoints return 401 when no token is provided."""
    endpoints = [
        "/api/v1/settings/system-info",
        "/api/v1/settings/preferences-defaults",
    ]
    for ep in endpoints:
        resp = test_client.get(ep)
        assert resp.status_code == 401, f"Endpoint {ep} must require authentication"


# ---------------------------------------------------------------------------
# 2. System Info Grounded Metadata Retrieval
# ---------------------------------------------------------------------------

def test_settings_system_info_grounded_metadata(test_client, auth_headers_operator):
    """Verify system info returns grounded, accurate metadata."""
    resp = test_client.get("/api/v1/settings/system-info", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()

    assert data["application_name"] == "Production Incident Intelligence System"
    assert data["application_edition"] == "Telecom Edition (Portfolio Release)"
    assert data["core_version"] == "1.0.0-rc2"
    assert data["api_version"] == "1.0.0"
    assert data["active_milestone"] == "PRODUCTION_READY"
    assert data["operational_mode"] == "read_only_decision_support"
    assert data["auth_mode"] == "IN_MEMORY_JWT_OIDC"
    assert data["rbac_enforced"] is True
    assert data["service_principals_barred"] is True
    assert set(data["telecom_domains"]) == {"RAN", "Transport", "Core", "IMS", "Cloud"}
    assert data["epistemic_classification"] == "VERIFIED_CONFIGURATION"


# ---------------------------------------------------------------------------
# 3. Locked Operational Boundaries
# ---------------------------------------------------------------------------

def test_settings_locked_operational_boundaries(test_client, auth_headers_operator):
    """Verify all operational boundary flags confirm strictly read-only execution."""
    resp = test_client.get("/api/v1/settings/system-info", headers=auth_headers_operator)
    assert resp.status_code == 200
    boundaries = resp.json()["operational_boundaries"]

    assert boundaries["network_mutations_allowed"] is False
    assert boundaries["production_commands_allowed"] is False
    assert boundaries["ticket_closures_allowed"] is False
    assert boundaries["external_egress_allowed"] is False
    assert boundaries["autonomous_remediation_allowed"] is False
    assert boundaries["secret_exposure_allowed"] is False


# ---------------------------------------------------------------------------
# 4. Secret Redaction (Zero Credentials Exposed)
# ---------------------------------------------------------------------------

def test_settings_secret_redaction(test_client, auth_headers_operator):
    """Verify responses do not leak HMAC keys, private keys, or passwords."""
    endpoints = [
        "/api/v1/settings/system-info",
        "/api/v1/settings/preferences-defaults",
    ]
    secret_patterns = [
        re.compile(r"-----BEGIN PRIVATE KEY-----", re.IGNORECASE),
        re.compile(r"-----BEGIN RSA PRIVATE KEY-----", re.IGNORECASE),
        re.compile(r"ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*"),
        re.compile(r"api[_-]?key", re.IGNORECASE),
    ]

    for ep in endpoints:
        resp = test_client.get(ep, headers=auth_headers_operator)
        assert resp.status_code == 200
        text = resp.text
        for pattern in secret_patterns:
            matches = pattern.findall(text)
            # Ensure no live bearer tokens or PEM private keys leaked in body
            assert len(matches) == 0, f"Potential credential leak at {ep}: {matches}"


# ---------------------------------------------------------------------------
# 5. Immutability Protection (405 on Mutations)
# ---------------------------------------------------------------------------

def test_settings_immutability_method_protection(test_client, auth_headers_operator):
    """Verify settings endpoints reject all mutation methods."""
    endpoints = [
        "/api/v1/settings/system-info",
        "/api/v1/settings/preferences-defaults",
    ]
    mutation_payload = {"theme": "light", "network_mutations_allowed": True}

    for ep in endpoints:
        assert test_client.post(ep, json=mutation_payload, headers=auth_headers_operator).status_code == 405
        assert test_client.put(ep, json=mutation_payload, headers=auth_headers_operator).status_code == 405
        assert test_client.patch(ep, json=mutation_payload, headers=auth_headers_operator).status_code == 405
        assert test_client.delete(ep, headers=auth_headers_operator).status_code == 405


# ---------------------------------------------------------------------------
# 6. NOC Factory Preferences Defaults
# ---------------------------------------------------------------------------

def test_settings_preferences_defaults(test_client, auth_headers_operator):
    """Verify factory defaults align with NOC standards."""
    resp = test_client.get("/api/v1/settings/preferences-defaults", headers=auth_headers_operator)
    assert resp.status_code == 200
    defaults = resp.json()

    assert defaults["theme"] == "dark"
    assert defaults["density"] == "comfortable"
    assert defaults["timezone"] == "UTC"
    assert defaults["time_format"] == "24H"
    assert defaults["page_size"] == 25
    assert defaults["refresh_interval_seconds"] == 30
    assert defaults["persistence_target"] == "localStorage"
    assert defaults["epistemic_classification"] == "NOC_FACTORY_DEFAULTS"


# ---------------------------------------------------------------------------
# 7. Documentation Catalog Grounding
# ---------------------------------------------------------------------------

def test_settings_documentation_catalog_grounding(test_client, auth_headers_operator):
    """Verify documentation catalog links reflect real docs."""
    resp = test_client.get("/api/v1/settings/system-info", headers=auth_headers_operator)
    assert resp.status_code == 200
    docs = resp.json()["documentation_catalog"]
    assert len(docs) >= 3

    paths = [d["path"] for d in docs]
    assert any("UI8_1" in p for p in paths)
    assert any("UI9" in p for p in paths)


# ---------------------------------------------------------------------------
# 8. GET Idempotency & Zero Side Effects
# ---------------------------------------------------------------------------

def test_settings_get_idempotency_zero_side_effects(test_client, auth_headers_operator):
    """Verify repeated GET requests cause zero state changes."""
    r1 = test_client.get("/api/v1/settings/system-info", headers=auth_headers_operator).json()
    r2 = test_client.get("/api/v1/settings/system-info", headers=auth_headers_operator).json()
    assert r1 == r2


# ---------------------------------------------------------------------------
# 9. Zero Subprocess Execution
# ---------------------------------------------------------------------------

def test_settings_zero_subprocess_execution(test_client, auth_headers_operator):
    """Verify settings endpoints invoke zero OS subprocesses."""
    with patch.object(subprocess, "Popen", side_effect=AssertionError("Subprocess forbidden")):
        resp = test_client.get("/api/v1/settings/system-info", headers=auth_headers_operator)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 10. Zero External Network Egress
# ---------------------------------------------------------------------------

def test_settings_zero_external_network_egress(test_client, auth_headers_operator):
    """Verify settings endpoints make zero outbound socket connections."""
    def guarded_connection(*args, **kwargs):
        raise AssertionError("Outbound network connection forbidden in read-only settings")

    with patch.object(socket, "create_connection", side_effect=guarded_connection):
        resp = test_client.get("/api/v1/settings/system-info", headers=auth_headers_operator)
        assert resp.status_code == 200
