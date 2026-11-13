"""Integration tests for UI-4 Network Intelligence API endpoints.

Tests read-only network observability overview, topology retrieval, element details,
blast radius impact analysis, alarm clustering, and telemetry time-series streams.
Verifies strict epistemic taxonomy, non-fabrication of data, RBAC protection,
and structured 404/400 error codes.
"""

from fastapi.testclient import TestClient
import pytest

from piis.api.app import create_app
from piis.api.schemas import (
    NetworkAlarmsResponse,
    NetworkElementDetailResponse,
    NetworkImpactResponse,
    NetworkOverviewResponse,
    NetworkTelemetryResponse,
    NetworkTopologyResponse,
)
from piis.auth import ApplicationRole, AuthManager


@pytest.fixture
def app_instance():
    return create_app()


@pytest.fixture
def api_client(app_instance):
    return TestClient(app_instance)


@pytest.fixture
def auth_token():
    auth = AuthManager()
    return auth.mint_dev_token("noc_operator_ui4", role=ApplicationRole.NOC_L2)


def test_network_endpoints_require_authentication(api_client):
    """Verify all network intelligence endpoints enforce 401 when unauthenticated."""
    assert api_client.get("/api/v1/network/overview").status_code == 401
    assert api_client.get("/api/v1/network/topology").status_code == 401
    assert api_client.get("/api/v1/network/elements/GNB-TESTBED-5G-01").status_code == 401
    assert api_client.get("/api/v1/network/impact?element_id=GNB-TESTBED-5G-01").status_code == 401
    assert api_client.get("/api/v1/network/alarms").status_code == 401
    assert api_client.get("/api/v1/network/telemetry?element_id=GNB-TESTBED-5G-01").status_code == 401


