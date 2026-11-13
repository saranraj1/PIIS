"""Comprehensive Security, Persistence, Concurrency, and Integrity Audit Tests for Milestone UI-5.1.

Audits:
1. Critical Audit A: Authentication and Identity Boundaries (missing, expired, wrong issuer/aud, invalid sig, role, service principal, spoofing).
2. Critical Audit B: Approval State Machine & Concurrent Races (terminal states, 10-thread race safety, association mismatch, 404 not found, whitespace notes).
3. Critical Audit C: Persistence & Restart Recovery (JSONL ledger write, state reconstruction, terminal lockout persistence, tamper fail-closed).
4. Critical Audit D: Atomicity & Failure Injection (rollback on failed ledger append, zero state/ledger divergence).
5. Critical Audit E: Cryptographic Integrity (RFC 8785 canonicalization, HMAC-SHA256 tamper evidence, notes binding).
"""

from __future__ import annotations

import concurrent.futures
import json
import pytest
from fastapi.testclient import TestClient

from piis.api.app import create_app
from piis.api.routers import incidents
from piis.auth import ApplicationRole, AuthManager
from piis.investigation.approval import (
    ApprovalStatus,
    AuditTrailDiscontinuityError,
    FileBasedCheckpointAnchor,
    HumanApprovalWorkflow,
    IllegalStateTransitionError,
    IsolatedTestTokenVerifier,
    canonical_json_dumps,
)
from piis.investigation.schemas import (
    DiagnosticRecommendation,
    RecommendationRisk,
)


@pytest.fixture
def audit_setup(tmp_path):
    """Setup clean app, auth manager, verifier, and temporary ledger file."""
    app = create_app()
    client = TestClient(app)
    auth_mgr = AuthManager()
    verifier = IsolatedTestTokenVerifier.get_default_instance()
    ledger_path = tmp_path / "test_audit_ledger.jsonl"
    anchor_path = tmp_path / "test_anchor.json"
    anchor = FileBasedCheckpointAnchor(anchor_path)

    workflow = HumanApprovalWorkflow(
        signing_key=b"piis-dev-audit-key-32bytes-long!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    incidents.set_workflow(workflow)

    return {
        "app": app,
        "client": client,
        "auth": auth_mgr,
        "workflow": workflow,
        "verifier": verifier,
        "ledger_path": ledger_path,
        "anchor": anchor,
        "tmp_path": tmp_path,
    }


def _create_rec(
    rec_id: str,
    incident_id: str = "INC-AUDIT-001",
    risk: RecommendationRisk = RecommendationRisk.READ_ONLY_SAFE,
) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        incident_id=incident_id,
        description=f"Operational diagnostic procedure for {rec_id}",
        reason="Testing UI-5.1 security and persistence",
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="SOP-RAN-001",
        source_section="Section 2.1",
        expected_observation="Normal metrics observed",
        risk_classification=risk,
        human_approval_required=True,
    )


# ==============================================================================
# CRITICAL AUDIT A: AUTHENTICATION AND IDENTITY
# ==============================================================================

def test_audit_a1_missing_authentication_returns_401(audit_setup):
    """Missing Bearer authorization header must return 401 Unauthorized."""
    client = audit_setup["client"]
    res = client.post(
        "/api/v1/incidents/INC-001/reviews",
        json={
            "recommendation_id": "REC-001",
            "decision": "APPROVED",
            "review_notes": "Attempt without auth",
        },
    )
    assert res.status_code == 401
    assert "missing or malformed" in res.json()["detail"].lower()


