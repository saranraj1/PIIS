"""Integration tests for PIIS UI-7 Integrations Workspace endpoints.

Verifies:
1. Authentication & RBAC protection on all integration workspace endpoints.
2. Registry listing with category, status, and search filters.
3. Summary metrics accuracy (total, available, degraded, simulated vs reference).
4. Pipeline data flow topology (8 stages, 7 directed edges, epistemic badges).
5. Integration activity stream pagination, filtering, and event recording.
6. Single integration detail endpoint with complete secret omission and read-only boundaries.
7. Single adapter health retrieval and 404 handling.
8. Read-only non-mutation invariant across all GET requests.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from piis.api.app import app
from piis.api.routers.incidents import get_pipeline
from piis.auth import ApplicationRole, AuthManager
from piis.integrations.contracts import HealthState, IngestionEnvelope


@pytest.fixture
def auth_manager():
    return AuthManager()


@pytest.fixture
def auth_headers_operator(auth_manager):
    """Network operator with VIEW_INCIDENTS permission."""
    token = auth_manager.mint_dev_token(
        principal_id="test-operator",
        role=ApplicationRole.NOC_L1,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_admin(auth_manager):
    """PIIS admin with full administration permissions."""
    token = auth_manager.mint_dev_token(
        principal_id="test-admin",
        role=ApplicationRole.PIIS_ADMIN,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_client():
    """FastAPI test client."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Authentication & RBAC Protection
# ---------------------------------------------------------------------------

def test_unauthenticated_requests_rejected(test_client):
    """Unauthenticated calls to all workspace endpoints must return 401."""
    endpoints = [
        "/api/v1/integrations",
        "/api/v1/integrations/summary",
        "/api/v1/integrations/data-flow",
        "/api/v1/integrations/activity",
        "/api/v1/integrations/health",
        "/api/v1/integrations/ITSM-SERVICENOW-01",
        "/api/v1/integrations/ITSM-SERVICENOW-01/health",
    ]
    for ep in endpoints:
        resp = test_client.get(ep)
        assert resp.status_code == 401, f"Expected 401 for unauthenticated {ep}, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 2. Registry Listing & Filtering
# ---------------------------------------------------------------------------

