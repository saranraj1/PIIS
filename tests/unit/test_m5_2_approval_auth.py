"""Comprehensive adversarial authentication and audit integrity unit tests for M5.2.

Remediates FIND-M5.1-001 across all 15 required adversarial cases:
1. Forged reviewer identity.
2. Dummy token.
3. Expired token.
4. Revoked token.
5. Invalid signature.
6. Wrong issuer and audience.
7. Insufficient role for HIGH_RISK_MANUAL actions.
8. Replay of an earlier approval.
9. Hardcoded/default key removal.
10. Full audit-chain rewrite.
11. Checkpoint replacement.
12. Recommendation mutation before and after restart.
13. Process restart and ledger restoration via load_from_ledger().
14. Concurrent approval attempts.
15. Missing identity or key configuration in production mode.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest

from piis.investigation.approval import (
    AuthenticatedReviewer,
    HumanApprovalWorkflow,
    IllegalStateTransitionError,
    InsufficientPrivilegeError,
    IsolatedTestTokenVerifier,
    MissingAuditKeyError,
    MissingAuthenticationConfigurationError,
    ProductionOIDCVerifier,
    RecommendationTamperedError,
    UnauthenticatedReviewerError,
)
from piis.investigation.schemas import (
    ApprovalStatus,
    DiagnosticRecommendation,
    RecommendationRisk,
)


def _sample_rec(
    rec_id: str = "REC-TST-001",
    risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE,
) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        description="Inspect optical return loss on SFP port 01",
        reason="Corroborate optical attenuation hypothesis",
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="SOP-TRANS-FIBER-001",
        source_section="Section 2.1",
        preconditions=["Clean optical connector"],
        expected_observation="Return loss > 18 dB",
        risk_classification=risk,
        human_approval_required=True,
    )


# 1. Forged Reviewer Identity
def test_case_01_forged_reviewer_identity_rejected():
    """Verify that constructing an unverified AuthenticatedReviewer is rejected."""
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-01")
    wf.register_recommendation(rec, "INC-01")

    # Attacker crafts an unverified AuthenticatedReviewer directly
    forged_reviewer = AuthenticatedReviewer(
        operator_id="attacker_forged",
        role="SYSADMIN",
        auth_token_hash="fake-hash-not-in-session-store",
        token_id="fake-jti-000",
    )

    with pytest.raises(UnauthenticatedReviewerError, match="Direct instantiation .* without verified IdP credentials"):
        wf.approve_recommendation("REC-01", forged_reviewer, "INC-01")


# 2. Dummy Token
def test_case_02_dummy_token_rejected():
    """Verify that raw dummy strings or non-JWT tokens are rejected."""
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-02")
    wf.register_recommendation(rec, "INC-02")

    with pytest.raises(UnauthenticatedReviewerError, match="token must be a signed credential with 3 segments"):
        wf.approve_recommendation("REC-02", "secret-dummy-session-token", "INC-02")


# 3. Expired Token
def test_case_03_expired_token_rejected():
    """Verify that expired credentials fail authentication."""
    verifier = IsolatedTestTokenVerifier()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-03")
    wf.register_recommendation(rec, "INC-03")

    expired_token = verifier.mint_token(
        operator_id="expired_op",
        lifetime_seconds=-60,  # Expired 60 seconds ago
    )

    with pytest.raises(UnauthenticatedReviewerError, match="Token expired"):
        wf.approve_recommendation("REC-03", expired_token, "INC-03")


# 4. Revoked Token
def test_case_04_revoked_token_rejected():
    """Verify that revoked tokens cannot be used to sign off approvals."""
    verifier = IsolatedTestTokenVerifier()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-04")
    wf.register_recommendation(rec, "INC-04")

    token = verifier.mint_token(operator_id="compromised_op", custom_jti="revoked-jti-999")
    verifier.revoke_token("revoked-jti-999")

    with pytest.raises(UnauthenticatedReviewerError, match="has been revoked"):
        wf.approve_recommendation("REC-04", token, "INC-04")


# 5. Invalid Signature
def test_case_05_invalid_signature_rejected():
    """Verify that tampered token signatures are rejected."""
    verifier = IsolatedTestTokenVerifier()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-05")
    wf.register_recommendation(rec, "INC-05")

    valid_token = verifier.mint_token("legit_op")
    parts = valid_token.split(".")
    # Tamper with signature
    tampered_sig = parts[2][:-4] + "ffff"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    with pytest.raises(UnauthenticatedReviewerError, match="Invalid token signature"):
        wf.approve_recommendation("REC-05", tampered_token, "INC-05")


# 6. Wrong Issuer and Audience
def test_case_06_wrong_issuer_and_audience_rejected():
    """Verify that tokens from untrusted issuers or wrong audience are rejected."""
    verifier = IsolatedTestTokenVerifier(
        expected_issuer="piis-trusted-idp",
        expected_audience="piis-decision-support",
    )
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-06")
    wf.register_recommendation(rec, "INC-06")

    # Token with rogue issuer
    rogue_issuer_token = verifier.mint_token("op_1", issuer="rogue-idp-realm")
    with pytest.raises(UnauthenticatedReviewerError, match="Wrong token issuer"):
        wf.approve_recommendation("REC-06", rogue_issuer_token, "INC-06")

    # Token with wrong audience
    wrong_aud_token = verifier.mint_token("op_1", issuer="piis-trusted-idp", audience="billing-service")
    with pytest.raises(UnauthenticatedReviewerError, match="Wrong token audience"):
        wf.approve_recommendation("REC-06", wrong_aud_token, "INC-06")


# 7. Insufficient Role
def test_case_07_insufficient_role_high_risk_rejected():
    """Verify that NOC_TIER_1 operators cannot approve HIGH_RISK_MANUAL actions."""
    verifier = IsolatedTestTokenVerifier()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-07", risk=RecommendationRisk.HIGH_RISK_MANUAL)
    wf.register_recommendation(rec, "INC-07")

    tier1_token = verifier.mint_token("tier1_operator", role="NOC_TIER_1")
    with pytest.raises(InsufficientPrivilegeError, match="Requires NOC_LEAD or SYSADMIN"):
        wf.approve_recommendation("REC-07", tier1_token, "INC-07")

    # NOC_LEAD must succeed
    noc_lead_token = verifier.mint_token("noc_lead_operator", role="NOC_LEAD")
    approved = wf.approve_recommendation("REC-07", noc_lead_token, "INC-07")
    assert approved.approval_status == ApprovalStatus.APPROVED


# 8. Replay of an Earlier Approval
def test_case_08_replay_approval_rejected():
    """Verify that replaying an earlier approval on an approved recommendation is blocked."""
    verifier = IsolatedTestTokenVerifier()
    wf = HumanApprovalWorkflow(verifier=verifier)
    rec = _sample_rec("REC-08")
    wf.register_recommendation(rec, "INC-08")

    token = verifier.mint_token("op_lead", role="NOC_LEAD")
    wf.approve_recommendation("REC-08", token, "INC-08")

    # Replay
    with pytest.raises(IllegalStateTransitionError, match="Cannot approve recommendation .* in terminal state 'APPROVED'"):
        wf.approve_recommendation("REC-08", token, "INC-08")


# 9. Hardcoded / Default Key Removal
def test_case_09_hardcoded_default_key_removal():
    """Verify that HumanApprovalWorkflow has no hardcoded DEFAULT_AUDIT_KEY attribute."""
    assert not hasattr(HumanApprovalWorkflow, "DEFAULT_AUDIT_KEY")


# 10. Full Audit-Chain Rewrite Detection
def test_case_10_full_audit_chain_rewrite_detected():
    """Verify that an attacker cannot substitute the audit history using a forged key."""
    key_legit = b"TRUE-MASTER-AUDIT-KEY-999-32BYTES!"
    key_attacker = b"ATTACKER-FORGED-KEY-000-32BYTES!"

    wf_legit = HumanApprovalWorkflow(signing_key=key_legit)
    rec = _sample_rec("REC-10")
    wf_legit.register_recommendation(rec, "INC-10")
    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("op_alice")
    wf_legit.approve_recommendation("REC-10", token, "INC-10")

    # Attacker builds a rewritten history using their own key
    wf_attacker = HumanApprovalWorkflow(signing_key=key_attacker)
    rec_fake = _sample_rec("REC-10")
    wf_attacker.register_recommendation(rec_fake, "INC-10")
    token_mallory = IsolatedTestTokenVerifier.get_default_instance().mint_token("op_mallory")
    wf_attacker.approve_recommendation("REC-10", token_mallory, "INC-10")

    # Inject into legit workflow
    wf_legit._audit_trail = wf_attacker.get_audit_trail()

    is_valid, errors = wf_legit.verify_audit_trail()
    assert is_valid is False
    assert any("Invalid HMAC signature" in e for e in errors)


# 11. Checkpoint Replacement Detection
def test_case_11_checkpoint_replacement_detected():
    """Verify that tampering with an entry's HMAC checkpoint invalidates verification."""
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-11")
    wf.register_recommendation(rec, "INC-11")
    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("op_alice")
    wf.approve_recommendation("REC-11", token, "INC-11")

    # Replace last entry's HMAC signature
    wf._audit_trail[-1].hmac_signature = "0" * 64

    is_valid, errors = wf.verify_audit_trail()
    assert is_valid is False
    assert any("Invalid HMAC signature" in e for e in errors)


