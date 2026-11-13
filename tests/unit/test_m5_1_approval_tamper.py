"""Exhaustive adversarial tamper and integrity tests for M5.1 / M5.2 HumanApprovalWorkflow."""

import pytest

from piis.investigation.approval import (
    AuthenticatedReviewer,
    HumanApprovalWorkflow,
    IllegalStateTransitionError,
    IsolatedTestTokenVerifier,
    RecommendationTamperedError,
    UnauthenticatedReviewerError,
)
from piis.investigation.schemas import (
    DiagnosticRecommendation,
    RecommendationRisk,
)


def _sample_rec(rec_id: str = "REC-TST-001") -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description="Inspect optical return loss on SFP port 01",
        reason="Corroborate optical attenuation hypothesis",
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="SOP-TRANS-FIBER-001",
        source_section="Section 2.1",
        preconditions=["Clean optical connector"],
        expected_observation="Return loss > 18 dB",
        risk_classification=RecommendationRisk.READ_ONLY_SAFE,
        human_approval_required=True,
    )


def test_normal_lifecycle_audit_chain_valid():
    wf = HumanApprovalWorkflow()
    rec1 = _sample_rec("REC-001")
    rec2 = _sample_rec("REC-002")

    wf.register_recommendation(rec1, "INC-001")
    wf.register_recommendation(rec2, "INC-001")

    reviewer = AuthenticatedReviewer.create_verified(
        operator_id="OP-NOC-LEAD-01", role="NOC_LEAD", auth_token="session-xyz-123"
    )

    wf.approve_recommendation("REC-001", reviewer, "INC-001", "Authorized physical inspection")
    wf.reject_recommendation("REC-002", reviewer, "INC-001", "Postponed until maintenance window")

    is_valid, errors = wf.verify_audit_trail()
    assert is_valid is True
    assert len(errors) == 0
    assert len(wf.get_audit_trail()) == 4


def test_tampering_earlier_event_fails_verification():
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-001")
    wf.register_recommendation(rec, "INC-001")

    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-ALICE")
    wf.approve_recommendation("REC-001", token, "INC-001")

    # Adversary alters operator_id in memory on the submitted event
    wf._audit_trail[0].operator_id = "OP-MALLORY"

    is_valid, errors = wf.verify_audit_trail()
    assert is_valid is False
    assert any("Tampered record digest" in e for e in errors)


def test_deleting_event_breaks_chain():
    wf = HumanApprovalWorkflow()
    rec1 = _sample_rec("REC-001")
    rec2 = _sample_rec("REC-002")
    wf.register_recommendation(rec1, "INC-001")
    wf.register_recommendation(rec2, "INC-001")

    token_alice = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-ALICE")
    token_bob = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-BOB")
    wf.approve_recommendation("REC-001", token_alice, "INC-001")
    wf.approve_recommendation("REC-002", token_bob, "INC-001")

    # Adversary deletes intermediate approval
    del wf._audit_trail[2]

    is_valid, errors = wf.verify_audit_trail()
    assert is_valid is False
    assert any("Broken hash chain" in e or "Sequence discontinuity" in e for e in errors)


def test_reordering_events_breaks_chain():
    wf = HumanApprovalWorkflow()
    rec1 = _sample_rec("REC-001")
    rec2 = _sample_rec("REC-002")
    wf.register_recommendation(rec1, "INC-001")
    wf.register_recommendation(rec2, "INC-001")

    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-ALICE")
    wf.approve_recommendation("REC-001", token, "INC-001")

    # Reverse audit trail
    wf._audit_trail.reverse()

    is_valid, errors = wf.verify_audit_trail()
    assert is_valid is False
    assert len(errors) > 0