def test_list_integrations_all(test_client, auth_headers_operator):
    """Listing integrations returns all 6 registered adapters."""
    resp = test_client.get("/api/v1/integrations", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 6

    adapter_ids = {item["integration_id"] for item in data}
    expected_ids = {
        "ITSM-SERVICENOW-01",
        "ITSM-JIRA-01",
        "ITSM-GENERIC-01",
        "TELEM-PROM-01",
        "TELEM-OTLP-01",
        "ALARM-OSS-01",
    }
    assert expected_ids.issubset(adapter_ids)

    # Verify no LIVE connection mode is ever advertised
    for item in data:
        assert item["connection_mode"] in {"LOCAL SIMULATION", "REFERENCE IMPLEMENTATION"}
        assert "LIVE" not in item["connection_mode"]
        assert item["data_direction"] == "INBOUND_ONLY"
        assert item["operational_status"] in {"AVAILABLE", "DEGRADED", "UNAVAILABLE"}


def test_list_integrations_filter_by_category(test_client, auth_headers_operator):
    """Filter integrations by category (ITSM, TELEMETRY, OSS_NMS_ALARM)."""
    # Category: ITSM
    resp_itsm = test_client.get("/api/v1/integrations?category=ITSM", headers=auth_headers_operator)
    assert resp_itsm.status_code == 200
    data_itsm = resp_itsm.json()
    assert len(data_itsm) == 3
    for it in data_itsm:
        assert it["category"] == "ITSM"

    # Category: TELEMETRY
    resp_telem = test_client.get("/api/v1/integrations?category=TELEMETRY", headers=auth_headers_operator)
    assert resp_telem.status_code == 200
    data_telem = resp_telem.json()
    assert len(data_telem) == 2
    for it in data_telem:
        assert it["category"] == "TELEMETRY"

    # Category: OSS_NMS_ALARM
    resp_alarm = test_client.get("/api/v1/integrations?category=OSS_NMS_ALARM", headers=auth_headers_operator)
    assert resp_alarm.status_code == 200
    data_alarm = resp_alarm.json()
    assert len(data_alarm) == 1
    assert data_alarm[0]["category"] == "OSS_NMS_ALARM"


def test_list_integrations_search_filter(test_client, auth_headers_operator):
    """Case-insensitive search across adapter fields."""
    resp = test_client.get("/api/v1/integrations?search=servicenow", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["integration_id"] == "ITSM-SERVICENOW-01"

    resp2 = test_client.get("/api/v1/integrations?search=prometheus", headers=auth_headers_operator)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) == 1
    assert data2[0]["integration_id"] == "TELEM-PROM-01"


# ---------------------------------------------------------------------------
# 3. Summary Endpoint
# ---------------------------------------------------------------------------

def test_get_integrations_summary(test_client, auth_headers_operator):
    """Integrations summary returns valid aggregate operational counts."""
    resp = test_client.get("/api/v1/integrations/summary", headers=auth_headers_operator)
    assert resp.status_code == 200
    summary = resp.json()

    assert summary["total_adapters"] >= 6
    assert summary["available_count"] + summary["degraded_count"] + summary["unavailable_count"] == summary["total_adapters"]
    assert summary["simulated_count"] + summary["reference_count"] == summary["total_adapters"]
    assert summary["overall_readiness"] in {"OPERATIONAL", "DEGRADED"}
    assert summary["epistemic_status"] == "REFERENCE_DATA"
    assert "ITSM" in summary["categories_breakdown"]
    assert "TELEMETRY" in summary["categories_breakdown"]
    assert "OSS_NMS_ALARM" in summary["categories_breakdown"]
    assert summary["total_dlq_count"] >= 0
    assert summary["total_ingested_events"] >= 0


# ---------------------------------------------------------------------------
# 4. Pipeline Data Flow Topology
# ---------------------------------------------------------------------------

def test_get_data_flow_topology(test_client, auth_headers_operator):
    """Data flow topology returns exactly 8 ordered stages and valid edges."""
    resp = test_client.get("/api/v1/integrations/data-flow", headers=auth_headers_operator)
    assert resp.status_code == 200
    flow = resp.json()

    stages = flow["stages"]
    assert len(stages) == 8

    # Verify stage ordering and identifiers
    expected_stages = [
        "STAGE_SOURCES",
        "STAGE_ADAPTERS",
        "STAGE_SECURITY",
        "STAGE_NORMALIZATION",
        "STAGE_DEDUPLICATION",
        "STAGE_DLQ",
        "STAGE_PROVENANCE",
        "STAGE_REVIEW",
    ]
    actual_stage_ids = [s["stage_id"] for s in stages]
    assert actual_stage_ids == expected_stages

    # Verify stage 1 is simulated and others are non-simulated
    assert stages[0]["is_simulated"] is True
    for s in stages[1:]:
        assert s["is_simulated"] is False

    # Verify edges
    edges = flow["edges"]
    assert len(edges) == 7
    source_targets = {(e["source"], e["target"]) for e in edges}
    assert ("STAGE_SOURCES", "STAGE_ADAPTERS") in source_targets
    assert ("STAGE_ADAPTERS", "STAGE_SECURITY") in source_targets
    assert ("STAGE_PROVENANCE", "STAGE_REVIEW") in source_targets


# ---------------------------------------------------------------------------
# 5. Activity Stream & Ingestion Tracking
# ---------------------------------------------------------------------------

def test_list_integration_activity(test_client, auth_headers_operator):
    """Activity stream returns paginated items with valid metadata."""
    resp = test_client.get("/api/v1/integrations/activity?limit=5&offset=0", headers=auth_headers_operator)
    assert resp.status_code == 200
    data = resp.json()

    assert "items" in data
    assert "total_count" in data
    assert data["limit"] == 5
    assert data["offset"] == 0
    assert len(data["items"]) <= 5

    if data["items"]:
        item = data["items"][0]
        assert "event_id" in item
        assert "timestamp" in item
        assert "adapter_id" in item
        assert "event_type" in item
        assert "status" in item
        assert "details" in item


def test_activity_records_ingestion(test_client, auth_headers_operator):
    """Ingesting an event through pipeline records an activity stream entry."""
    pipeline = get_pipeline()
    envelope = IngestionEnvelope.create(
        source_system="ServiceNow",
        source_type="ITSM",
        raw_payload={
            "sys_id": "SNOW-ACT-TEST-001",
            "short_description": "RAN Cell Carrier Loss Test",
            "priority": "1",
            "cmdb_ci": "gNodeB-501",
            "state": "1",
            "sys_created_on": "2026-11-04 12:00:00",
        },
        external_event_id="EXT-TEST-001",
    )
    result = pipeline.ingest_envelope(envelope)
    assert result.status.value in {"SUCCESS", "DUPLICATE"}

    # Fetch activity filtered by ServiceNow
    resp = test_client.get(
        "/api/v1/integrations/activity?integration_id=ServiceNow&limit=10",
        headers=auth_headers_operator,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_count"] > 0
    matching = [it for it in data["items"] if it["source_system"] == "ServiceNow"]
    assert len(matching) > 0


# ---------------------------------------------------------------------------
# 6. Single Integration Detail Endpoint & Secret Redaction
# ---------------------------------------------------------------------------

def test_get_integration_detail_servicenow(test_client, auth_headers_operator):
    """Detailed specification for ServiceNow adapter with secret omission."""
    resp = test_client.get("/api/v1/integrations/ITSM-SERVICENOW-01", headers=auth_headers_operator)
    assert resp.status_code == 200
    detail = resp.json()

    assert detail["integration_id"] == "ITSM-SERVICENOW-01"
    assert detail["category"] == "ITSM"
    assert detail["connection_mode"] == "LOCAL SIMULATION"
    assert detail["read_only_boundary_enforced"] is True
    assert "NORMALIZE" in detail["supported_operations"]
    assert "CREATE_TICKET" in detail["forbidden_operations"]
    assert "UPDATE_TICKET" in detail["forbidden_operations"]
    assert "EXECUTE_COMMAND" in detail["forbidden_operations"]

    # Verify required config fields omit all secrets
    config_fields = detail["required_config_fields"]
    assert len(config_fields) > 0
    for cf in config_fields:
        assert cf["is_secret"] is False
        # Ensure no credential or password strings leaked in sanitized values
        assert "password" not in cf["name"].lower()
        assert "secret" not in cf["name"].lower()

    # Verify health block
    assert detail["health"]["adapter_id"] == "ITSM-SERVICENOW-01"


def test_get_integration_detail_not_found(test_client, auth_headers_operator):
    """Unknown integration ID returns 404."""
    resp = test_client.get("/api/v1/integrations/NON_EXISTENT_ADAPTER", headers=auth_headers_operator)
    assert resp.status_code == 404
    assert "not registered" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 7. Single Adapter Health Endpoint
# ---------------------------------------------------------------------------

def test_get_single_adapter_health(test_client, auth_headers_operator):
    """Retrieve operational health for a specific adapter."""
    resp = test_client.get("/api/v1/integrations/TELEM-PROM-01/health", headers=auth_headers_operator)
    assert resp.status_code == 200
    h = resp.json()
    assert h["adapter_id"] == "TELEM-PROM-01"
    assert h["adapter_type"] == "TELEMETRY"
    assert h["state"] in {s.value for s in HealthState}
    assert "last_heartbeat" in h


def test_get_single_adapter_health_not_found(test_client, auth_headers_operator):
    """Unknown adapter ID for health check returns 404."""
    resp = test_client.get("/api/v1/integrations/UNKNOWN_ADAPTER/health", headers=auth_headers_operator)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 8. GET Non-Mutation Invariant
# ---------------------------------------------------------------------------

def test_get_requests_are_strictly_read_only(test_client, auth_headers_operator):
    """Invoking GET endpoints causes 0 state changes or side effects."""
    pipeline = get_pipeline()
    dlq_count_before = pipeline.dlq.count()
    incidents_count_before = pipeline.count_incidents()

    # Invoke all GET endpoints consecutively
    test_client.get("/api/v1/integrations", headers=auth_headers_operator)
    test_client.get("/api/v1/integrations/summary", headers=auth_headers_operator)
    test_client.get("/api/v1/integrations/data-flow", headers=auth_headers_operator)
    test_client.get("/api/v1/integrations/activity", headers=auth_headers_operator)
    test_client.get("/api/v1/integrations/health", headers=auth_headers_operator)
    test_client.get("/api/v1/integrations/ITSM-SERVICENOW-01", headers=auth_headers_operator)
    test_client.get("/api/v1/integrations/ITSM-SERVICENOW-01/health", headers=auth_headers_operator)

    dlq_count_after = pipeline.dlq.count()
    incidents_count_after = pipeline.count_incidents()

    assert dlq_count_before == dlq_count_after
    assert incidents_count_before == incidents_count_after
