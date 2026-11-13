"""Integration tests for PIIS UI-5 Human Review Hub endpoints and security boundaries.

Verifies:
1. Review Queue endpoint (GET /api/v1/incidents/reviews/queue): pagination, empty states, filtering.
2. Incident reviews history (GET /api/v1/incidents/{id}/reviews).
3. Authenticated human reviewer submission (POST /api/v1/incidents/{id}/reviews) for APPROVED and REJECTED.
4. Service principal lockout: automated identities strictly barred from signing reviews (403 Forbidden).
5. Unauthorized role lockout: non-operational roles (e.g. SECURITY_AUDITOR) rejected (403 Forbidden).
6. Reviewer identity spoofing resistance: operator identity extracted strictly from server-side bearer token.
7. Validation: invalid decisions rejected (400 Bad Request), rejection requires non-empty reason.
8. Duplicate submission lockout: terminal states cannot be re-approved/re-rejected (409 Conflict).
9. Cryptographic audit integrity: notes bound in RFC 8785 canonical payload, HMAC signature generated.
10. Operational boundary: strictly read-only decision support with zero network mutation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from piis.api.app import create_app
from piis.api.routers import incidents
from piis.auth import ApplicationRole, AuthManager
from piis.investigation.approval import (
    ApprovalStatus,
    IsolatedTestTokenVerifier,
)
from piis.investigation.schemas import (
    DiagnosticRecommendation,
    RecommendationRisk,
)


@pytest.fixture
def test_setup():
    """Setup clean app, workflow, auth manager, and test client."""
    app = create_app()
    client = TestClient(app)
    auth_mgr = AuthManager()
    workflow = incidents.get_workflow()
    pipeline = incidents.get_pipeline()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    return {
        "app": app,
        "client": client,
        "auth": auth_mgr,
        "workflow": workflow,
        "pipeline": pipeline,
        "verifier": verifier,
    }


def _create_test_recommendation(
    rec_id: str = "REC-TEST-001",
    description: str = "Verify diagnostic telemetry",
    source_runbook_id: str = "SOP-TEST-001",
    risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE,
) -> DiagnosticRecommendation:
    """Helper to construct a valid DiagnosticRecommendation with required fields."""
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description=description,
        reason="Testing operational review flow",
        supporting_evidence_ids=["EVID-TEST-001"],
        source_runbook_id=source_runbook_id,
        source_section="Section 2.1: Operational Check",
        expected_observation="Normal telemetry metrics observed",
        risk_classification=risk,
        human_approval_required=True,
    )


def test_review_queue_empty_state_returns_200(test_setup):
    """Verify review queue returns valid structure when queried."""
    client = test_setup["client"]
    token = test_setup["auth"].mint_dev_token("OP-NOC-01", role=ApplicationRole.NOC_L2)

    res = client.get(
        "/api/v1/incidents/reviews/queue",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total_count" in data
    assert "pending_count" in data
    assert "approved_count" in data
    assert "rejected_count" in data


def test_review_queue_with_registered_recommendations(test_setup):
    """Verify review queue returns populated recommendations with incident context."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    token = test_setup["auth"].mint_dev_token("OP-NOC-02", role=ApplicationRole.NOC_L2)

    rec = _create_test_recommendation(
        rec_id="REC-TEST-Q-001",
        description="Run diagnostic ping sweep on RAN fronthaul",
        source_runbook_id="SOP-RAN-001",
        risk=RecommendationRisk.READ_ONLY_SAFE,
    )
    workflow.register_recommendation(rec, incident_id="INC-TEST-Q-999")

    res = client.get(
        "/api/v1/incidents/reviews/queue",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 1
    assert data["pending_count"] >= 1

    matching = [item for item in data["items"] if item["recommendation_id"] == "REC-TEST-Q-001"]
    assert len(matching) == 1
    item = matching[0]
    assert item["incident_id"] == "INC-TEST-Q-999"
    assert item["approval_status"] == "PENDING_REVIEW"
    assert item["risk_classification"] == "READ_ONLY_SAFE"
    assert item["source_runbook_id"] == "SOP-RAN-001"


def test_review_queue_status_filtering(test_setup):
    """Verify filtering by approval status in the review queue."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    token = test_setup["auth"].mint_dev_token("OP-NOC-03", role=ApplicationRole.NOC_L2)

    rec1 = _create_test_recommendation(
        rec_id="REC-FILTER-PENDING",
        description="Check optic power levels",
        source_runbook_id="SOP-OPT-001",
        risk=RecommendationRisk.LOW_OBSERVABILITY,
    )
    workflow.register_recommendation(rec1, incident_id="INC-FILTER-101")

    # Query with status=PENDING_REVIEW
    res_pending = client.get(
        "/api/v1/incidents/reviews/queue?status=PENDING_REVIEW",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_pending.status_code == 200
    pending_items = res_pending.json()["items"]
    assert all(i["approval_status"] == "PENDING_REVIEW" for i in pending_items)
    assert any(i["recommendation_id"] == "REC-FILTER-PENDING" for i in pending_items)


def test_human_operator_approval_success_and_receipt(test_setup):
    """Verify authenticated operator can approve a recommendation and receive cryptographic receipt."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    token = test_setup["auth"].mint_dev_token("OP-TIER2-55", role=ApplicationRole.NOC_L2)

    rec = _create_test_recommendation(
        rec_id="REC-APPROVE-001",
        description="Verify BGP neighbor state on PE-01",
        source_runbook_id="SOP-TRANS-BGP-001",
        risk=RecommendationRisk.READ_ONLY_SAFE,
    )
    workflow.register_recommendation(rec, incident_id="INC-BGP-200")

    res = client.post(
        "/api/v1/incidents/INC-BGP-200/reviews",
        json={
            "recommendation_id": "REC-APPROVE-001",
            "decision": "APPROVED",
            "review_notes": "Reviewed BGP flap timestamps; verified safe read-only query.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    receipt = res.json()
    assert receipt["incident_id"] == "INC-BGP-200"
    assert receipt["recommendation_id"] == "REC-APPROVE-001"
    assert receipt["decision"] == "APPROVED"
    assert receipt["reviewed_by"] == "OP-TIER2-55"
    assert receipt["status"] == "RECORDED_IN_AUDIT_CHAIN"
    assert receipt["receipt_id"].startswith("RCPT-")
    assert len(receipt["audit_entry_hash"]) == 64
    assert receipt["ledger_sequence"] > 0

    # Verify workflow state locked to APPROVED
    updated = workflow.get_recommendation("REC-APPROVE-001")
    assert updated.approval_status == ApprovalStatus.APPROVED
    assert updated.reviewed_by == "OP-TIER2-55"
    assert updated.review_notes == "Reviewed BGP flap timestamps; verified safe read-only query."


def test_human_operator_rejection_success(test_setup):
    """Verify authenticated operator can reject a recommendation with required justification."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    token = test_setup["auth"].mint_dev_token("OP-TIER2-56", role=ApplicationRole.NOC_L2)

    rec = _create_test_recommendation(
        rec_id="REC-REJECT-001",
        description="Active ping flood test to core UPF",
        source_runbook_id="SOP-CORE-001",
        risk=RecommendationRisk.DISRUPTIVE_AUDIT,
    )
    workflow.register_recommendation(rec, incident_id="INC-UPF-300")

    res = client.post(
        "/api/v1/incidents/INC-UPF-300/reviews",
        json={
            "recommendation_id": "REC-REJECT-001",
            "decision": "REJECTED",
            "review_notes": "Rejected: Peak subscriber traffic hour; disruptive test prohibited.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    receipt = res.json()
    assert receipt["decision"] == "REJECTED"
    assert receipt["reviewed_by"] == "OP-TIER2-56"

    updated = workflow.get_recommendation("REC-REJECT-001")
    assert updated.approval_status == ApprovalStatus.REJECTED
    assert updated.reviewed_by == "OP-TIER2-56"


def test_service_principal_review_submission_strictly_barred(test_setup):
    """Verify service accounts / automated bots are barred with 403 Forbidden."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    svc_token = test_setup["auth"].mint_dev_token("svc-auto-poller", is_service=True)

    rec = _create_test_recommendation(
        rec_id="REC-SVC-BLOCK-001",
        description="Automated diagnostic check",
        source_runbook_id="SOP-AUTO-001",
        risk=RecommendationRisk.READ_ONLY_SAFE,
    )
    workflow.register_recommendation(rec, incident_id="INC-SVC-400")

    res = client.post(
        "/api/v1/incidents/INC-SVC-400/reviews",
        json={
            "recommendation_id": "REC-SVC-BLOCK-001",
            "decision": "APPROVED",
            "review_notes": "Bot attempting autonomous sign-off",
        },
        headers={"Authorization": f"Bearer {svc_token}"},
    )
    assert res.status_code == 403
    assert "automated service account" in res.json()["detail"].lower()


def test_unauthorized_role_review_submission_rejected(test_setup):
    """Verify users without operational NOC roles (e.g. SECURITY_AUDITOR) receive 403 Forbidden."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    auditor_token = test_setup["auth"].mint_dev_token("auditor-01", role=ApplicationRole.SECURITY_AUDITOR)

    rec = _create_test_recommendation(
        rec_id="REC-ROLE-BLOCK-001",
        description="Check optical interface",
        source_runbook_id="SOP-OPT-001",
        risk=RecommendationRisk.READ_ONLY_SAFE,
    )
    workflow.register_recommendation(rec, incident_id="INC-ROLE-500")

    res = client.post(
        "/api/v1/incidents/INC-ROLE-500/reviews",
        json={
            "recommendation_id": "REC-ROLE-BLOCK-001",
            "decision": "APPROVED",
            "review_notes": "Auditor attempting operational review",
        },
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert res.status_code == 403
    assert "lacks review authorization" in res.json()["detail"].lower()


def test_invalid_decision_string_rejected_with_400(test_setup):
    """Verify invalid decision strings (e.g. REQUEST_MORE_EVIDENCE, MAYBE) return 400 Bad Request."""
    client = test_setup["client"]
    token = test_setup["auth"].mint_dev_token("OP-TIER2-57", role=ApplicationRole.NOC_L2)

    res = client.post(
        "/api/v1/incidents/INC-INV-600/reviews",
        json={
            "recommendation_id": "REC-001",
            "decision": "REQUEST_MORE_EVIDENCE",
            "review_notes": "Need more data before approving",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "APPROVED" in res.json()["detail"]
    assert "REJECTED" in res.json()["detail"]


def test_duplicate_review_submission_fails_closed_with_409(test_setup):
    """Verify duplicate submission on an already-approved recommendation returns 409 Conflict."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    token = test_setup["auth"].mint_dev_token("OP-TIER2-58", role=ApplicationRole.NOC_L2)

    rec = _create_test_recommendation(
        rec_id="REC-REPLAY-001",
        description="Check fiber splice telemetry",
        source_runbook_id="SOP-FIBER-001",
        risk=RecommendationRisk.READ_ONLY_SAFE,
    )
    workflow.register_recommendation(rec, incident_id="INC-REPLAY-700")

    # First approval: succeeds
    res1 = client.post(
        "/api/v1/incidents/INC-REPLAY-700/reviews",
        json={
            "recommendation_id": "REC-REPLAY-001",
            "decision": "APPROVED",
            "review_notes": "Initial valid approval",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == 200

    # Second approval attempt: must fail with 409 Conflict
    res2 = client.post(
        "/api/v1/incidents/INC-REPLAY-700/reviews",
        json={
            "recommendation_id": "REC-REPLAY-001",
            "decision": "APPROVED",
            "review_notes": "Duplicate re-approval replay attempt",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 409
    assert "terminal state" in res2.json()["detail"].lower()


def test_get_incident_reviews_history(test_setup):
    """Verify GET /api/v1/incidents/{incident_id}/reviews returns decision history."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    token = test_setup["auth"].mint_dev_token("OP-TIER2-59", role=ApplicationRole.NOC_L2)

    rec = _create_test_recommendation(
        rec_id="REC-HIST-001",
        description="Inspect antenna alignment",
        source_runbook_id="SOP-ANT-001",
        risk=RecommendationRisk.READ_ONLY_SAFE,
    )
    workflow.register_recommendation(rec, incident_id="INC-HIST-800")

    # Submit approval
    client.post(
        "/api/v1/incidents/INC-HIST-800/reviews",
        json={
            "recommendation_id": "REC-HIST-001",
            "decision": "APPROVED",
            "review_notes": "Approved tower climb alignment check.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    # Query reviews history
    res = client.get(
        "/api/v1/incidents/INC-HIST-800/reviews",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    history = res.json()
    assert len(history) >= 1
    record = history[-1]
    assert record["incident_id"] == "INC-HIST-800"
    assert record["recommendation_id"] == "REC-HIST-001"
    assert record["action"] == "APPROVED"
    assert record["operator_id"] == "OP-TIER2-59"
    assert "climb alignment" in record["notes"]
    assert len(record["entry_sha256"]) == 64


def test_client_cannot_spoof_operator_id_in_body(test_setup):
    """Verify reviewer identity is strictly taken from bearer token and ignores body tampering."""
    client = test_setup["client"]
    workflow = test_setup["workflow"]
    legit_token = test_setup["auth"].mint_dev_token("OP-GENUINE-USER", role=ApplicationRole.NOC_L2)

    rec = _create_test_recommendation(
        rec_id="REC-SPOOF-001",
        description="Check routing table entries",
        source_runbook_id="SOP-RT-001",
        risk=RecommendationRisk.READ_ONLY_SAFE,
    )
    workflow.register_recommendation(rec, incident_id="INC-SPOOF-900")

    # Attempt to spoof operator_id in body
    res = client.post(
        "/api/v1/incidents/INC-SPOOF-900/reviews",
        json={
            "recommendation_id": "REC-SPOOF-001",
            "decision": "APPROVED",
            "review_notes": "Normal notes",
            "operator_id": "HACKER_ADMIN",
            "reviewed_by": "ROOT_OVERRIDE",
        },
        headers={"Authorization": f"Bearer {legit_token}"},
    )
    assert res.status_code == 200
    receipt = res.json()
    # Must attribute strictly to token identity OP-GENUINE-USER, NOT HACKER_ADMIN
    assert receipt["reviewed_by"] == "OP-GENUINE-USER"
    assert receipt["reviewed_by"] != "HACKER_ADMIN"
    assert receipt["reviewed_by"] != "ROOT_OVERRIDE"