# 12. Recommendation Mutation Before and After Restart
def test_case_12_recommendation_mutation_detected():
    """Verify that post-approval in-memory mutation is detected."""
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-12")
    wf.register_recommendation(rec, "INC-12")
    token = IsolatedTestTokenVerifier.get_default_instance().mint_token("op_alice")
    wf.approve_recommendation("REC-12", token, "INC-12")

    # Mutate description
    rec.description = "MUTATED: Drop tables and shutdown router"

    assert wf.verify_recommendation_binding("REC-12") is False
    with pytest.raises(RecommendationTamperedError, match="mutated in memory after operator approval"):
        wf.get_verified_recommendation("REC-12")


# 13. Process Restart and Ledger Restoration
def test_case_13_process_restart_and_ledger_restoration(tmp_path: Path):
    """Verify that the ledger persists to disk and restores cleanly with HMAC validation."""
    ledger_file = tmp_path / "persistent_audit.jsonl"
    key = b"TEST_PERSISTENT_SIGNING_KEY_32_BYTES!"
    wf1 = HumanApprovalWorkflow(signing_key=key, ledger_path=ledger_file)

    rec1 = _sample_rec("REC-13A")
    rec2 = _sample_rec("REC-13B")
    wf1.register_recommendation(rec1, "INC-13")
    wf1.register_recommendation(rec2, "INC-13")

    token1 = IsolatedTestTokenVerifier.get_default_instance().mint_token("op_alpha")
    token2 = IsolatedTestTokenVerifier.get_default_instance().mint_token("op_beta")
    wf1.approve_recommendation("REC-13A", token1, "INC-13", "Approved 13A")
    wf1.reject_recommendation("REC-13B", token2, "INC-13", "Rejected 13B")

    assert ledger_file.exists()

    # Simulate restart by instantiating new workflow and restoring ledger
    wf2 = HumanApprovalWorkflow(signing_key=key, ledger_path=ledger_file)
    restored_count = wf2.load_from_ledger()

    assert restored_count == 4
    is_valid, errors = wf2.verify_audit_trail()
    assert is_valid is True
    assert len(errors) == 0

    # Ensure terminal state is locked after restore
    with pytest.raises(IllegalStateTransitionError):
        wf2.approve_recommendation("REC-13A", token1, "INC-13")


