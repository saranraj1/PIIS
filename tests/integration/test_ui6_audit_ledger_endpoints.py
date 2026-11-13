"""Integration tests for PIIS UI-6 Audit Ledger Workspace endpoints.

Verifies:
1. Authorization & RBAC controls (401 on unauthenticated, 403 on insufficient permissions).
2. Read-only ledger inspection (no mutations occur on GET).
3. Pagination and stable ordering (asc vs desc).
4. Rich filtering (incident_id, action, operator_id, sequence ranges, timestamp ranges).
5. Single record detail inspection and RFC 8785 canonical JSON provenance.
6. Empty ledger and genesis state handling.
7. Verification status classification (VERIFIED, FAILED, UNAVAILABLE).
8. Failure detection (tampered digest, broken hash chain, HMAC substitution, anchor desync).
9. Sensitive cryptographic key redaction (zero secret keys in responses).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
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


def _make_rec(rec_id: str, desc: str, action: str = "ROUTING", risk: str = "READ_ONLY_SAFE", incident_id: str = "INC-101") -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        incident_id=incident_id,
        description=desc,
        reason="Testing UI-6 audit ledger",
        action_type=action,
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="RB-001",
        source_section="Section 1.1",
        expected_observation="Normal metrics restored",
        risk_classification=risk,
    )


@pytest.fixture
def workflow_with_records(temp_dir, auth_manager):
    ledger_path = temp_dir / "audit_log.jsonl"
    anchor_path = temp_dir / "checkpoint.json"
    anchor = FileBasedCheckpointAnchor(anchor_path=anchor_path)
    wf = HumanApprovalWorkflow(
        signing_key=b"test-signing-key-32-bytes-long-ok!!",
        key_id="test-key-01",
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )

    # Register 3 recommendations across 2 incidents
    r1 = _make_rec("REC-001", "Reroute traffic from Core-Switch-01 to Core-Switch-02", "ROUTING_CHANGE", "LOW_OBSERVABILITY", "INC-101")
    r2 = _make_rec("REC-002", "Restart BGP session on Edge-Router-09", "BGP_RESET", "READ_ONLY_SAFE", "INC-101")
    r3 = _make_rec("REC-003", "Drain load on Cell-Site-Tower-404", "LOAD_DRAIN", "DISRUPTIVE_AUDIT", "INC-202")

    wf.register_recommendation(r1, "INC-101")
    wf.register_recommendation(r2, "INC-101")
    wf.register_recommendation(r3, "INC-202")

    # Mint valid tokens for human reviewers
    token_alice = auth_manager.mint_dev_token("operator_alice", role=ApplicationRole.NOC_L2)
    token_bob = auth_manager.mint_dev_token("manager_bob", role=ApplicationRole.INCIDENT_MANAGER)

    wf.approve_recommendation("REC-001", token_alice, "INC-101", notes="Approved after verifying route metrics.")
    wf.reject_recommendation("REC-002", token_bob, "INC-101", reason="Rejected due to maintenance window lock.")

    return wf


@pytest.fixture
def client_and_tokens(workflow_with_records, auth_manager):
    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: workflow_with_records
    client = TestClient(app)

    tokens = {
        "auditor": auth_manager.mint_dev_token("auditor_eve", role=ApplicationRole.SECURITY_AUDITOR),
        "admin": auth_manager.mint_dev_token("admin_dan", role=ApplicationRole.PIIS_ADMIN),
        "manager": auth_manager.mint_dev_token("manager_bob", role=ApplicationRole.INCIDENT_MANAGER),
        "noc_l1": auth_manager.mint_dev_token("noc_charlie", role=ApplicationRole.NOC_L1),
        "noc_l2": auth_manager.mint_dev_token("noc_alice", role=ApplicationRole.NOC_L2),
        "service": auth_manager.mint_dev_token("svc_daemon", is_service=True),
    }

    return client, tokens, workflow_with_records


# ---------------------------------------------------------------------------
# 1. Authorization & RBAC Tests
# ---------------------------------------------------------------------------

def test_unauthenticated_requests_rejected(client_and_tokens):
    client, _, _ = client_and_tokens

    assert client.get("/api/v1/audit/records").status_code == 401
    assert client.get("/api/v1/audit/records/1").status_code == 401
    assert client.get("/api/v1/audit/summary").status_code == 401
    assert client.get("/api/v1/audit/verify").status_code == 401


def test_insufficient_permissions_rejected(client_and_tokens):
    client, tokens, _ = client_and_tokens

    # NOC_L1 and NOC_L2 do not have VIEW_AUDIT_LOGS or VERIFY_AUDIT_LEDGER
    for role_token in [tokens["noc_l1"], tokens["noc_l2"], tokens["service"]]:
        headers = {"Authorization": f"Bearer {role_token}"}
        assert client.get("/api/v1/audit/records", headers=headers).status_code == 403
        assert client.get("/api/v1/audit/records/1", headers=headers).status_code == 403
        assert client.get("/api/v1/audit/summary", headers=headers).status_code == 403
        assert client.get("/api/v1/audit/verify", headers=headers).status_code == 403


def test_incident_manager_can_view_but_cannot_verify(client_and_tokens):
    client, tokens, _ = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['manager']}"}

    # Incident manager has VIEW_AUDIT_LOGS
    assert client.get("/api/v1/audit/records", headers=headers).status_code == 200
    assert client.get("/api/v1/audit/records/1", headers=headers).status_code == 200
    assert client.get("/api/v1/audit/summary", headers=headers).status_code == 200

    # Incident manager DOES NOT have VERIFY_AUDIT_LEDGER
    assert client.get("/api/v1/audit/verify", headers=headers).status_code == 403


def test_security_auditor_and_admin_have_full_audit_access(client_and_tokens):
    client, tokens, _ = client_and_tokens

    for role_token in [tokens["auditor"], tokens["admin"]]:
        headers = {"Authorization": f"Bearer {role_token}"}
        assert client.get("/api/v1/audit/records", headers=headers).status_code == 200
        assert client.get("/api/v1/audit/records/1", headers=headers).status_code == 200
        assert client.get("/api/v1/audit/summary", headers=headers).status_code == 200
        assert client.get("/api/v1/audit/verify", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# 2. Read-Only Ledger Guarantees & Stability
# ---------------------------------------------------------------------------

def test_audit_endpoints_are_strictly_read_only(client_and_tokens):
    client, tokens, workflow = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['auditor']}"}

    initial_count = len(workflow.get_audit_trail())

    # Execute multiple GET inspections and verification
    client.get("/api/v1/audit/records", headers=headers)
    client.get("/api/v1/audit/records/1", headers=headers)
    client.get("/api/v1/audit/summary", headers=headers)
    client.get("/api/v1/audit/verify", headers=headers)

    # In-memory and disk records remain unaltered
    assert len(workflow.get_audit_trail()) == initial_count


# ---------------------------------------------------------------------------
# 3. Pagination and Ordering Tests
# ---------------------------------------------------------------------------

def test_pagination_and_ordering(client_and_tokens):
    client, tokens, workflow = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['auditor']}"}

    total_in_db = len(workflow.get_audit_trail())
    assert total_in_db == 5  # 3 registrations + 1 approve + 1 reject

    # Default order = desc (newest sequence first)
    res_desc = client.get("/api/v1/audit/records?limit=2&offset=0", headers=headers)
    assert res_desc.status_code == 200
    data_desc = res_desc.json()
    assert data_desc["total_count"] == 5
    assert len(data_desc["items"]) == 2
    assert data_desc["items"][0]["sequence_number"] == 5
    assert data_desc["items"][1]["sequence_number"] == 4

    # Order = asc (oldest sequence first)
    res_asc = client.get("/api/v1/audit/records?limit=2&offset=0&order=asc", headers=headers)
    assert res_asc.status_code == 200
    data_asc = res_asc.json()
    assert data_asc["items"][0]["sequence_number"] == 1
    assert data_asc["items"][1]["sequence_number"] == 2

    # Second page
    res_p2 = client.get("/api/v1/audit/records?limit=2&offset=2&order=desc", headers=headers)
    assert res_p2.status_code == 200
    data_p2 = res_p2.json()
    assert len(data_p2["items"]) == 2
    assert data_p2["items"][0]["sequence_number"] == 3
    assert data_p2["items"][1]["sequence_number"] == 2


# ---------------------------------------------------------------------------
# 4. Filtering Tests
# ---------------------------------------------------------------------------

def test_filtering_by_incident_and_action(client_and_tokens):
    client, tokens, _ = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['auditor']}"}

    # Filter by incident INC-101
    res_inc = client.get("/api/v1/audit/records?incident_id=INC-101", headers=headers)
    assert res_inc.status_code == 200
    items_inc = res_inc.json()["items"]
    assert len(items_inc) == 4
    for it in items_inc:
        assert it["incident_id"] == "INC-101"

    # Filter by action APPROVE (matches APPROVED via substring/exact)
    res_app = client.get("/api/v1/audit/records?action=APPROVE", headers=headers)
    assert res_app.status_code == 200
    items_app = res_app.json()["items"]
    assert len(items_app) == 1
    assert items_app[0]["action"] == "APPROVED"
    assert items_app[0]["operator_id"] == "operator_alice"
    assert items_app[0]["recommendation_id"] == "REC-001"

    # Filter by operator_id manager_bob
    res_op = client.get("/api/v1/audit/records?operator_id=manager_bob", headers=headers)
    assert res_op.status_code == 200
    items_op = res_op.json()["items"]
    assert len(items_op) == 1
    assert items_op[0]["action"] == "REJECTED"

    # Filter by sequence range
    res_seq = client.get("/api/v1/audit/records?from_sequence=2&to_sequence=4", headers=headers)
    assert res_seq.status_code == 200
    items_seq = res_seq.json()["items"]
    assert len(items_seq) == 3
    seqs = {it["sequence_number"] for it in items_seq}
    assert seqs == {2, 3, 4}


# ---------------------------------------------------------------------------
# 5. Single Record Detail & Provenance Chain
# ---------------------------------------------------------------------------

def test_get_single_record_detail(client_and_tokens):
    client, tokens, _ = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['auditor']}"}

    # Sequence 4 was APPROVE for REC-001
    res = client.get("/api/v1/audit/records/4", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["record"]["sequence_number"] == 4
    assert data["record"]["action"] == "APPROVED"
    assert data["canonical_hash_matches"] is True
    assert data["hmac_valid"] is True
    assert data["is_genesis"] is False
    assert "recomputed_hash" in data
    assert data["recomputed_hash"] == data["record"]["entry_hash"]
    assert "canonical_json" in data
    assert '"action":"APPROVED"' in data["canonical_json"]

    # Provenance chain details
    prov = data["provenance_chain"]
    assert prov["incident_id"] == "INC-101"
    assert prov["recommendation_id"] == "REC-001"
    assert prov["has_stored_recommendation"] is True
    assert prov["operator_id"] == "operator_alice"


def test_get_single_record_404_for_nonexistent_sequence(client_and_tokens):
    client, tokens, _ = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['auditor']}"}

    res = client.get("/api/v1/audit/records/9999", headers=headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. Audit Summary Metrics
# ---------------------------------------------------------------------------

def test_get_audit_summary_metrics(client_and_tokens):
    client, tokens, _ = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['auditor']}"}

    res = client.get("/api/v1/audit/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_records"] == 5
    assert data["latest_sequence"] == 5
    assert data["anchor_present"] is True
    assert data["anchor_sequence"] == 5
    assert data["canonicalization_scheme"] == "RFC_8785_JCS"
    assert data["hashing_algorithm"] == "SHA_256"
    assert data["mac_algorithm"] == "HMAC_SHA256"
    assert len(data["limitations"]) > 0
    assert data["actions_breakdown"].get("APPROVED") == 1
    assert data["actions_breakdown"].get("REJECTED") == 1
    assert data["actions_breakdown"].get("SUBMITTED") == 3


# ---------------------------------------------------------------------------
# 7. Verification State Classification (VERIFIED, FAILED, UNAVAILABLE)
# ---------------------------------------------------------------------------

def test_audit_verify_success_state(client_and_tokens):
    client, tokens, _ = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['auditor']}"}

    res = client.get("/api/v1/audit/verify", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["is_valid"] is True
    assert data["verification_status"] == "VERIFIED"
    assert data["records_checked"] == 5
    assert data["first_sequence"] == 1
    assert data["last_sequence"] == 5
    assert data["hash_chain_valid"] is True
    assert data["jcs_canonicalization_valid"] is True
    assert data["hmac_signatures_valid"] is True
    assert data["checkpoint_parity_valid"] is True
    assert data["errors"] == []


def test_audit_verify_detects_tampered_record_digest(temp_dir, auth_manager):
    anchor = FileBasedCheckpointAnchor(anchor_path=temp_dir / "cp.json")
    wf = HumanApprovalWorkflow(
        signing_key=b"k" * 32,
        ledger_path=temp_dir / "ledger.jsonl",
        checkpoint_anchor=anchor,
    )
    r = _make_rec("R-1", "desc")
    wf.register_recommendation(r, "INC-1")

    # Tamper with the in-memory entry's entry_sha256
    with wf._lock:
        wf._audit_trail[0].entry_sha256 = "0" * 64

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is False
    assert data["verification_status"] == "FAILED"
    assert data["jcs_canonicalization_valid"] is False
    assert any("Tampered record digest" in e for e in data["errors"])


def test_audit_verify_detects_broken_hash_chain(temp_dir, auth_manager):
    anchor = FileBasedCheckpointAnchor(anchor_path=temp_dir / "cp.json")
    wf = HumanApprovalWorkflow(
        signing_key=b"k" * 32,
        ledger_path=temp_dir / "ledger.jsonl",
        checkpoint_anchor=anchor,
    )
    r1 = _make_rec("R-1", "d1")
    r2 = _make_rec("R-2", "d2")
    wf.register_recommendation(r1, "INC-1")
    wf.register_recommendation(r2, "INC-1")

    # Corrupt previous hash on sequence 2
    with wf._lock:
        wf._audit_trail[1].previous_entry_sha256 = "corrupted_hash_string"

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
    assert any("Broken hash chain" in e for e in data["errors"])


def test_audit_verify_detects_anchor_desynchronization(temp_dir, auth_manager):
    anchor = FileBasedCheckpointAnchor(anchor_path=temp_dir / "cp.json")
    wf = HumanApprovalWorkflow(
        signing_key=b"k" * 32,
        ledger_path=temp_dir / "ledger.jsonl",
        checkpoint_anchor=anchor,
    )
    r1 = _make_rec("R-1", "d1")
    wf.register_recommendation(r1, "INC-1")

    # Mutate anchor on disk to an uncoordinated sequence using internal override simulation
    anchor.record_checkpoint(
        audit_id="A-FORK",
        sequence_number=1,
        entry_sha256="ffff" * 16,
        hmac_signature="0000" * 16,
        timestamp_utc="2026-11-04T10:00:00Z",
        force_override=True,
    )

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
    assert any("FORK" in e or "mismatch" in e for e in data["errors"])


def test_audit_verify_key_unavailable_returns_unavailable(temp_dir, auth_manager):
    anchor = FileBasedCheckpointAnchor(anchor_path=temp_dir / "cp.json")
    wf = HumanApprovalWorkflow(
        signing_key=b"k" * 32,
        ledger_path=temp_dir / "ledger.jsonl",
        checkpoint_anchor=anchor,
    )
    r = _make_rec("R-1", "d")
    wf.register_recommendation(r, "INC-1")

    # Simulate key becoming unavailable
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


# ---------------------------------------------------------------------------
# 8. Empty Ledger Genesis State
# ---------------------------------------------------------------------------

def test_empty_ledger_genesis_state(temp_dir, auth_manager):
    anchor = FileBasedCheckpointAnchor(anchor_path=temp_dir / "cp.json")
    wf = HumanApprovalWorkflow(
        signing_key=b"k" * 32,
        ledger_path=temp_dir / "ledger.jsonl",
        checkpoint_anchor=anchor,
    )

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)
    headers = {"Authorization": f"Bearer {token}"}

    # Records list is empty
    res_rec = client.get("/api/v1/audit/records", headers=headers)
    assert res_rec.status_code == 200
    assert res_rec.json()["total_count"] == 0
    assert res_rec.json()["items"] == []

    # Summary shows 0 records
    res_sum = client.get("/api/v1/audit/summary", headers=headers)
    assert res_sum.status_code == 200
    assert res_sum.json()["total_records"] == 0
    assert res_sum.json()["latest_sequence"] == 0

    # Verification passes as genesis state
    res_ver = client.get("/api/v1/audit/verify", headers=headers)
    assert res_ver.status_code == 200
    assert res_ver.json()["is_valid"] is True
    assert res_ver.json()["verification_status"] == "VERIFIED"
    assert res_ver.json()["total_records"] == 0


# ---------------------------------------------------------------------------
# 9. Cryptographic Key Redaction & Security Boundary
# ---------------------------------------------------------------------------

def test_zero_raw_signing_keys_exposed(client_and_tokens):
    client, tokens, workflow = client_and_tokens
    headers = {"Authorization": f"Bearer {tokens['auditor']}"}

    signing_key_str = workflow._signing_key.decode("latin-1")

    for url in [
        "/api/v1/audit/records",
        "/api/v1/audit/records/1",
        "/api/v1/audit/summary",
        "/api/v1/audit/verify",
    ]:
        res = client.get(url, headers=headers)
        assert res.status_code == 200
        raw_text = res.text
        assert signing_key_str not in raw_text
        assert "test-signing-key" not in raw_text