def test_wholesale_substitution_fails_hmac():
    secret_key = b"TRUE-MASTER-AUDIT-KEY-999-32BYTES!"
    attacker_key = b"ATTACKER-FORGED-KEY-000-32BYTES!"

    wf_legit = HumanApprovalWorkflow(signing_key=secret_key)
    rec = _sample_rec("REC-001")
    wf_legit.register_recommendation(rec, "INC-001")

    token_alice = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-ALICE")
    wf_legit.approve_recommendation("REC-001", token_alice, "INC-001")

    # Adversary tries to forge an audit trail using their own key
    wf_attacker = HumanApprovalWorkflow(signing_key=attacker_key)
    rec_fake = _sample_rec("REC-001")
    wf_attacker.register_recommendation(rec_fake, "INC-001")

    token_mallory = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-MALLORY")
    wf_attacker.approve_recommendation("REC-001", token_mallory, "INC-001")

    # Inject forged audit trail into legit workflow
    wf_legit._audit_trail = wf_attacker.get_audit_trail()

    is_valid, errors = wf_legit.verify_audit_trail()
    assert is_valid is False
    assert any("Invalid HMAC signature" in e for e in errors)


def test_modifying_recommendation_after_approval_invalidates_binding():
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-001")
    wf.register_recommendation(rec, "INC-001")

    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-ALICE")
    wf.approve_recommendation("REC-001", token, "INC-001")

    assert wf.verify_recommendation_binding("REC-001") is True

    # Adversary alters description of approved recommendation in memory
    rec.description = "MALICIOUS: format c: and drop database tables"

    # Binding check must fail
    assert wf.verify_recommendation_binding("REC-001") is False

    # Attempting to fetch verified recommendation must raise RecommendationTamperedError
    with pytest.raises(RecommendationTamperedError, match="mutated in memory after operator approval"):
        wf.get_verified_recommendation("REC-001")

    # Audit trail verification also flags this mutation
    is_valid, errors = wf.verify_audit_trail()
    assert is_valid is False
    assert any("mutated in memory after approval" in e for e in errors)


def test_replay_approval_raises_illegal_state():
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-001")
    wf.register_recommendation(rec, "INC-001")

    token_alice = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-ALICE")
    token_bob = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-BOB")
    wf.approve_recommendation("REC-001", token_alice, "INC-001")

    # Attempting to approve an already approved recommendation must raise IllegalStateTransitionError
    with pytest.raises(IllegalStateTransitionError, match="Replays and duplicate approvals are strictly prohibited"):
        wf.approve_recommendation("REC-001", token_bob, "INC-001")


def test_transition_rejected_to_approved_raises_illegal_state():
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-001")
    wf.register_recommendation(rec, "INC-001")

    token_alice = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-ALICE")
    token_bob = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-BOB")
    wf.reject_recommendation("REC-001", token_alice, "INC-001", "Safety hazard on site")

    # Attempting to approve a rejected recommendation must raise IllegalStateTransitionError
    with pytest.raises(IllegalStateTransitionError, match="Cannot approve recommendation .* in terminal state 'REJECTED'"):
        wf.approve_recommendation("REC-001", token_bob, "INC-001")


def test_transition_approved_to_rejected_raises_illegal_state():
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-001")
    wf.register_recommendation(rec, "INC-001")

    token_alice = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-ALICE")
    token_bob = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-BOB")
    wf.approve_recommendation("REC-001", token_alice, "INC-001")

    with pytest.raises(IllegalStateTransitionError, match="Cannot reject recommendation .* in terminal state 'APPROVED'"):
        wf.reject_recommendation("REC-001", token_bob, "INC-001", "Changed mind")


def test_empty_or_unauthenticated_reviewer_rejected():
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-001")
    wf.register_recommendation(rec, "INC-001")

    with pytest.raises(ValueError, match="non-empty operator_id"):
        wf.approve_recommendation("REC-001", "", "INC-001")

    with pytest.raises(ValueError, match="non-empty operator_id"):
        wf.approve_recommendation("REC-001", "   ", "INC-001")

    with pytest.raises(UnauthenticatedReviewerError, match="not authorized"):
        AuthenticatedReviewer.create_verified(operator_id="ANONYMOUS")


def test_append_only_ledger_file_persistence(tmp_path):
    ledger_file = tmp_path / "test_approval_ledger.jsonl"
    wf = HumanApprovalWorkflow(ledger_path=ledger_file)
    rec = _sample_rec("REC-001")
    wf.register_recommendation(rec, "INC-001")

    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("OP-NOC-1")
    wf.approve_recommendation("REC-001", token, "INC-001", "Approved via ledger")

    assert ledger_file.exists()
    lines = ledger_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2  # SUBMITTED and APPROVED