def test_audit_a2_invalid_signature_returns_401(audit_setup):
    """Tampered or invalid JWT signature must be rejected with 401 Unauthorized."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    valid_token = auth.mint_dev_token("OP-LEGIT", role=ApplicationRole.NOC_L2)
    # Corrupt signature portion
    parts = valid_token.split(".")
    tampered_sig = "0" * len(parts[2])
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    res = client.post(
        "/api/v1/incidents/INC-001/reviews",
        json={
            "recommendation_id": "REC-001",
            "decision": "APPROVED",
            "review_notes": "Attempt with forged signature",
        },
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res.status_code == 401
    assert "authentication failed" in res.json()["detail"].lower()


def test_audit_a3_expired_token_returns_401(audit_setup):
    """Expired JWT must be rejected with 401 Unauthorized."""
    client = audit_setup["client"]
    verifier = audit_setup["verifier"]
    expired_token = verifier.mint_token("OP-EXPIRED", lifetime_seconds=-30)

    res = client.post(
        "/api/v1/incidents/INC-001/reviews",
        json={
            "recommendation_id": "REC-001",
            "decision": "APPROVED",
            "review_notes": "Attempt with expired token",
        },
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_audit_a4_wrong_issuer_and_audience_returns_401(audit_setup):
    """Token with untrusted issuer or audience must be rejected with 401 Unauthorized."""
    client = audit_setup["client"]
    verifier = audit_setup["verifier"]

    wrong_iss_token = verifier.mint_token("OP-UNTRUSTED", issuer="untrusted-foreign-idp")
    res_iss = client.post(
        "/api/v1/incidents/INC-001/reviews",
        json={"recommendation_id": "REC-001", "decision": "APPROVED", "review_notes": "Wrong issuer"},
        headers={"Authorization": f"Bearer {wrong_iss_token}"},
    )
    assert res_iss.status_code == 401
    assert "issuer" in res_iss.json()["detail"].lower()

    wrong_aud_token = verifier.mint_token("OP-UNTRUSTED", audience="wrong-service-aud")
    res_aud = client.post(
        "/api/v1/incidents/INC-001/reviews",
        json={"recommendation_id": "REC-001", "decision": "APPROVED", "review_notes": "Wrong aud"},
        headers={"Authorization": f"Bearer {wrong_aud_token}"},
    )
    assert res_aud.status_code == 401
    assert "audience" in res_aud.json()["detail"].lower()


def test_audit_a5_missing_human_reviewer_role_returns_403(audit_setup):
    """Users without operational review roles (e.g. SECURITY_AUDITOR, PIIS_ADMIN) return 403."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]

    rec = _create_rec("REC-ROLE-01", "INC-ROLE-01")
    workflow.register_recommendation(rec, "INC-ROLE-01")

    auditor_token = auth.mint_dev_token("auditor-user", role=ApplicationRole.SECURITY_AUDITOR)
    res = client.post(
        "/api/v1/incidents/INC-ROLE-01/reviews",
        json={"recommendation_id": "REC-ROLE-01", "decision": "APPROVED", "review_notes": "Auditor review"},
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert res.status_code == 403
    assert "lacks review authorization" in res.json()["detail"].lower()


def test_audit_a6_service_principal_token_returns_403(audit_setup):
    """Service principals must be strictly barred from human review sign-offs (403 Forbidden)."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]

    rec = _create_rec("REC-SVC-01", "INC-SVC-01")
    workflow.register_recommendation(rec, "INC-SVC-01")

    svc_token = auth.mint_dev_token("svc-collector", is_service=True)
    res = client.post(
        "/api/v1/incidents/INC-SVC-01/reviews",
        json={"recommendation_id": "REC-SVC-01", "decision": "APPROVED", "review_notes": "Automated approval"},
        headers={"Authorization": f"Bearer {svc_token}"},
    )
    assert res.status_code == 403
    assert "automated service account" in res.json()["detail"].lower()


def test_audit_a7_forged_operator_id_in_payload_ignored(audit_setup):
    """Client request body tampering cannot spoof reviewer identity; token claims take precedence."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]

    rec = _create_rec("REC-SPOOF-01", "INC-SPOOF-01")
    workflow.register_recommendation(rec, "INC-SPOOF-01")

    legit_token = auth.mint_dev_token("OP-REAL-OPERATOR", role=ApplicationRole.NOC_L2)
    res = client.post(
        "/api/v1/incidents/INC-SPOOF-01/reviews",
        json={
            "recommendation_id": "REC-SPOOF-01",
            "decision": "APPROVED",
            "review_notes": "Legitimate operator review",
            "operator_id": "IMPOSTOR_ROOT",
            "reviewed_by": "ATTACKER",
        },
        headers={"Authorization": f"Bearer {legit_token}"},
    )
    assert res.status_code == 200
    receipt = res.json()
    assert receipt["status"] == "RECORDED_IN_AUDIT_CHAIN"
    assert receipt["reviewed_by"] == "OP-REAL-OPERATOR"
    assert receipt["reviewed_by"] != "IMPOSTOR_ROOT"


def test_audit_a8_malformed_identity_claims_returns_401(audit_setup):
    """Garbled, truncated, or non-JWT tokens return 401 Unauthorized."""
    client = audit_setup["client"]
    for bad_token in ["not-a-token", "a.b", "...", "eyJhbGciOiJIUzI1NiJ9.malformed"]:
        res = client.post(
            "/api/v1/incidents/INC-001/reviews",
            json={"recommendation_id": "REC-001", "decision": "APPROVED", "review_notes": "Bad token"},
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert res.status_code == 401


def test_audit_a9_concurrent_requests_using_distinct_reviewers(audit_setup):
    """Concurrent requests by distinct authenticated operators on different recommendations succeed independently."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]

    tokens = [
        auth.mint_dev_token(f"OP-OPERATOR-{i}", role=ApplicationRole.NOC_L2)
        for i in range(5)
    ]
    recs = [_create_rec(f"REC-CONC-DIST-{i}", f"INC-CONC-{i}") for i in range(5)]
    for r in recs:
        workflow.register_recommendation(r, r.incident_id)

    def submit_review(idx):
        return client.post(
            f"/api/v1/incidents/INC-CONC-{idx}/reviews",
            json={
                "recommendation_id": f"REC-CONC-DIST-{idx}",
                "decision": "APPROVED",
                "review_notes": f"Concurrent review by operator {idx}",
            },
            headers={"Authorization": f"Bearer {tokens[idx]}"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(submit_review, range(5)))

    assert all(r.status_code == 200 for r in responses)
    for idx, r in enumerate(responses):
        data = r.json()
        assert data["reviewed_by"] == f"OP-OPERATOR-{idx}"
        assert data["decision"] == "APPROVED"


# ==============================================================================
# CRITICAL AUDIT B: APPROVAL STATE MACHINE & CONCURRENCY
# ==============================================================================

def test_audit_b1_conflicting_concurrent_submissions_exactly_one_succeeds(audit_setup):
    """10 concurrent threads racing to approve and reject the same recommendation: exactly 1 succeeds."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]

    rec = _create_rec("REC-RACE-001", "INC-RACE-001")
    workflow.register_recommendation(rec, "INC-RACE-001")

    token = auth.mint_dev_token("OP-RACE-RUNNER", role=ApplicationRole.NOC_L2)

    def race_submit(thread_idx: int):
        decision = "APPROVED" if thread_idx % 2 == 0 else "REJECTED"
        return client.post(
            "/api/v1/incidents/INC-RACE-001/reviews",
            json={
                "recommendation_id": "REC-RACE-001",
                "decision": decision,
                "review_notes": f"Race submission from thread {thread_idx}",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(race_submit, range(10)))

    successes = [r for r in results if r.status_code == 200]
    conflicts = [r for r in results if r.status_code == 409]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == 9, f"Expected exactly 9 conflicts (409), got {len(conflicts)}"

    # Recommendation must be in exactly one terminal state
    updated = workflow.get_recommendation("REC-RACE-001")
    assert updated.approval_status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}
    winning_decision = successes[0].json()["decision"]
    assert updated.approval_status.value == winning_decision


def test_audit_b2_terminal_state_replay_fails_with_409(audit_setup):
    """Re-approving or re-rejecting a terminal recommendation yields 409 Conflict."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]

    rec = _create_rec("REC-TERM-001", "INC-TERM-001")
    workflow.register_recommendation(rec, "INC-TERM-001")

    token = auth.mint_dev_token("OP-TERM-01", role=ApplicationRole.NOC_L2)

    # 1. First approval: succeeds
    r1 = client.post(
        "/api/v1/incidents/INC-TERM-001/reviews",
        json={"recommendation_id": "REC-TERM-001", "decision": "APPROVED", "review_notes": "Initial approval"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200

    # 2. Duplicate approval: returns 409
    r2 = client.post(
        "/api/v1/incidents/INC-TERM-001/reviews",
        json={"recommendation_id": "REC-TERM-001", "decision": "APPROVED", "review_notes": "Duplicate re-approval"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409

    # 3. Subsequent rejection attempt on approved item: returns 409
    r3 = client.post(
        "/api/v1/incidents/INC-TERM-001/reviews",
        json={"recommendation_id": "REC-TERM-001", "decision": "REJECTED", "review_notes": "Conflicting rejection"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 409


def test_audit_b3_invalid_decision_values_rejected_with_400(audit_setup):
    """Unsupported decision strings (REQUEST_MORE_EVIDENCE, MAYBE, DEFER) return 400 Bad Request."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    token = auth.mint_dev_token("OP-TIER2", role=ApplicationRole.NOC_L2)

    for invalid_val in ["REQUEST_MORE_EVIDENCE", "MAYBE", "DEFER", "HOLD", ""]:
        res = client.post(
            "/api/v1/incidents/INC-001/reviews",
            json={"recommendation_id": "REC-001", "decision": invalid_val, "review_notes": "Notes"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "APPROVED" in res.json()["detail"]


def test_audit_b4_missing_or_whitespace_notes_rejected_with_422(audit_setup):
    """Blank or whitespace-only reviewer notes must be rejected by schema validator."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    token = auth.mint_dev_token("OP-TIER2", role=ApplicationRole.NOC_L2)

    for empty_note in ["", "   ", "\t\n  "]:
        res = client.post(
            "/api/v1/incidents/INC-001/reviews",
            json={"recommendation_id": "REC-001", "decision": "APPROVED", "review_notes": empty_note},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Pydantic field_validator raises ValueError -> HTTP 422
        assert res.status_code == 422


def test_audit_b5_recommendation_not_found_returns_404(audit_setup):
    """Submitting review for non-existent recommendation ID returns 404 Not Found."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    token = auth.mint_dev_token("OP-TIER2", role=ApplicationRole.NOC_L2)

    res = client.post(
        "/api/v1/incidents/INC-001/reviews",
        json={"recommendation_id": "REC-NON-EXISTENT-999", "decision": "APPROVED", "review_notes": "Valid note"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_audit_b6_incident_association_mismatch_returns_400(audit_setup):
    """Submitting review for recommendation associated with a different incident returns 400 Bad Request."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]

    rec = _create_rec("REC-INC-MISMATCH", incident_id="INC-PRIMARY")
    workflow.register_recommendation(rec, "INC-PRIMARY")

    token = auth.mint_dev_token("OP-TIER2", role=ApplicationRole.NOC_L2)

    # Attempt to approve under INC-FOREIGN instead of INC-PRIMARY
    res = client.post(
        "/api/v1/incidents/INC-FOREIGN/reviews",
        json={"recommendation_id": "REC-INC-MISMATCH", "decision": "APPROVED", "review_notes": "Mismatch attempt"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "incident association mismatch" in res.json()["detail"].lower()


# ==============================================================================
# CRITICAL AUDIT C & D: PERSISTENCE, RESTART RECOVERY & ATOMICITY
# ==============================================================================

def test_audit_c1_durable_ledger_append_and_restart_recovery(audit_setup):
    """Workflow writes to JSONL on disk; process restart reconstructs terminal states and receipts."""
    client = audit_setup["client"]
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]
    ledger_path = audit_setup["ledger_path"]
    anchor = audit_setup["anchor"]
    verifier = audit_setup["verifier"]

    rec = _create_rec("REC-DURABLE-01", "INC-DURABLE-01")
    workflow.register_recommendation(rec, "INC-DURABLE-01")

    token = auth.mint_dev_token("OP-DURABLE-01", role=ApplicationRole.NOC_L2)

    # Submit approval
    res = client.post(
        "/api/v1/incidents/INC-DURABLE-01/reviews",
        json={"recommendation_id": "REC-DURABLE-01", "decision": "APPROVED", "review_notes": "Persistent approval note"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    receipt = res.json()
    assert receipt["status"] == "RECORDED_IN_AUDIT_CHAIN"

    # Verify JSONL file exists and contains 2 records (SUBMITTED + APPROVED)
    assert ledger_path.exists()
    lines = [line.strip() for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2

    # Simulate process restart by instantiating a completely new workflow instance loading from disk
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-dev-audit-key-32bytes-long!",
        verifier=verifier,
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )
    loaded_count = restarted_wf.load_from_ledger()
    assert loaded_count == 2

    # Verify restored state
    restored_rec = restarted_wf.get_recommendation("REC-DURABLE-01")
    assert restored_rec is not None
    assert restored_rec.approval_status == ApprovalStatus.APPROVED
    assert restored_rec.reviewed_by == "OP-DURABLE-01"
    assert restored_rec.review_notes == "Persistent approval note"
    assert restarted_wf.get_recommendation_incident("REC-DURABLE-01") == "INC-DURABLE-01"

    # Verify terminal lockout is preserved across restart
    with pytest.raises(IllegalStateTransitionError):
        restarted_wf.approve_recommendation(
            "REC-DURABLE-01",
            operator_id=token,
            incident_id="INC-DURABLE-01",
            notes="Second attempt after restart",
        )

    # Verify audit trail continuity verification passes
    valid, errors = restarted_wf.verify_audit_trail()
    assert valid is True
    assert errors == []


def test_audit_c2_tampered_ledger_file_fails_closed_on_restart(audit_setup):
    """Tampering with a line in the durable ledger file causes load_from_ledger to fail closed."""
    auth = audit_setup["auth"]
    workflow = audit_setup["workflow"]
    ledger_path = audit_setup["ledger_path"]
    verifier = audit_setup["verifier"]

    rec = _create_rec("REC-TAMPER-01", "INC-TAMPER-01")
    workflow.register_recommendation(rec, "INC-TAMPER-01")

    token = auth.mint_dev_token("OP-TAMPER", role=ApplicationRole.NOC_L2)
    workflow.approve_recommendation("REC-TAMPER-01", token, "INC-TAMPER-01", "Notes before tampering")

    # Tamper with the file: change a byte in the approved entry's notes
    lines = [line.strip() for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    tampered_entry = json.loads(lines[-1])
    tampered_entry["notes"] = "TAMPERED NOTES IN STORAGE"
    lines[-1] = json.dumps(tampered_entry)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Restart attempt must fail closed with AuditTrailDiscontinuityError
    restarted_wf = HumanApprovalWorkflow(
        signing_key=b"piis-dev-audit-key-32bytes-long!",
        verifier=verifier,
        ledger_path=ledger_path,
    )
    with pytest.raises(AuditTrailDiscontinuityError) as exc_info:
        restarted_wf.load_from_ledger()
    assert "tampered" in str(exc_info.value).lower() or "hmac" in str(exc_info.value).lower()


def test_audit_d1_atomicity_failure_injection_rolls_back_memory_state(audit_setup):
    """If ledger append fails, in-memory state rolls back to PENDING_REVIEW (no state/ledger divergence)."""
    workflow = audit_setup["workflow"]
    rec = _create_rec("REC-ATOMIC-01", "INC-ATOMIC-01")
    workflow.register_recommendation(rec, "INC-ATOMIC-01")

    token = audit_setup["auth"].mint_dev_token("OP-ATOMIC", role=ApplicationRole.NOC_L2)

    # Monkey-patch _create_and_append_entry to simulate a disk full / I/O error
    original_create = workflow._create_and_append_entry

    def broken_create(*args, **kwargs):
        raise IOError("Simulated disk write failure: ENOSPC (no space left on device)")

    workflow._create_and_append_entry = broken_create

    with pytest.raises(IOError) as exc_info:
        workflow.approve_recommendation("REC-ATOMIC-01", token, "INC-ATOMIC-01", "Notes")
    assert "ENOSPC" in str(exc_info.value)

    # In-memory recommendation MUST have rolled back to PENDING_REVIEW
    current_rec = workflow.get_recommendation("REC-ATOMIC-01")
    assert current_rec.approval_status == ApprovalStatus.PENDING_REVIEW
    assert current_rec.reviewed_by is None
    assert current_rec.review_timestamp is None

    # Restore method: now approval succeeds cleanly
    workflow._create_and_append_entry = original_create
    success_rec = workflow.approve_recommendation("REC-ATOMIC-01", token, "INC-ATOMIC-01", "Valid note")
    assert success_rec.approval_status == ApprovalStatus.APPROVED


# ==============================================================================
# CRITICAL AUDIT E: CRYPTOGRAPHIC INTEGRITY
# ==============================================================================

def test_audit_e1_rfc8785_canonicalization_and_hmac_tamper_evidence():
    """Verify RFC 8785 deterministic serialization and HMAC-SHA256 authenticated tamper-evidence."""
    payload_a = {"sequence_number": 1, "action": "APPROVED", "notes": "Zebra", "operator_id": "OP-01"}
    payload_b = {"operator_id": "OP-01", "notes": "Zebra", "action": "APPROVED", "sequence_number": 1}

    # Keys sorted, whitespace eliminated
    canon_a = canonical_json_dumps(payload_a)
    canon_b = canonical_json_dumps(payload_b)
    assert canon_a == canon_b
    assert canon_a == '{"action":"APPROVED","notes":"Zebra","operator_id":"OP-01","sequence_number":1}'

    # Modifying any single character invalidates HMAC
    key = b"piis-dev-audit-key-32bytes-long!"
    sig_original = canonical_json_dumps(payload_a).encode("utf-8")
    import hmac
    import hashlib
    h1 = hmac.new(key, sig_original, hashlib.sha256).hexdigest()

    tampered_payload = dict(payload_a)
    tampered_payload["notes"] = "zebra"  # lower-case alteration
    h2 = hmac.new(key, canonical_json_dumps(tampered_payload).encode("utf-8"), hashlib.sha256).hexdigest()

    assert h1 != h2, "HMAC must change upon note content alteration"
