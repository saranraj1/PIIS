"""Adversarial and independent verification tests for PIIS UI-6.1.

Covers the complete adversarial verification test matrix:
1. Entire valid ledger -> VERIFIED.
2. Filtered record query separation -> Never presented as full-ledger verification.
3. Missing HMAC key -> UNAVAILABLE.
4. Incorrect HMAC signature -> FAILED.
5. Broken hash chain -> FAILED.
6. Missing sequence (gap) -> FAILED.
7. Malformed record on disk -> FAILED or INCOMPLETE.
8. Missing checkpoint anchor -> UNAVAILABLE or FAILED.
9. Corrupted checkpoint anchor -> FAILED.
10. Ledger ahead of anchor -> FAILED.
11. Anchor ahead of ledger -> FAILED.
12. Coordinated ledger and anchor rollback -> Explicit local boundary qualification.
13. Empty ledger genesis semantics -> VERIFIED only if genuine; UNAVAILABLE if anchor missing.
14. Large ledger pagination & full-scope verification -> Limit/offset & records_checked == total.
15. Verification request immutability -> Byte-for-byte identical files before and after verification.
16. Recovery override (force_override) injection rejection -> Ineffective via API.
17. Unauthorized user rejection -> 401 unauthenticated, 403 unauthorized.
18. Concurrent read and verification operations -> Thread safety under concurrent load.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
import pytest

from piis.api.app import create_app
from piis.api.routers.incidents import get_workflow
from piis.auth import ApplicationRole, AuthManager
from piis.investigation.approval import (
    DiagnosticRecommendation,
    FileBasedCheckpointAnchor,
    HumanApprovalWorkflow,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def auth_manager():
    return AuthManager()


def _make_rec(
    rec_id: str,
    desc: str,
    action: str = "ROUTING",
    risk: str = "READ_ONLY_SAFE",
    incident_id: str = "INC-101",
) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        incident_id=incident_id,
        description=desc,
        reason="Testing UI-6.1 adversarial verification matrix",
        action_type=action,
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="RB-001",
        source_section="Section 1.1",
        expected_observation="Normal metrics restored",
        risk_classification=risk,
    )


def _setup_seeded_workflow(temp_dir, auth_manager, num_records: int = 3):
    ledger_path = temp_dir / "audit_log.jsonl"
    anchor_path = temp_dir / "checkpoint.json"
    anchor = FileBasedCheckpointAnchor(anchor_path=anchor_path)
    wf = HumanApprovalWorkflow(
        signing_key=b"test-secret-key-32-bytes-long-ok",
        key_id="test-key-01",
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )

    for i in range(1, num_records + 1):
        rec_id = f"REC-{i:03d}"
        inc_id = f"INC-{(i % 2) + 1:03d}"
        r = _make_rec(rec_id, f"Action description {i}", "CHECK_METRICS", "READ_ONLY_SAFE", inc_id)
        wf.register_recommendation(r, inc_id)

    token = auth_manager.mint_dev_token("alice", role=ApplicationRole.NOC_L2)
    if num_records >= 1:
        wf.approve_recommendation("REC-001", token, "INC-002", notes="Verified by NOC.")

    return wf, ledger_path, anchor_path


# ---------------------------------------------------------------------------
# 1. Entire Valid Ledger -> VERIFIED
# ---------------------------------------------------------------------------

def test_entire_valid_ledger_verified(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)
    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["verification_status"] == "VERIFIED"
    assert data["hash_chain_valid"] is True
    assert data["jcs_canonicalization_valid"] is True
    assert data["hmac_signatures_valid"] is True
    assert data["checkpoint_parity_valid"] is True
    assert data["verification_scope"] == "FULL_LEDGER"
    assert len(data["errors"]) == 0


# ---------------------------------------------------------------------------
# 2. Filtered Record Query Separation
# ---------------------------------------------------------------------------

def test_filtered_record_query_cannot_subvert_full_ledger_verification(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=3)
    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)
    headers = {"Authorization": f"Bearer {token}"}

    # Query a filtered subset of records (e.g. limit=1, specific action)
    res_filtered = client.get("/api/v1/audit/records?limit=1&action=APPROVED", headers=headers)
    assert res_filtered.status_code == 200
    filtered_data = res_filtered.json()
    assert len(filtered_data["items"]) == 1
    assert filtered_data["total_count"] == 1

    # Verify endpoint MUST still verify the ENTIRE ledger (all 4 events: 3 registers + 1 approve)
    res_verify = client.get("/api/v1/audit/verify?limit=1&action=APPROVED", headers=headers)
    assert res_verify.status_code == 200
    verify_data = res_verify.json()
    assert verify_data["verification_scope"] == "FULL_LEDGER"
    assert verify_data["records_checked"] == 4
    assert verify_data["total_records"] == 4
    assert verify_data["verification_status"] == "VERIFIED"


# ---------------------------------------------------------------------------
# 3. Missing HMAC Key -> UNAVAILABLE
# ---------------------------------------------------------------------------

def test_missing_hmac_key_returns_unavailable(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        wf._signing_key = None

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "UNAVAILABLE"
    assert data["hmac_signatures_valid"] is False
    assert any("signing key unavailable" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# 4. Incorrect HMAC Signature -> FAILED
# ---------------------------------------------------------------------------

def test_incorrect_hmac_signature_detected_as_failed(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        # Corrupt the HMAC signature on entry 1
        entry = wf._audit_trail[0]
        corrupted_dict = entry.model_dump()
        corrupted_dict["hmac_signature"] = "deadbeef" * 8
        wf._audit_trail[0] = entry.__class__.model_validate(corrupted_dict)

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert data["hmac_signatures_valid"] is False
    assert any("Invalid HMAC signature" in err for err in data["errors"])


# ---------------------------------------------------------------------------
# 5. Broken Hash Chain -> FAILED
# ---------------------------------------------------------------------------

def test_broken_hash_chain_detected_as_failed(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)
    with wf._lock:
        # Corrupt previous_entry_sha256 on entry 2
        entry = wf._audit_trail[1]
        corrupted_dict = entry.model_dump()
        corrupted_dict["previous_entry_sha256"] = "0000" * 16
        wf._audit_trail[1] = entry.__class__.model_validate(corrupted_dict)

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert data["hash_chain_valid"] is False
    assert any("Broken hash chain" in err for err in data["errors"])


# ---------------------------------------------------------------------------
# 6. Missing Sequence (Discontinuity) -> FAILED
# ---------------------------------------------------------------------------

def test_missing_sequence_discontinuity_detected_as_failed(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)
    with wf._lock:
        # Modify sequence number of entry 2 to 3 (creating a gap at seq 2)
        entry = wf._audit_trail[1]
        corrupted_dict = entry.model_dump()
        corrupted_dict["sequence_number"] = 3
        wf._audit_trail[1] = entry.__class__.model_validate(corrupted_dict)

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert data["hash_chain_valid"] is False
    assert any("Sequence discontinuity" in err for err in data["errors"])


# ---------------------------------------------------------------------------
# 7. Malformed Record on Disk -> FAILED or INCOMPLETE
# ---------------------------------------------------------------------------

def test_malformed_record_on_disk_detected(temp_dir, auth_manager):
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)

    # Append a corrupted, incomplete JSON line to the ledger file
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('{"sequence_number": 3, "audit_id": "REC-CORRUPTED", "truncated_json\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] in ("FAILED", "INCOMPLETE")
    assert any("Malformed or truncated record" in err for err in data["errors"])


# ---------------------------------------------------------------------------
# 8. Missing Checkpoint Anchor -> UNAVAILABLE
# ---------------------------------------------------------------------------

def test_missing_checkpoint_anchor_returns_unavailable(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        wf._checkpoint_anchor = None

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "UNAVAILABLE"
    assert data["anchor_present"] is False
    assert data["checkpoint_parity_valid"] is False
    assert any("not configured or unavailable" in err for err in data["errors"])


# ---------------------------------------------------------------------------
# 9. Corrupted Checkpoint Anchor -> FAILED
# ---------------------------------------------------------------------------

def test_corrupted_checkpoint_anchor_detected_as_failed(temp_dir, auth_manager):
    wf, _, anchor_path = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)

    # Overwrite anchor with unparseable binary noise
    anchor_path.write_bytes(b"\x00\xff\xfe\x01\x02\x03CORRUPTED_ANCHOR")

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert data["checkpoint_parity_valid"] is False
    assert any("read error" in err.lower() or "exception" in err.lower() or "anchor" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# 10. Ledger Ahead of Anchor -> FAILED
# ---------------------------------------------------------------------------

def test_ledger_ahead_of_anchor_detected_as_failed(temp_dir, auth_manager):
    wf, _, anchor_path = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # The workflow has 2 entries (register REC-001 + approve REC-001)
    # Set anchor back to sequence 1 (ledger is ahead of anchor)
    anchor_dict = {
        "audit_id": "REC-001",
        "sequence_number": 1,
        "entry_sha256": wf._audit_trail[0].entry_sha256,
        "hmac_signature": wf._audit_trail[0].hmac_signature,
        "timestamp_utc": wf._audit_trail[0].timestamp_utc,
    }
    anchor_path.write_text(json.dumps(anchor_dict), encoding="utf-8")

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert data["checkpoint_parity_valid"] is False
    assert any("DESYNCHRONIZATION" in err or "ahead of" in err for err in data["errors"])


# ---------------------------------------------------------------------------
# 11. Anchor Ahead of Ledger -> FAILED
# ---------------------------------------------------------------------------

def test_anchor_ahead_of_ledger_detected_as_failed(temp_dir, auth_manager):
    wf, _, anchor_path = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # Anchor set to sequence 99 (ledger is sequence 2)
    anchor_dict = {
        "audit_id": "FUTURE-099",
        "sequence_number": 99,
        "entry_sha256": "aaaa" * 16,
        "hmac_signature": "bbbb" * 16,
        "timestamp_utc": "2026-11-04T12:00:00Z",
    }
    anchor_path.write_text(json.dumps(anchor_dict), encoding="utf-8")

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert data["checkpoint_parity_valid"] is False
    assert any("ROLLBACK" in err or "older than" in err for err in data["errors"])


# ---------------------------------------------------------------------------
# 12. Coordinated Ledger and Anchor Rollback (Local Boundary Limitation)
# ---------------------------------------------------------------------------

def test_coordinated_ledger_and_anchor_rollback_boundary_proof(temp_dir, auth_manager):
    """Proves that simultaneous multi-file rollback to a valid historical snapshot (sequence 1)
    passes local parity checks. This documents the explicit security limitation:
    Local parity checking detects uncoordinated single-file truncation or desync, but cannot
    prevent coordinated host-level snapshot restoration without external cloud WORM / KMS anchor.
    """
    wf, ledger_path, anchor_path = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # Currently 2 entries exist in ledger:
    # Seq 1: SUBMITTED
    # Seq 2: APPROVED
    assert len(wf._audit_trail) == 2

    # Save exact state of sequence 1
    seq1_json = wf._audit_trail[0].model_dump_json()
    seq1_anchor = {
        "audit_id": wf._audit_trail[0].audit_id,
        "sequence_number": 1,
        "entry_sha256": wf._audit_trail[0].entry_sha256,
        "hmac_signature": wf._audit_trail[0].hmac_signature,
        "timestamp_utc": wf._audit_trail[0].timestamp_utc,
    }

    # Simulate coordinated filesystem snapshot restore back to sequence 1:
    ledger_path.write_text(seq1_json + "\n", encoding="utf-8")
    anchor_path.write_text(json.dumps(seq1_anchor), encoding="utf-8")

    # Fresh process boots from the restored snapshot
    anchor2 = FileBasedCheckpointAnchor(anchor_path=anchor_path)
    wf2 = HumanApprovalWorkflow(
        signing_key=b"test-secret-key-32-bytes-long-ok",
        ledger_path=ledger_path,
        checkpoint_anchor=anchor2,
    )
    wf2.load_from_ledger()

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf2
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    # Coordinated rollback passes local checks because sequence 1 is mathematically internally consistent!
    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["verification_status"] == "VERIFIED"
    assert data["total_records"] == 1
    # This precisely proves why limitations disclaimer is mandatory on UI and API!
    assert any("cannot prevent coordinated host-level snapshot restoration" in lim for lim in data["limitations"])


# ---------------------------------------------------------------------------
# 13. Empty Ledger Genesis Semantics
# ---------------------------------------------------------------------------

def test_empty_ledger_missing_anchor_returns_unavailable(temp_dir, auth_manager):
    # Workflow with no anchor configured
    wf = HumanApprovalWorkflow(
        signing_key=b"test-key-32-bytes-long-ok!!12345",
        checkpoint_anchor=None,
    )
    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "UNAVAILABLE"
    assert data["anchor_present"] is False


# ---------------------------------------------------------------------------
# 14. Large Ledger Pagination & Full-Scope Verification
# ---------------------------------------------------------------------------

def test_large_ledger_pagination_and_full_verification(temp_dir, auth_manager):
    anchor_path = temp_dir / "large_anchor.json"
    ledger_path = temp_dir / "large_ledger.jsonl"
    anchor = FileBasedCheckpointAnchor(anchor_path=anchor_path)
    wf = HumanApprovalWorkflow(
        signing_key=b"test-secret-key-32-bytes-long-ok",
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )

    # Register 120 recommendations
    for i in range(1, 121):
        rec = _make_rec(f"REC-{i:04d}", f"Bulk check {i}")
        wf.register_recommendation(rec, "INC-BULK")

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)
    headers = {"Authorization": f"Bearer {token}"}

    # Test pagination: default limit 50, page 1 (records 1..50)
    res_p1 = client.get("/api/v1/audit/records?limit=50&offset=0&order=asc", headers=headers)
    assert res_p1.status_code == 200
    p1_data = res_p1.json()
    assert p1_data["total_count"] == 120
    assert len(p1_data["items"]) == 50
    assert p1_data["items"][0]["sequence_number"] == 1
    assert p1_data["items"][-1]["sequence_number"] == 50

    # Page 2 (records 51..100)
    res_p2 = client.get("/api/v1/audit/records?limit=50&offset=50&order=asc", headers=headers)
    assert res_p2.status_code == 200
    p2_data = res_p2.json()
    assert len(p2_data["items"]) == 50
    assert p2_data["items"][0]["sequence_number"] == 51

    # Page 3 (records 101..120)
    res_p3 = client.get("/api/v1/audit/records?limit=50&offset=100&order=asc", headers=headers)
    assert res_p3.status_code == 200
    p3_data = res_p3.json()
    assert len(p3_data["items"]) == 20
    assert p3_data["items"][-1]["sequence_number"] == 120

    # Full ledger verification verifies ALL 120 records
    res_ver = client.get("/api/v1/audit/verify", headers=headers)
    assert res_ver.status_code == 200
    ver_data = res_ver.json()
    assert ver_data["is_valid"] is True
    assert ver_data["verification_status"] == "VERIFIED"
    assert ver_data["records_checked"] == 120
    assert ver_data["total_records"] == 120
    assert ver_data["first_sequence"] == 1
    assert ver_data["last_sequence"] == 120


# ---------------------------------------------------------------------------
# 15. Verification Request Immutability (Zero State Mutation)
# ---------------------------------------------------------------------------

def test_verification_request_causes_zero_file_or_state_mutation(temp_dir, auth_manager):
    wf, ledger_path, anchor_path = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)

    ledger_bytes_before = ledger_path.read_bytes()
    ledger_hash_before = hashlib.sha256(ledger_bytes_before).hexdigest()

    anchor_bytes_before = anchor_path.read_bytes()
    anchor_hash_before = hashlib.sha256(anchor_bytes_before).hexdigest()

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    # Execute verify 5 times in succession
    for _ in range(5):
        res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["is_valid"] is True

    # Assert exact byte-level identity on disk
    ledger_bytes_after = ledger_path.read_bytes()
    ledger_hash_after = hashlib.sha256(ledger_bytes_after).hexdigest()
    assert ledger_hash_before == ledger_hash_after
    assert ledger_bytes_before == ledger_bytes_after

    anchor_bytes_after = anchor_path.read_bytes()
    anchor_hash_after = hashlib.sha256(anchor_bytes_after).hexdigest()
    assert anchor_hash_before == anchor_hash_after
    assert anchor_bytes_before == anchor_bytes_after


# ---------------------------------------------------------------------------
# 16. Recovery Override (force_override) Injection Ineffectiveness
# ---------------------------------------------------------------------------

def test_recovery_override_injection_ineffective_via_api(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to inject force_override via query parameters across all audit endpoints
    urls = [
        "/api/v1/audit/records?force_override=true",
        "/api/v1/audit/records/1?force_override=true",
        "/api/v1/audit/summary?force_override=true",
        "/api/v1/audit/verify?force_override=true",
    ]
    for u in urls:
        res = client.get(u, headers=headers)
        assert res.status_code == 200  # Query param is ignored, never passes to anchor

    # Attempt to POST / PUT with force_override body (must return 405 Method Not Allowed)
    for u in ["/api/v1/audit/verify", "/api/v1/audit/records", "/api/v1/audit/summary"]:
        res_post = client.post(u, json={"force_override": True}, headers=headers)
        assert res_post.status_code in (404, 405)
        res_put = client.put(u, json={"force_override": True}, headers=headers)
        assert res_put.status_code in (404, 405)


# ---------------------------------------------------------------------------
# 17. Unauthorized User Rejection
# ---------------------------------------------------------------------------

def test_unauthorized_user_rejection(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)

    # 1. Unauthenticated (no token) -> 401
    res_no_auth = client.get("/api/v1/audit/verify")
    assert res_no_auth.status_code == 401

    # 2. Token with insufficient role (NOC_L1 has VIEW_INCIDENTS, not VERIFY_AUDIT_LEDGER) -> 403
    token_noc1 = auth_manager.mint_dev_token("noc1", role=ApplicationRole.NOC_L1)
    res_l1 = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token_noc1}"})
    assert res_l1.status_code == 403

    # 3. Token with correct permission (SECURITY_AUDITOR has VERIFY_AUDIT_LEDGER) -> 200
    token_auditor = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)
    res_auditor = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token_auditor}"})
    assert res_auditor.status_code == 200


# ---------------------------------------------------------------------------
# 18. Concurrent Read and Verification Operations
# ---------------------------------------------------------------------------

def test_concurrent_read_and_verification_operations(temp_dir, auth_manager):
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=5)
    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)
    headers = {"Authorization": f"Bearer {token}"}

    def _call_records():
        return client.get("/api/v1/audit/records?limit=10", headers=headers).status_code

    def _call_verify():
        return client.get("/api/v1/audit/verify", headers=headers).status_code

    def _call_summary():
        return client.get("/api/v1/audit/summary", headers=headers).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for _ in range(15):
            futures.append(executor.submit(_call_records))
            futures.append(executor.submit(_call_verify))
            futures.append(executor.submit(_call_summary))

        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 45
    assert all(code == 200 for code in results)



# ===========================================================================
# UI-6.1.1 Verification Precedence & Two-Layer Integrity Closure Scenarios
# ===========================================================================

def test_precedence_scenario_1_missing_hmac_key_valid_ledger_returns_unavailable(temp_dir, auth_manager):
    """Scenario 1: Missing HMAC key + valid physical ledger -> UNAVAILABLE."""
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)
    with wf._lock:
        wf._signing_key = None

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "UNAVAILABLE"
    assert data["hmac_signatures_valid"] is False
    assert any("signing key unavailable" in err.lower() for err in data["errors"])


def test_precedence_scenario_2_missing_hmac_key_truncated_ledger_returns_incomplete(temp_dir, auth_manager):
    """Scenario 2: Missing HMAC key + truncated physical ledger -> INCOMPLETE.
    Precedence: Layer 1 structural truncation takes precedence over Layer 2 key unavailability.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        wf._signing_key = None

    # Simulate an incomplete/truncated record from partial write or power loss
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('{"sequence_number": 3, "audit_id": "REC-PARTIAL", "truncated\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "INCOMPLETE"
    assert any("truncated record" in err.lower() or "incomplete" in err.lower() for err in data["errors"])


def test_precedence_scenario_3_missing_checkpoint_malformed_json_returns_failed(temp_dir, auth_manager):
    """Scenario 3: Missing checkpoint + malformed JSON -> FAILED.
    Precedence: Layer 1 syntax corruption takes precedence over missing checkpoint anchor.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        wf._checkpoint_anchor = None

    # Append malformed JSON syntax (not an EOF truncation, but corrupted syntax)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('MALFORMED_NON_JSON_RECORD_CONTENT_12345\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert any("malformed json syntax" in err.lower() for err in data["errors"])


def test_precedence_scenario_4_missing_checkpoint_valid_ledger_returns_unavailable(temp_dir, auth_manager):
    """Scenario 4: Missing checkpoint + valid ledger -> UNAVAILABLE."""
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        wf._checkpoint_anchor = None

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "UNAVAILABLE"
    assert data["anchor_present"] is False
    assert any("not configured or unavailable" in err.lower() for err in data["errors"])


def test_precedence_scenario_5_missing_key_broken_hash_chain_returns_failed(temp_dir, auth_manager):
    """Scenario 5: Missing key + broken hash chain -> FAILED.
    Precedence: Pure Layer 1 hash-chain discontinuity does not require HMAC key and takes precedence over UNAVAILABLE.
    """
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)
    with wf._lock:
        wf._signing_key = None
        # Corrupt previous_entry_sha256 on entry 2 in memory
        entry = wf._audit_trail[1]
        corrupted_dict = entry.model_dump()
        corrupted_dict["previous_entry_sha256"] = "1111" * 16
        wf._audit_trail[1] = entry.__class__.model_validate(corrupted_dict)

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert data["hash_chain_valid"] is False
    assert any("broken hash chain" in err.lower() for err in data["errors"])


def test_precedence_scenario_6_both_dependencies_missing_corrupted_ledger_returns_failed(temp_dir, auth_manager):
    """Scenario 6: Both dependencies missing + structurally corrupted ledger -> FAILED.
    Precedence: Layer 1 fatal corruption takes precedence over missing key AND missing anchor.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        wf._signing_key = None
        wf._checkpoint_anchor = None

    # Append corrupted JSON to disk ledger
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('!!!FATAL_CORRUPT_BYTES_ON_DISK!!!\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert any("malformed json syntax" in err.lower() for err in data["errors"])


def test_precedence_scenario_7_valid_empty_ledger_with_genesis_checkpoint_returns_verified(temp_dir, auth_manager):
    """Scenario 7: Valid empty ledger with valid genesis checkpoint -> VERIFIED."""
    anchor_path = temp_dir / "genesis_checkpoint.json"
    ledger_path = temp_dir / "empty_ledger.jsonl"
    anchor = FileBasedCheckpointAnchor(anchor_path=anchor_path)
    wf = HumanApprovalWorkflow(
        signing_key=b"test-secret-key-32-bytes-long-ok",
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["verification_status"] == "VERIFIED"
    assert data["total_records"] == 0
    assert data["records_checked"] == 0
    assert data["hash_chain_valid"] is True
    assert data["checkpoint_parity_valid"] is True


def test_precedence_scenario_8_empty_ledger_with_missing_checkpoint_returns_unavailable(temp_dir, auth_manager):
    """Scenario 8: Empty ledger with missing checkpoint -> UNAVAILABLE."""
    ledger_path = temp_dir / "empty_ledger2.jsonl"
    wf = HumanApprovalWorkflow(
        signing_key=b"test-secret-key-32-bytes-long-ok",
        ledger_path=ledger_path,
        checkpoint_anchor=None,
    )

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "UNAVAILABLE"
    assert data["anchor_present"] is False


def test_precedence_scenario_9_concurrent_read_and_verification_operations(temp_dir, auth_manager):
    """Scenario 9: Concurrent read and verification operations -> Thread-safe 200 OK."""
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=3)
    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)
    headers = {"Authorization": f"Bearer {token}"}

    def _call(endpoint: str):
        return client.get(endpoint, headers=headers).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futs = []
        for _ in range(10):
            futs.append(executor.submit(_call, "/api/v1/audit/records"))
            futs.append(executor.submit(_call, "/api/v1/audit/verify"))
        results = [f.result() for f in futs]

    assert len(results) == 20
    assert all(code == 200 for code in results)


def test_precedence_scenario_10_verification_does_not_mutate_persistent_files(temp_dir, auth_manager):
    """Scenario 10: Verification does not mutate persistent files -> Byte-for-byte identical."""
    wf, ledger_path, anchor_path = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)

    l_before = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    a_before = hashlib.sha256(anchor_path.read_bytes()).hexdigest()

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    for _ in range(3):
        res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200

    l_after = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    a_after = hashlib.sha256(anchor_path.read_bytes()).hexdigest()

    assert l_before == l_after
    assert a_before == a_after