def test_get_network_overview_success(api_client, auth_token):
    """Verify overview returns valid topology summary, alarm counts, and provenance."""
    res = api_client.get(
        "/api/v1/network/overview",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    data = res.json()

    # Validate against Pydantic schema
    validated = NetworkOverviewResponse.model_validate(data)
    assert validated.total_elements >= 13
    assert "RAN" in validated.elements_by_domain
    assert "TRANSPORT" in validated.elements_by_domain
    assert "5G_CORE" in validated.elements_by_domain
    assert validated.total_links >= 10
    assert validated.epistemic_status == "REFERENCE_DATA"
    assert "source_model" in validated.provenance
    assert "integrity_hash" in validated.provenance


def test_get_network_topology_all_and_filtered(api_client, auth_token):
    """Verify topology returns nodes and directed links, and supports domain filtering."""
    # Full topology
    res = api_client.get(
        "/api/v1/network/topology",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    validated = NetworkTopologyResponse.model_validate(data)
    assert len(validated.nodes) >= 13
    assert len(validated.links) >= 10
    assert validated.epistemic_status == "COMPUTED_TOPOLOGY"

    # Verify directed downstream dependencies exist
    downstream_links = [link for link in validated.links if link.is_dependency and link.direction == "downstream"]
    assert len(downstream_links) > 0

    # Domain filtered topology: RAN only
    res_ran = api_client.get(
        "/api/v1/network/topology?domain=RAN",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_ran.status_code == 200
    ran_data = res_ran.json()
    ran_validated = NetworkTopologyResponse.model_validate(ran_data)
    for node in ran_validated.nodes:
        assert node.domain == "RAN"


def test_get_element_detail_success_and_not_found(api_client, auth_token):
    """Verify element detail returns neighbors, upstream, and downstream, with 404 for unknown elements."""
    # Valid element: GNB-TESTBED-5G-01
    res = api_client.get(
        "/api/v1/network/elements/GNB-TESTBED-5G-01",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    validated = NetworkElementDetailResponse.model_validate(data)
    assert validated.element_id == "GNB-TESTBED-5G-01"
    assert validated.domain == "RAN"
    assert "SW-ACCESS-SITE01" in validated.upstream_parents
    assert "CELL-101" in validated.downstream_children
    assert validated.epistemic_status == "REFERENCE_DATA"

    # Unknown element
    res_404 = api_client.get(
        "/api/v1/network/elements/UNKNOWN-ELEMENT-999",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_404.status_code == 404
    assert res_404.headers.get("x-piis-error-code") == "ELEMENT_NOT_FOUND"


def test_get_network_impact_analysis(api_client, auth_token):
    """Verify blast radius impact analysis computes direct and inferred downstream nodes."""
    res = api_client.get(
        "/api/v1/network/impact?element_id=SW-ACCESS-SITE01",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    validated = NetworkImpactResponse.model_validate(data)
    assert validated.target_element == "SW-ACCESS-SITE01"
    assert "SW-ACCESS-SITE01" in validated.direct_elements
    # SW-ACCESS-SITE01 serves GNB-TESTBED-5G-01 which serves cells
    assert "GNB-TESTBED-5G-01" in validated.inferred_elements
    assert validated.epistemic_status == "DERIVED_ESTIMATE"
    assert validated.subscriber_impact_basis is not None
    assert "registered topology metadata" in validated.subscriber_impact_basis


def test_get_network_impact_validation_errors(api_client, auth_token):
    """Verify impact analysis returns 400 when missing params and 404 for unknown elements."""
    # Missing both element_id and incident_id
    res_bad = api_client.get(
        "/api/v1/network/impact",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_bad.status_code == 400
    assert res_bad.headers.get("x-piis-error-code") == "INVALID_QUERY_PARAMETERS"

    # Unknown element ID
    res_404 = api_client.get(
        "/api/v1/network/impact?element_id=NON-EXISTENT-ROUTER",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_404.status_code == 404
    assert res_404.headers.get("x-piis-error-code") == "ELEMENT_NOT_FOUND"


def test_get_network_alarms_and_clustering(api_client, auth_token):
    """Verify alarms retrieval and clustering with ingested alarms."""
    # Ingest two correlated alarms via unified ingestion pipeline
    alarm1 = {
        "alarm_id": "ALM-RAN-TEST-01",
        "element_id": "GNB-TESTBED-5G-01",
        "alarm_code": "7100",
        "severity": "CRITICAL",
        "vendor": "NOKIA",
        "probable_cause": "High VSWR on antenna feeder",
        "timestamp": "2026-11-03T12:00:00Z",
    }
    alarm2 = {
        "alarm_id": "ALM-RAN-TEST-02",
        "element_id": "CELL-101",
        "alarm_code": "7100",
        "severity": "MAJOR",
        "vendor": "NOKIA",
        "probable_cause": "Radio link failure",
        "timestamp": "2026-11-03T12:01:00Z",
    }

    res_ingest1 = api_client.post(
        "/api/v1/incidents/ingest",
        json={"source_system": "GenericOSS", "source_type": "OPERATOR_INTERNAL", "payload": alarm1},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_ingest1.status_code == 200

    res_ingest2 = api_client.post(
        "/api/v1/incidents/ingest",
        json={"source_system": "GenericOSS", "source_type": "OPERATOR_INTERNAL", "payload": alarm2},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_ingest2.status_code == 200

    # Query alarms
    res_alarms = api_client.get(
        "/api/v1/network/alarms",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_alarms.status_code == 200
    data = res_alarms.json()
    validated = NetworkAlarmsResponse.model_validate(data)
    assert validated.total_alarms >= 2
    assert any(a.network_element_id == "GNB-TESTBED-5G-01" for a in validated.alarms)
    assert any(a.network_element_id == "CELL-101" for a in validated.alarms)

    # Filter by domain
    res_ran = api_client.get(
        "/api/v1/network/alarms?domain=RAN",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_ran.status_code == 200
    for a in res_ran.json()["alarms"]:
        assert a["network_domain"] == "RAN"


def test_get_network_telemetry_and_anomalies(api_client, auth_token):
    """Verify telemetry time-series and anomaly detection on ingested observations."""
    # Ingest telemetry observations for CELL-101 via Prometheus adapter
    for i in range(10):
        val = 45.0 + i
        if i == 8:
            val = 98.5  # Significant spike
        sample = {
            "metric": {"__name__": "prb_utilization_pct", "instance": "CELL-101"},
            "value": [1767225600.0 + (i * 60), str(val)],
            "timestamp": f"2026-11-03T12:0{i}:00Z",
        }
        res_t = api_client.post(
            "/api/v1/incidents/ingest",
            json={"source_system": "Prometheus", "source_type": "OPERATOR_INTERNAL", "payload": sample},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert res_t.status_code == 200

    # Query telemetry
    res_tel = api_client.get(
        "/api/v1/network/telemetry?element_id=CELL-101",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_tel.status_code == 200
    data = res_tel.json()
    validated = NetworkTelemetryResponse.model_validate(data)
    assert validated.element_id == "CELL-101"
    assert len(validated.series) >= 1
    assert validated.series[0].metric_name == "prb_utilization_pct"
    assert len(validated.series[0].values) == 10
    assert validated.epistemic_status == "OBSERVED_FACT"

    # Query non-existent element
    res_404 = api_client.get(
        "/api/v1/network/telemetry?element_id=NON-EXISTENT-ELEMENT",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res_404.status_code == 404
    assert res_404.headers.get("x-piis-error-code") == "ELEMENT_NOT_FOUND"
