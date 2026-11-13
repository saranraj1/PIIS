"""UI-6.1.2 Regression Test Suite: JSONL Truncation Classification & Final Milestone Freeze.

Validates the precise two-layer classification rules:
- INCOMPLETE: Used only when the final physical ledger record demonstrates a credible
  incomplete-write condition (unfinished JSON object at unexpected EOF).
- FAILED: Used when there is evidence of malformed or corrupted content:
  * Invalid JSON syntax not demonstrably an interrupted final append.
  * Malformed records before the final physical line (middle-record corruption).
  * Structurally invalid records / non-conformant schema.
  * Broken sequence continuity or hash-chain relationships.
- UNAVAILABLE: Used when structural verification passes, but required key/anchor is missing.
- VERIFIED: Used when all structural, cryptographic, and parity checks pass.

Tests 12 explicit regression scenarios:
1. Valid final JSONL record.
2. Final line containing an unfinished JSON object.
3. Final line containing arbitrary garbage.
4. Final line containing invalid JSON with a closing brace.
5. Malformed JSON in the middle of the ledger.
6. Empty final line after a valid record.
7. Valid JSON with an invalid record schema.
8. Truncated final record combined with a missing HMAC key.
9. Malformed middle record combined with a missing checkpoint.
10. Multiple valid records followed by an interrupted final append.
11. File ending without a newline but containing a complete valid JSON record.
12. A JSON string containing escaped braces and quotes.
"""

from __future__ import annotations

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
    action: str = "CHECK_METRICS",
    risk: str = "READ_ONLY_SAFE",
    incident_id: str = "INC-101",
) -> DiagnosticRecommendation:
    return DiagnosticRecommendation(
        recommendation_id=rec_id,
        incident_id=incident_id,
        description=desc,
        reason="Testing UI-6.1.2 truncation classification semantics",
        action_type=action,
        supporting_evidence_ids=["EVID-001"],
        source_runbook_id="RB-001",
        source_section="Section 1.1",
        expected_observation="Normal metrics restored",
        risk_classification=risk,
    )


def _setup_seeded_workflow(temp_dir, auth_manager, num_records: int = 2):
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
# Scenario 1: Valid final JSONL record
# ---------------------------------------------------------------------------
def test_scenario_01_valid_final_jsonl_record(temp_dir, auth_manager):
    """Scenario 1: Valid final JSONL record -> VERIFIED, is_valid=True, errors=[]."""
    wf, _, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)
    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "VERIFIED"
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0
    assert data["error"] is None
    assert data["hash_chain_valid"] is True
    assert data["checkpoint_parity_valid"] is True


