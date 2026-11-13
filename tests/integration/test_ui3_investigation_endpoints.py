"""Integration tests for UI-3 / UI-3.2 Investigation Workspace API endpoints.

Tests the read-only retrieval of investigation context, hypotheses, and evidence,
verifies strict 404 lifecycle semantics for ungenerated investigations,
verifies pure GET idempotency without state mutations or workflow side-effects,
and verifies typed schema validation against InvestigationHypothesisItem.
"""

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from piis.api.app import create_app
from piis.api.schemas import InvestigationHypothesisItem, InvestigationResponse
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
    return auth.mint_dev_token("noc_operator_1", role=ApplicationRole.NOC_L2)


@pytest.fixture
def seeded_incident(api_client, auth_token):
    # Ingest a sample incident into the pipeline
    raw_payload = {
        "number": "INC0099112",
        "short_description": "High VSWR on 5G NR Sector 4B",
        "description": "Antenna impedance mismatch detected on gnb-cluster-tx-09",
        "category": "RAN",
        "state": "1",
    }
    res = api_client.post(
        "/api/v1/incidents/ingest",
        json={"source_system": "ServiceNow", "source_type": "PUBLIC_REAL", "payload": raw_payload},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    return res.json()["canonical_id"]


@pytest.fixture
def investigated_incident(api_client, auth_token, seeded_incident):
    res = api_client.post(
        f"/api/v1/incidents/{seeded_incident}/investigate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    return seeded_incident


def test_get_investigation_not_yet_generated_returns_404_without_side_effects(
    app_instance, api_client, auth_token, seeded_incident
):
    """Verify all 4 investigation GET endpoints return 404 when investigation has not been triggered."""
    expected_detail = (
        f"Investigation not yet generated for incident '{seeded_incident}'. "
        f"Trigger investigation via POST /api/v1/incidents/{seeded_incident}/investigate."
    )

    endpoints = [
        f"/api/v1/incidents/{seeded_incident}/investigation",
        f"/api/v1/incidents/{seeded_incident}/hypotheses",
        f"/api/v1/incidents/{seeded_incident}/evidence",
        f"/api/v1/incidents/{seeded_incident}/recommendations",
    ]

    for ep in endpoints:
        res = api_client.get(ep, headers={"Authorization": f"Bearer {auth_token}"})
        assert res.status_code == 404
        assert res.json()["detail"] == expected_detail
        assert res.headers.get("x-piis-error-code") == "INVESTIGATION_NOT_YET_GENERATED"
        assert res.json().get("code") == "INVESTIGATION_NOT_YET_GENERATED"

    # Verify zero side-effects: investigation remains None in pipeline
    from piis.api.routers.incidents import get_pipeline, get_workflow
    pipeline = get_pipeline()
    assert pipeline.get_investigation(seeded_incident) is None

    # Verify zero side-effects: no recommendations registered in approval workflow
    workflow = get_workflow()
    with workflow._lock:
        registered_recs = [
            r for r in workflow._recommendations.values()
            if getattr(r, "incident_id", None) == seeded_incident
        ]
        assert len(registered_recs) == 0


def test_get_investigation_nonexistent_incident_returns_404(api_client, auth_token):
    """Verify non-existent incidents return 404 'Incident not found' on all GET endpoints."""
    bad_id = "INC-NONEXISTENT-9999"
    endpoints = [
        f"/api/v1/incidents/{bad_id}/investigation",
        f"/api/v1/incidents/{bad_id}/hypotheses",
        f"/api/v1/incidents/{bad_id}/evidence",
        f"/api/v1/incidents/{bad_id}/recommendations",
    ]
    for ep in endpoints:
        res = api_client.get(ep, headers={"Authorization": f"Bearer {auth_token}"})
        assert res.status_code == 404
        assert res.json()["detail"] == f"Incident '{bad_id}' not found"
        assert res.headers.get("x-piis-error-code") == "INCIDENT_NOT_FOUND"
        assert res.json().get("code") == "INCIDENT_NOT_FOUND"


def test_investigate_post_populates_cache_and_enables_get(
    api_client, auth_token, seeded_incident
):
    """Verify POST /investigate triggers investigation and enables subsequent read-only GET endpoints."""
    # 1. Trigger POST investigation
    post_res = api_client.post(
        f"/api/v1/incidents/{seeded_incident}/investigate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["incident_id"] == seeded_incident

    # 2. Subsequent GET calls now succeed
    get_res = api_client.get(
        f"/api/v1/incidents/{seeded_incident}/investigation",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["incident_id"] == seeded_incident

    hyp_res = api_client.get(
        f"/api/v1/incidents/{seeded_incident}/hypotheses",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert hyp_res.status_code == 200
    assert isinstance(hyp_res.json(), list)

    ev_res = api_client.get(
        f"/api/v1/incidents/{seeded_incident}/evidence",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert ev_res.status_code == 200
    assert isinstance(ev_res.json(), list)

    rec_res = api_client.get(
        f"/api/v1/incidents/{seeded_incident}/recommendations",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert rec_res.status_code == 200
    assert isinstance(rec_res.json(), list)


def test_get_investigation_hypotheses_endpoint(api_client, auth_token, investigated_incident):
    """Verify GET /api/v1/incidents/{incident_id}/hypotheses returns typed ranked hypotheses."""
    res = api_client.get(
        f"/api/v1/incidents/{investigated_incident}/hypotheses",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    hypotheses = res.json()
    assert isinstance(hypotheses, list)
    if len(hypotheses) > 0:
        h = hypotheses[0]
        validated_item = InvestigationHypothesisItem(**h)
        assert validated_item.hypothesis_id == h["hypothesis_id"]
        assert 0.0 <= validated_item.confidence_proxy <= 1.0
        assert isinstance(validated_item.supporting_evidence_ids, list)
        assert isinstance(validated_item.contradicting_evidence_ids, list)
        assert len(validated_item.confidence_rationale) > 0


def test_get_investigation_context_endpoint(api_client, auth_token, investigated_incident):
    """Verify GET /api/v1/incidents/{incident_id}/investigation returns full typed context."""
    res = api_client.get(
        f"/api/v1/incidents/{investigated_incident}/investigation",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    validated_response = InvestigationResponse(**data)
    assert validated_response.incident_id == investigated_incident
    assert validated_response.hypotheses_count == len(validated_response.hypotheses)
    assert isinstance(validated_response.is_sufficient, bool)


def test_get_investigation_idempotency(api_client, auth_token, investigated_incident):
    """Verify GET investigation endpoint is strictly read-only and idempotent."""
    res1 = api_client.get(
        f"/api/v1/incidents/{investigated_incident}/investigation",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    res2 = api_client.get(
        f"/api/v1/incidents/{investigated_incident}/investigation",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["incident_id"] == res2.json()["incident_id"]
    assert res1.json()["hypotheses_count"] == res2.json()["hypotheses_count"]


def test_unauthorized_hypotheses_request(api_client, seeded_incident):
    """Verify unauthenticated requests to hypotheses endpoint return 401."""
    res = api_client.get(f"/api/v1/incidents/{seeded_incident}/hypotheses")
    assert res.status_code == 401


def test_hypothesis_schema_bounds_validation():
    """Verify InvestigationHypothesisItem strictly validates confidence proxy bounds and status enum."""
    base_payload = {
        "hypothesis_id": "HYP-VALID-01",
        "description": "Feeder line physical damage",
        "supporting_evidence_ids": ["EVID-1"],
        "contradicting_evidence_ids": [],
        "evidence_source": "TelemetryEngine",
        "confidence_proxy": 0.85,
        "confidence_rationale": "High VSWR and impedance spike",
        "status": "SUPPORTED",
    }

    # Valid item should parse successfully
    valid = InvestigationHypothesisItem(**base_payload)
    assert valid.confidence_proxy == 0.85
    assert valid.status == "SUPPORTED"

    # Lower bound violation: confidence_proxy < 0.0
    with pytest.raises(ValidationError):
        InvestigationHypothesisItem(**{**base_payload, "confidence_proxy": -0.01})

    # Upper bound violation: confidence_proxy > 1.0
    with pytest.raises(ValidationError):
        InvestigationHypothesisItem(**{**base_payload, "confidence_proxy": 1.01})

    # Invalid status violation
    with pytest.raises(ValidationError):
        InvestigationHypothesisItem(**{**base_payload, "status": "UNKNOWN_CUSTOM_STATUS"})

    # Valid boundary items: 0.0 and 1.0
    item_zero = InvestigationHypothesisItem(**{**base_payload, "confidence_proxy": 0.0})
    assert item_zero.confidence_proxy == 0.0
    item_one = InvestigationHypothesisItem(**{**base_payload, "confidence_proxy": 1.0})
    assert item_one.confidence_proxy == 1.0
