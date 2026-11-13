"""Unit tests for M5 Human Approval Workflow and cryptographic decision audit log."""

import pytest

from piis.investigation.approval import (
    HumanApprovalWorkflow,
    IsolatedTestTokenVerifier,
)
from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    RecommendationRisk,
)


def _sample_recommendation(rec_id: str = "REC-001") -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description="Inspect physical RF feeder line",
        reason="Corroborate VSWR spike",
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="SOP-RAN-VSWR-001",
        source_section="Section 2.1",
        expected_observation="VSWR <= 1.3:1",
        risk_classification=RecommendationRisk.LOW_OBSERVABILITY,
        human_approval_required=True,
    )


def test_registration_creates_submitted_audit():
    wf = HumanApprovalWorkflow()
    rec = _sample_recommendation("REC-100")
    wf.register_recommendation(rec, incident_id="INC-999")

    assert wf.get_pending_count() == 1
    assert rec.approval_status == ApprovalStatus.PENDING_REVIEW

    trail = wf.get_audit_trail()
    assert len(trail) == 1
    assert trail[0].action == "SUBMITTED"
    assert trail[0].operator_id == "SYSTEM"
    assert len(trail[0].state_sha256) == 64


def test_operator_approval():
    wf = HumanApprovalWorkflow()
    rec = _sample_recommendation("REC-101")
    wf.register_recommendation(rec, incident_id="INC-999")

    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-NOC-742", role="NOC_TIER_2")
    approved_rec = wf.approve_recommendation(
        recommendation_id="REC-101",
        operator_id=token,
        incident_id="INC-999",
        notes="Reviewed telemetry; antenna feeder sweep authorized.",
    )

    assert approved_rec.approval_status == ApprovalStatus.APPROVED
    assert approved_rec.reviewed_by == "OP-NOC-742"
    assert approved_rec.review_notes == "Reviewed telemetry; antenna feeder sweep authorized."
    assert approved_rec.review_timestamp is not None
    assert wf.get_pending_count() == 0

    trail = wf.get_audit_trail()
    assert len(trail) == 2
    assert trail[1].action == "APPROVED"
    assert trail[1].operator_id == "OP-NOC-742"
    assert trail[1].previous_status == ApprovalStatus.PENDING_REVIEW
    assert trail[1].new_status == ApprovalStatus.APPROVED


def test_approval_requires_operator_id():
    wf = HumanApprovalWorkflow()
    rec = _sample_recommendation("REC-102")
    wf.register_recommendation(rec, incident_id="INC-999")

    with pytest.raises(ValueError, match="non-empty operator_id"):
        wf.approve_recommendation(
            recommendation_id="REC-102",
            operator_id="",  # Empty operator ID must fail
            incident_id="INC-999",
        )


def test_operator_rejection():
    wf = HumanApprovalWorkflow()
    rec = _sample_recommendation("REC-103")
    wf.register_recommendation(rec, incident_id="INC-999")

    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-NOC-105", role="NOC_TIER_2")
    rejected_rec = wf.reject_recommendation(
        recommendation_id="REC-103",
        operator_id=token,
        incident_id="INC-999",
        reason="Severe thunderstorm at tower site; unsafe for physical sweep.",
    )

    assert rejected_rec.approval_status == ApprovalStatus.REJECTED
    assert rejected_rec.reviewed_by == "OP-NOC-105"
    assert "thunderstorm" in rejected_rec.review_notes

    trail = wf.get_audit_trail()
    assert len(trail) == 2
    assert trail[1].action == "REJECTED"


def test_operator_rejection_requires_reason():
    wf = HumanApprovalWorkflow()
    rec = _sample_recommendation("REC-104")
    wf.register_recommendation(rec, incident_id="INC-999")

    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-NOC-105", role="NOC_TIER_2")
    with pytest.raises(ValueError, match="non-empty explanation"):
        wf.reject_recommendation(
            recommendation_id="REC-104",
            operator_id=token,
            incident_id="INC-999",
            reason="",
        )


def test_operator_modification():
    wf = HumanApprovalWorkflow()
    rec = _sample_recommendation("REC-105")
    wf.register_recommendation(rec, incident_id="INC-999")

    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-NOC-999", role="NOC_TIER_2")
    modified_rec = wf.modify_recommendation(
        recommendation_id="REC-105",
        operator_id=token,
        incident_id="INC-999",
        modified_description="Execute remote loopback sweep first before dispatching technician.",
        notes="Staging remote test first.",
    )

    assert modified_rec.approval_status == ApprovalStatus.MODIFIED
    assert "remote loopback" in modified_rec.description
    assert modified_rec.reviewed_by == "OP-NOC-999"

    trail = wf.get_audit_trail()
    assert len(trail) == 2
    assert trail[1].action == "MODIFIED"


def test_unknown_recommendation_raises_key_error():
    wf = HumanApprovalWorkflow()
    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-1")
    with pytest.raises(KeyError, match="not found"):
        wf.approve_recommendation("REC-NONEXISTENT", token, "INC-1")