# ---------------------------------------------------------------------------
# Scenario 2: Final line containing an unfinished JSON object
# ---------------------------------------------------------------------------
def test_scenario_02_final_line_unfinished_json_object(temp_dir, auth_manager):
    """Scenario 2: Final line containing an unfinished JSON object -> INCOMPLETE.
    Asserts exact category, affected physical line number, and is_valid=False.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # The ledger currently has 2 lines (register + approve REC-001)
    # Append an unfinished JSON object as line 3
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('{"sequence_number": 3, "audit_id": "REC-PARTIAL", "action": "REG\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "INCOMPLETE"
    assert data["is_valid"] is False
    assert any("line 3" in err for err in data["errors"])
    assert any("truncated record" in err.lower() or "malformed or truncated" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# Scenario 3: Final line containing arbitrary garbage
# ---------------------------------------------------------------------------
def test_scenario_03_final_line_arbitrary_garbage(temp_dir, auth_manager):
    """Scenario 3: Final line containing arbitrary garbage -> FAILED.
    Must NOT be classified as truncation because it lacks a JSON object prefix.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # Line 3 is arbitrary garbage
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('GARBAGE_PAYLOAD_NOT_JSON_DATA_AT_ALL_12345\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "FAILED"
    assert data["is_valid"] is False
    assert any("line 3" in err for err in data["errors"])
    assert any("malformed json syntax" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# Scenario 4: Final line containing invalid JSON with a closing brace
# ---------------------------------------------------------------------------
def test_scenario_04_final_line_invalid_json_with_closing_brace(temp_dir, auth_manager):
    """Scenario 4: Final line containing invalid JSON with a closing brace -> FAILED.
    Presence of closing brace proves complete construct; syntax error is corruption, not truncation.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # Line 3 has syntax error but ends with closing brace
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('{"sequence_number": 3, invalid_unquoted_syntax: true}\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "FAILED"
    assert data["is_valid"] is False
    assert any("line 3" in err for err in data["errors"])
    assert any("malformed json syntax" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# Scenario 5: Malformed JSON in the middle of the ledger
# ---------------------------------------------------------------------------
def test_scenario_05_malformed_json_in_middle_of_ledger(temp_dir, auth_manager):
    """Scenario 5: Malformed JSON in the middle of the ledger -> FAILED.
    Even if it looks like an unfinished JSON object, being followed by subsequent lines
    proves it is corruption, NOT an interrupted final append.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # Replace ledger with:
    # Line 1: valid record (seq 1)
    # Line 2: malformed unfinished object in middle
    # Line 3: valid record (seq 2)
    entry1 = wf._audit_trail[0].model_dump_json()
    entry2 = wf._audit_trail[1].model_dump_json()

    with ledger_path.open("w", encoding="utf-8") as f:
        f.write(entry1 + "\n")
        f.write('{"sequence_number": 2, "audit_id": "REC-002", "incomplete_mid\n')
        f.write(entry2 + "\n")

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "FAILED"
    assert data["is_valid"] is False
    assert any("line 2" in err for err in data["errors"])
    assert any("malformed record before final line" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# Scenario 6: Empty final line after a valid record
# ---------------------------------------------------------------------------
def test_scenario_06_empty_final_line_after_valid_record(temp_dir, auth_manager):
    """Scenario 6: Empty final line after a valid record -> VERIFIED.
    Trailing newlines are standard in POSIX and JSONL and must not cause errors.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=2)
    # Append multiple blank/empty lines to the ledger
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write("\n\n   \n\t\n")

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "VERIFIED"
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0


# ---------------------------------------------------------------------------
# Scenario 7: Valid JSON with an invalid record schema
# ---------------------------------------------------------------------------
def test_scenario_07_valid_json_with_invalid_record_schema(temp_dir, auth_manager):
    """Scenario 7: Valid JSON with an invalid record schema -> FAILED.
    A complete valid JSON object that violates the audit record schema is corruption, NOT truncation.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # Line 3 is valid JSON, but completely non-conformant schema
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('{"arbitrary_non_audit_key": "some_value", "number": 999}\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "FAILED"
    assert data["is_valid"] is False
    assert any("line 3" in err for err in data["errors"])
    assert any("structurally invalid" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# Scenario 8: Truncated final record combined with a missing HMAC key
# ---------------------------------------------------------------------------
def test_scenario_08_truncated_final_record_with_missing_hmac_key(temp_dir, auth_manager):
    """Scenario 8: Truncated final record + missing HMAC key -> INCOMPLETE.
    Precedence: Layer 1 truncation takes precedence over Layer 2 key unavailability.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        wf._signing_key = None

    # Line 3 is an interrupted final append
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('{"sequence_number": 3, "audit_id": "REC-003", "truncated\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "INCOMPLETE"
    assert data["is_valid"] is False
    assert any("line 3" in err for err in data["errors"])
    assert any("signing key unavailable" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# Scenario 9: Malformed middle record combined with a missing checkpoint
# ---------------------------------------------------------------------------
def test_scenario_09_malformed_middle_record_with_missing_checkpoint(temp_dir, auth_manager):
    """Scenario 9: Malformed middle record + missing checkpoint -> FAILED.
    Precedence: Layer 1 fatal corruption takes precedence over Layer 2 missing checkpoint.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    with wf._lock:
        wf._checkpoint_anchor = None

    # Write: line 1 valid, line 2 corrupt, line 3 valid
    entry1 = wf._audit_trail[0].model_dump_json()
    entry2 = wf._audit_trail[1].model_dump_json()
    with ledger_path.open("w", encoding="utf-8") as f:
        f.write(entry1 + "\n")
        f.write('MALFORMED_MIDDLE_LINE_GARBAGE\n')
        f.write(entry2 + "\n")

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "FAILED"
    assert data["is_valid"] is False
    assert any("line 2" in err for err in data["errors"])
    assert any("malformed record before final line" in err.lower() for err in data["errors"])
    assert any("checkpoint anchor is not configured or unavailable" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# Scenario 10: Multiple valid records followed by an interrupted final append
# ---------------------------------------------------------------------------
def test_scenario_10_multiple_valid_records_followed_by_interrupted_final_append(temp_dir, auth_manager):
    """Scenario 10: Multiple valid records followed by an interrupted final append -> INCOMPLETE.
    Lines 1..4 valid, line 5 truncated.
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=3)
    # The workflow currently has 4 records in ledger: 3 register + 1 approve (lines 1..4)
    # Append line 5 as an interrupted append
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write('{"sequence_number": 5, "audit_id": "REC-005", "operator_id": "alice", "action": "REG\n')

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "INCOMPLETE"
    assert data["is_valid"] is False
    assert any("line 5" in err for err in data["errors"])
    assert any("truncated record" in err.lower() or "malformed or truncated" in err.lower() for err in data["errors"])


# ---------------------------------------------------------------------------
# Scenario 11: File ending without a newline but containing a complete valid JSON record
# ---------------------------------------------------------------------------
def test_scenario_11_file_ending_without_newline_complete_record(temp_dir, auth_manager):
    """Scenario 11: File ending without a newline but containing a complete valid JSON record -> VERIFIED.
    Asserts complete cryptographic verification succeeds (is_valid=True).
    """
    wf, ledger_path, _ = _setup_seeded_workflow(temp_dir, auth_manager, num_records=1)
    # Read entire ledger and strip the trailing newline character
    content = ledger_path.read_text(encoding="utf-8")
    assert content.endswith("\n")
    ledger_path.write_text(content.rstrip("\r\n"), encoding="utf-8")

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "VERIFIED"
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0
    assert data["hash_chain_valid"] is True
    assert data["checkpoint_parity_valid"] is True


# ---------------------------------------------------------------------------
# Scenario 12: A JSON string containing escaped braces and quotes
# ---------------------------------------------------------------------------
def test_scenario_12_json_string_with_escaped_braces_and_quotes(temp_dir, auth_manager):
    """Scenario 12: A JSON string containing escaped braces and quotes -> VERIFIED.
    RFC 8785 canonicalization and JSON parser must handle escaped characters without false alarms.
    """
    ledger_path = temp_dir / "audit_log_escaped.jsonl"
    anchor_path = temp_dir / "checkpoint_escaped.json"
    anchor = FileBasedCheckpointAnchor(anchor_path=anchor_path)
    wf = HumanApprovalWorkflow(
        signing_key=b"test-secret-key-32-bytes-long-ok",
        key_id="test-key-01",
        ledger_path=ledger_path,
        checkpoint_anchor=anchor,
    )

    rec = _make_rec("REC-ESC-01", "Testing escaped sequences in JSON fields")
    wf.register_recommendation(rec, "INC-ESC-01")

    # Approve with complex escaped strings: braces, double-quotes, tabs, and newlines
    escaped_notes = 'Review with {"bracket_key": "val"} and \\"quoted\\" words and \\\\ backslash.'
    token = auth_manager.mint_dev_token("alice", role=ApplicationRole.NOC_L2)
    wf.approve_recommendation("REC-ESC-01", token, "INC-ESC-01", notes=escaped_notes)

    app = create_app()
    app.dependency_overrides[get_workflow] = lambda: wf
    client = TestClient(app)
    token = auth_manager.mint_dev_token("auditor", role=ApplicationRole.SECURITY_AUDITOR)

    res = client.get("/api/v1/audit/verify", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["verification_status"] == "VERIFIED"
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0
    assert data["hash_chain_valid"] is True
    assert data["jcs_canonicalization_valid"] is True
    assert data["hmac_signatures_valid"] is True
    assert data["checkpoint_parity_valid"] is True