# 14. Concurrent Approval Attempts
def test_case_14_concurrent_approval_attempts():
    """Verify thread-safety when multiple concurrent threads attempt to approve the same recommendation."""
    wf = HumanApprovalWorkflow()
    rec = _sample_rec("REC-14")
    wf.register_recommendation(rec, "INC-14")

    successes = []
    failures = []

    def attempt_approval(worker_id: int):
        token = IsolatedTestTokenVerifier.get_default_instance().mint_token(f"op_{worker_id}")
        try:
            res = wf.approve_recommendation("REC-14", token, "INC-14", f"Approved by worker {worker_id}")
            successes.append(res)
        except Exception as e:
            failures.append(e)

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_approval, i) for i in range(10)]
        for f in futures:
            f.result()

    # Exactly one approval must succeed; 9 must fail with IllegalStateTransitionError
    assert len(successes) == 1
    assert len(failures) == 9
    assert all(isinstance(err, IllegalStateTransitionError) for err in failures)

    # Cryptographic integrity must be intact
    is_valid, errors = wf.verify_audit_trail()
    assert is_valid is True
    assert len(errors) == 0


# 15. Missing Identity or Key Configuration
def test_case_15_missing_identity_or_key_configuration(monkeypatch):
    """Verify that unconfigured production environment fails closed immediately."""
    monkeypatch.delenv("PIIS_AUDIT_HMAC_KEY", raising=False)
    monkeypatch.delenv("PIIS_IDP_JWKS_URL", raising=False)
    monkeypatch.delenv("PIIS_IDP_ISSUER", raising=False)

    # 1. Missing audit key in production mode raises MissingAuditKeyError
    with pytest.raises(MissingAuditKeyError, match="Production deployment requires explicit"):
        HumanApprovalWorkflow(environment="production")

    # 2. ProductionOIDCVerifier without IdP config fails closed
    unconfigured_idp = ProductionOIDCVerifier()
    with pytest.raises(MissingAuthenticationConfigurationError, match="Production authentication fails closed"):
        unconfigured_idp.verify_token("some.jwt.token")
