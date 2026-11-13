"""Unit and adversarial tests for M5.3 Workstream 1: Eliminating SYSTEM identity bypass.

Validates:
1. Direct construction of AuthenticatedReviewer with 'SYSTEM' is rejected.
2. Magic string 'SYSTEM' passed to approval is rejected.
3. Service principal credentials attempting human review are rejected (InsufficientPrivilegeError).
4. Service principal with missing SCOPE_INTERNAL_REGISTRATION cannot register recommendations.
5. Expired or forged service credentials are rejected.
6. Legitimate human reviewers with valid HMAC/JWT tokens succeed.
7. Service principal registration records principal_type='SERVICE' and authorization_scope in audit log.
"""

import pytest

from piis.investigation.approval import (
    AuthenticatedReviewer,
    AuthenticatedServicePrincipal,
    HumanApprovalWorkflow,
    InsufficientPrivilegeError,
    IsolatedTestTokenVerifier,
    SCOPE_INTERNAL_REGISTRATION,
    SCOPE_READ_ONLY_OBSERVATION,
    UnauthenticatedReviewerError,
)
from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    RecommendationRisk,
)


def _sample_rec(rec_id: str = "REC-SYS-01", risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description="Verify interface CRC error rates on optical trunk",
        reason="Check for physical layer frame corruption",
        supporting_evidence_ids=["EVID-SYS-01"],
        source_runbook_id="SOP-TRANS-FIBER-001",
        source_section="Section 1.2",
        expected_observation="CRC error count = 0",
        risk_classification=risk,
        human_approval_required=True,
    )


def test_direct_forged_system_identity_rejected():
    """Verify that constructing AuthenticatedReviewer(operator_id='SYSTEM') is strictly rejected."""
    with pytest.raises((UnauthenticatedReviewerError, ValueError), match="Prohibited human reviewer identity"):
        AuthenticatedReviewer(operator_id="SYSTEM")

    with pytest.raises(UnauthenticatedReviewerError, match="not authorized"):
        AuthenticatedReviewer.create_verified(operator_id="SYSTEM")


def test_magic_string_system_rejected_in_approval():
    """Verify that passing the raw string 'SYSTEM' to approve_recommendation is rejected."""
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-SYS-02")
    wf.register_recommendation(rec, "INC-SYS-02")

    with pytest.raises(UnauthenticatedReviewerError, match="Magic string 'SYSTEM' is not an authorized credential"):
        wf.approve_recommendation("REC-SYS-02", "SYSTEM", "INC-SYS-02")

    with pytest.raises(UnauthenticatedReviewerError, match="Magic string 'ROOT' is not an authorized credential"):
        wf.approve_recommendation("REC-SYS-02", "ROOT", "INC-SYS-02")


def test_service_principal_cannot_perform_human_approvals():
    """Verify that service principals are strictly blocked from approving or modifying recommendations."""
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-SYS-03")
    wf.register_recommendation(rec, "INC-SYS-03")

    svc_tok = verifier.mint_service_token(
        service_id="svc-telemetry-aggregator",
        service_name="Telemetry Aggregator",
        allowed_scopes=[SCOPE_INTERNAL_REGISTRATION],
    )
    svc_claims = verifier.verify_service_token(svc_tok)
    svc_principal = AuthenticatedServicePrincipal.from_claims(svc_claims)

    # Passing AuthenticatedServicePrincipal object directly
    with pytest.raises(InsufficientPrivilegeError, match="cannot approve, reject, or modify"):
        wf.approve_recommendation("REC-SYS-03", svc_principal, "INC-SYS-03")

    # Passing service token string
    with pytest.raises(InsufficientPrivilegeError, match="Service principal credential supplied to human review boundary"):
        wf.approve_recommendation("REC-SYS-03", svc_tok, "INC-SYS-03")


def test_service_registration_scope_enforcement():
    """Verify that only service principals with SCOPE_INTERNAL_REGISTRATION can register recommendations."""
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-SYS-04")

    # Service with wrong scope
    obs_tok = verifier.mint_service_token(
        service_id="svc-read-only",
        service_name="Read-Only Observability",
        allowed_scopes=[SCOPE_READ_ONLY_OBSERVATION],
    )
    with pytest.raises(InsufficientPrivilegeError, match="lacks required scope"):
        wf.register_recommendation(rec, "INC-SYS-04", service_credential=obs_tok)

    # Service with valid registration scope
    reg_tok = verifier.mint_service_token(
        service_id="svc-ingestion",
        service_name="Ingestion Service",
        allowed_scopes=[SCOPE_INTERNAL_REGISTRATION],
    )
    wf.register_recommendation(rec, "INC-SYS-04", service_credential=reg_tok)
    assert rec.approval_status == ApprovalStatus.PENDING_REVIEW

    trail = wf.get_audit_trail()
    assert len(trail) == 1
    assert trail[0].principal_type == "SERVICE"
    assert trail[0].operator_id == "svc-ingestion"
    assert trail[0].authorization_scope == SCOPE_INTERNAL_REGISTRATION


def test_expired_service_credential_rejected():
    """Verify that expired service credentials fail verification."""
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-SYS-05")

    exp_tok = verifier.mint_service_token(
        service_id="svc-expired",
        lifetime_seconds=-10,  # Already expired
    )
    with pytest.raises(UnauthenticatedReviewerError, match="expired"):
        wf.register_recommendation(rec, "INC-SYS-05", service_credential=exp_tok)


def test_revoked_service_credential_rejected():
    """Verify that revoked service tokens fail verification."""
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-SYS-06")

    tok = verifier.mint_service_token(service_id="svc-to-revoke")
    verifier.revoke_token(tok)

    with pytest.raises(UnauthenticatedReviewerError, match="revoked"):
        wf.register_recommendation(rec, "INC-SYS-06", service_credential=tok)


def test_valid_human_approval_records_human_principal():
    """Verify that legitimate human review records principal_type='HUMAN' and proper reviewer role."""
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-SYS-07", risk=RecommendationRisk.READ_ONLY_SAFE)
    wf.register_recommendation(rec, "INC-SYS-07")

    user_tok = verifier.mint_token(operator_id="op_alice", role="NOC_TIER_2")
    approved_rec = wf.approve_recommendation("REC-SYS-07", user_tok, "INC-SYS-07", notes="Diagnostics approved")

    assert approved_rec.approval_status == ApprovalStatus.APPROVED
    trail = wf.get_audit_trail()
    assert len(trail) == 2
    # First entry is service registration
    assert trail[0].principal_type == "SERVICE"
    assert trail[0].action == "SUBMITTED"
    # Second entry is human approval
    assert trail[1].principal_type == "HUMAN"
    assert trail[1].action == "APPROVED"
    assert trail[1].operator_id == "op_alice"
    assert trail[1].reviewer_role == "NOC_TIER_2"
    assert trail[1].notes == "Diagnostics approved"
